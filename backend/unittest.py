# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from backend.models import Person, Process, AM
from backend import const
from django.utils.timezone import now
from django.test import Client
import datetime
import os
import io
import re
import six


class NamedObjects(dict):
    """
    Container for fixture model objects.
    """
    def __init__(self, model, **defaults):
        super(NamedObjects, self).__init__()
        self._model = model
        self._defaults = defaults

    def __getitem__(self, key):
        """
        Dict that only looks things up if they are strings, otherwise just return key.

        This allows to use __getitem__ with already resolved objects, just to have
        functions that can take either objects or their fixture names.
        """
        if not isinstance(key, basestring): return key
        return super(NamedObjects, self).__getitem__(key)

    def __getattr__(self, key):
        """
        Make dict elements also appear as class members
        """
        res = self.get(key, None)
        if res is not None: return res
        raise AttributeError("member {} not found".format(key))

    def _update_kwargs_with_defaults(self, _name, kw):
        """
        Update the kw dict with defaults from self._defaults.

        If self._defaults for an argument is a string, then calls .format() on
        it passing _name and self._defaults as format arguments.
        """
        for k, v in self._defaults.items():
            if isinstance(v, six.string_types):
                kw.setdefault(k, v.format(_name=_name, **self._defaults))
            elif hasattr(v, "__call__"):
                kw.setdefault(k, v(_name, **self._defaults))
            else:
                kw.setdefault(k, v)

    def create(self, _name, **kw):
        self._update_kwargs_with_defaults(_name, kw)
        self[_name] = o = self._model.objects.create(**kw)
        return o

    def refresh(self):
        """
        Reload all the objects from the database.

        This is needed because although Django's TestCase rolls back the
        database after a test, the data stored in memory in the objects stored
        in NamedObjects repositories is not automatically refreshed.
        """
        # FIXME: when we get Django 1.8, we can just do
        # for o in self.values(): o.refresh_from_db()
        for name, o in list(self.items()):
            try:
                self[name] = self._model.objects.get(pk=o.pk)
            except self._model.DoesNotExist:
                del self[name]

    def delete_all(self):
        """
        Call delete() on all model objects registered in this dict.

        This can be used in methods like tearDownClass to remove objects common
        to all tests.
        """
        for o in self.values():
            o.delete()


class TestPersons(NamedObjects):
    def __init__(self, **defaults):
        defaults.setdefault("cn", lambda name, **kw: name.capitalize())
        defaults.setdefault("email", "{_name}@example.org")
        super(TestPersons, self).__init__(Person, **defaults)

    def create(self, _name, alioth=False, **kw):
        if alioth:
            kw.setdefault("username", _name + "-guest@users.alioth.debian.org")
        else:
            kw.setdefault("username", _name + "@debian.org")
        kw.setdefault("uid", _name)
        self._update_kwargs_with_defaults(_name, kw)
        self[_name] = o = self._model.objects.create_user(audit_skip=True, **kw)
        return o


class TestProcesses(NamedObjects):
    def __init__(self, **defaults):
        super(TestProcesses, self).__init__(Process, **defaults)
        defaults.setdefault("progress", const.PROGRESS_APP_NEW)

    def create(self, _name, advocates=[], **kw):
        self._update_kwargs_with_defaults(_name, kw)

        if "process" in kw:
            kw.setdefault("is_active", kw["process"] not in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED))
        else:
            kw.setdefault("is_active", True)

        if "manager" in kw:
            try:
                am = kw["manager"].am
            except AM.DoesNotExist:
                am = AM.objects.create(person=kw["manager"])
            kw["manager"] = am

        self[_name] = o = self._model.objects.create(**kw)
        for a in advocates:
            o.advocates.add(a)
        return o


class TestKeys(NamedObjects):
    def __init__(self, **defaults):
        from keyring.models import Key
        super(TestKeys, self).__init__(Key, **defaults)

    def create(self, _name, **kw):
        self._update_kwargs_with_defaults(_name, kw)
        self._model.objects.test_preload(_name)
        self[_name] = o = self._model.objects.get_or_download(_name, **kw)
        return o


class TestMeta(type):
    def __new__(cls, name, bases, attrs):
        res = super(TestMeta, cls).__new__(cls, name, bases, attrs)
        if hasattr(res, "__add_extra_tests__"):
            res.__add_extra_tests__()
        return res


@six.add_metaclass(TestMeta)
class TestBase(object):
    @classmethod
    def _add_method(cls, meth, *args, **kw):
        """
        Add a test method, made of the given method called with the given args
        and kwargs.

        The method name and args are used to built the test method name, the
        kwargs are not: make sure you use the args to make the test case
        unique, and the kwargs for things you do not want to appear in the test
        name, like the expected test results for those args.
        """
        name = re.sub(r"[^0-9A-Za-z_]", "_", "{}_{}".format(meth.__name__.lstrip("_"), "_".join(str(x) for x in args)))
        setattr(cls, name, lambda self: meth(self, *args, **kw))

    def make_test_client(self, person, sso_username=None, **kw):
        """
        Instantiate a test client, logging in the given person.

        If person is None, visit anonymously. If person is None but
        sso_username is not None, authenticate as the given sso_username even
        if a Person record does not exist.
        """
        person = self.persons[person]
        if person is not None:
            kw["SSL_CLIENT_S_DN_CN"] = person.username
        elif sso_username is not None:
            kw["SSL_CLIENT_S_DN_CN"] = sso_username
        return Client(**kw)

    def assertPermissionDenied(self, response):
        if response.status_code == 403:
            pass
        else:
            self.fail("response has status code {} instead of a 403 Forbidden".format(response.status_code))

    def assertRedirectMatches(self, response, target):
        if response.status_code != 302:
            self.fail("response has status code {} instead of a Redirect".format(response.status_code))
        if target and not re.search(target, response["Location"]):
            self.fail("response redirects to {} which does not match {}".format(response["Location"], target))

    def assertFormErrorMatches(self, response, form_name, field_name, regex):
        form = response.context[form_name]
        errors = form.errors
        if not errors: self.fail("Form {} has no errors".format(form_name))
        if field_name not in errors: self.fail("Form {} has no errors in field {}".format(form_name, field_name))
        match = re.compile(regex)
        for errmsg in errors[field_name]:
            if match.search(errmsg): return
        self.fail("{} dit not match any in {}".format(regex, repr(errors)))


class BaseFixtureMixin(TestBase):
    @classmethod
    def get_persons_defaults(cls):
        """
        Get default arguments for test persons
        """
        return {}

    @classmethod
    def get_processes_defaults(cls):
        """
        Get default arguments for test processes
        """
        return {}

    @classmethod
    def setUpClass(cls):
        super(BaseFixtureMixin, cls).setUpClass()
        cls.persons = TestPersons(**cls.get_persons_defaults())
        cls.processes = TestProcesses(**cls.get_processes_defaults())
        cls.ams = NamedObjects(AM)
        cls.keys = TestKeys()

        # Preload two keys
        cls.keys.create("66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB")
        cls.keys.create("1793D6AB75663E6BF104953A634F4BD1E7AD5568")

    @classmethod
    def tearDownClass(cls):
        cls.keys.delete_all()
        cls.ams.delete_all()
        cls.processes.delete_all()
        cls.persons.delete_all()
        super(BaseFixtureMixin, cls).tearDownClass()

    def setUp(self):
        super(BaseFixtureMixin, self).setUp()
        self.persons.refresh();
        self.processes.refresh();
        self.ams.refresh();
        self.keys.refresh();


class PersonFixtureMixin(BaseFixtureMixin):
    """
    Pre-create some persons
    """
    @classmethod
    def setUpClass(cls):
        super(PersonFixtureMixin, cls).setUpClass()
        # pending account
        cls.persons.create("pending", status=const.STATUS_DC, expires=now() + datetime.timedelta(days=1), pending="12345", alioth=True)
        # debian contributor
        cls.persons.create("dc", status=const.STATUS_DC, alioth=True)
        # debian contributor with guest account
        cls.persons.create("dc_ga", status=const.STATUS_DC_GA, alioth=True)
        # dm
        cls.persons.create("dm", status=const.STATUS_DM, alioth=True)
        # dm with guest account
        cls.persons.create("dm_ga", status=const.STATUS_DM_GA, alioth=True)
        # dd, nonuploading
        cls.persons.create("dd_nu", status=const.STATUS_DD_NU)
        # dd, uploading
        cls.persons.create("dd_u", status=const.STATUS_DD_U)
        # fd
        fd = cls.persons.create("fd", status=const.STATUS_DD_NU)
        cls.ams.create("fd", person=fd, is_fd=True)
        # dam
        dam = cls.persons.create("dam", status=const.STATUS_DD_NU)
        cls.ams.create("dam", person=dam, is_fd=True, is_dam=True)
