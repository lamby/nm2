# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from . import models as bmodels
from . import const
from django.core.urlresolvers import reverse
from django.test import Client, override_settings
from django.utils.timezone import now
import datetime
import re

# Warning: do not write new tests using this infrastructure. See
# backend.unittest for one that leads to faster and more readable tests.
# This is here only until all the old tests get rewritten.

class NMFactoryMixin(object):
    def setUp(self):
        super(NMFactoryMixin, self).setUp()
        self.users = {}

    def make_user(self, tag, status, alioth=False, **kw):
        if alioth:
            uid = tag + "-guest"
            username = uid + "@users.alioth.debian.org"
        else:
            uid = tag
            username = uid + "@debian.org"

        kw.setdefault("email", tag + "@example.org")
        kw.setdefault("cn", tag.capitalize())

        res = bmodels.Person.objects.create_user(username=username,
                                    uid=uid,
                                    status=status,
                                    audit_skip=True,
                                    **kw)
        self.users[tag] = res
        return res

    def make_process(self, applicant, applying_for, progress, applying_as=None, advocates=[], manager=None):
        """
        Create a process for the given applicant
        """
        if applying_as is None: applying_as = applicant.status
        proc = bmodels.Process(person=applicant,
                               applying_as=applying_as,
                               applying_for=applying_for,
                               progress=progress,
                               is_active=progress not in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED))
        if manager:
            try:
                am = manager.am
            except bmodels.AM.DoesNotExist:
                am = bmodels.AM.objects.create(person=manager)
            proc.manager = am

        proc.save()

        for a in advocates:
            proc.advocates.add(a)

        return proc


class NMBasicFixtureMixin(NMFactoryMixin):
    def setUp(self):
        super(NMBasicFixtureMixin, self).setUp()

        # anonymous
        # pending account
        self.make_user("pending", const.STATUS_DC, expires=now() + datetime.timedelta(days=1), pending="12345", alioth=True)
        # debian contributor
        self.make_user("dc", const.STATUS_DC, alioth=True)
        # debian contributor with guest account
        self.make_user("dc_ga", const.STATUS_DC_GA, alioth=True)
        # dm
        self.make_user("dm", const.STATUS_DM, alioth=True)
        # dm with guest account
        self.make_user("dm_ga", const.STATUS_DM_GA, alioth=True)
        # dd, nonuploading
        self.make_user("dd_nu", const.STATUS_DD_NU)
        # dd, uploading
        self.make_user("dd_u", const.STATUS_DD_U)
#        # non-dd applicant
#        app_dc = self.make_user("app_dc", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
#        # non-dd applicant
#        app_dc_ga = self.make_user("app_dc_ga", const.STATUS_DC_GA, alioth=True, fd_comment="FD_COMMENTS")
#        # non-dd applicant
#        app_dm = self.make_user("app_dm", const.STATUS_DM, alioth=True, fd_comment="FD_COMMENTS")
#        # non-dd applicant
#        app_dm_ga = self.make_user("app_dm_ga", const.STATUS_DM_GA, alioth=True, fd_comment="FD_COMMENTS")
#        # dd advocate
#        adv = self.make_user("adv", const.STATUS_DD_NU)
#        # dd advocate of a past process
#        adv_past = self.make_user("adv_past", const.STATUS_DD_NU)
#        # am of applicant
#        am =self.make_user("am", const.STATUS_DD_NU)
#        am_am = bmodels.AM.objects.create(person=am, slots=1)
#        proc = bmodels.Process.objects.create(person=applicant,
#                                       applying_as=const.STATUS_DC_GA,
#                                       applying_for=const.STATUS_DD_NU,
#                                       progress=const.PROGRESS_AM,
#                                       manager=am_am,
#                                       is_active=True)
#        proc.advocates.add(adv)
#        # am not of applicant
#        am_other = self.make_user("am_other", const.STATUS_DD_NU)
#        bmodels.AM.objects.create(person=am_other, slots=1)
#        # am of a past process
#        am_past = self.make_user("am_past", const.STATUS_DD_NU)
#        am_am_past = bmodels.AM.objects.create(person=am_past, slots=1)
#        proc = bmodels.Process.objects.create(person=applicant,
#                                       applying_as=const.STATUS_DC,
#                                       applying_for=const.STATUS_DC_GA,
#                                       progress=const.PROGRESS_DONE,
#                                       manager=am_am_past,
#                                       is_active=False)
#        proc.advocates.add(adv_past)
        # fd
        fd = self.make_user("fd", const.STATUS_DD_NU)
        bmodels.AM.objects.create(person=fd, is_fd=True)
        # dam
        dam = self.make_user("dam", const.STATUS_DD_NU)
        bmodels.AM.objects.create(person=dam, is_fd=True, is_dam=True)


# Inspired from http://blog.liw.fi/posts/yarn/

class NMTestUtilsWhen(object):
    method = "get"
    url = None
    user = None
    data = None # Optional dict with GET or POST data
    data_content_type = None # Content type to use for POST request. See: http://stackoverflow.com/questions/11802299/django-testing-post-based-views-with-json-objects

    def __init__(self, method=None, url=None, user=None, data=None, data_content_type=None, **kw):
        """
        Set up the parameters used by assertVisit to make a request
        """
        # Override the class defaults with the constructor arguments
        if method is not None: self.method = method
        if self.url is None or url is not None: self.url = url
        if self.user is None or user is not None: self.user = user
        if self.data is None or data is not None: self.data = data
        if self.data_content_type is None or data_content_type is not None: self.data_content_type = data_content_type
        self.args = kw

    def setUp(self, fixture):
        """
        Normalise the parameters using data from the fixture
        """
        if isinstance(self.user, basestring):
            self.user = getattr(fixture, "user_{}".format(self.user))
        if self.data is None:
            self.data = {}

    def tearDown(self, fixture):
        pass

    def __unicode__(self): return "performing {} {}".format(self.method.upper(), self.url)

class NMTestUtilsThen(object):
    def __call__(self, fixture, response, when, test_client):
        fixture.fail("test not implemented")

    def __unicode__(self):
        return "user {} visits {}".format(self.user, self.url)

class ThenSuccess(NMTestUtilsThen):
    def __call__(self, fixture, response, when, test_client):
        if response.status_code != 200:
            fixture.fail("User {} got status code {} instead of a Success when {}".format(
                when.user, response.status_code, when))

class ThenForbidden(NMTestUtilsThen):
    def __call__(self, fixture, response, when, test_client):
        if response.status_code != 403:
            fixture.fail("User {} got status code {} instead of a Forbidden when {}".format(
                when.user, response.status_code, when))

class ThenBadMethod(NMTestUtilsThen):
    def __call__(self, fixture, response, when, test_client):
        if response.status_code != 400:
            fixture.fail("User {} got status code {} instead of a BadMethod when {}".format(
                when.user, response.status_code, when))

class ThenMethodNotAllowed(NMTestUtilsThen):
    def __call__(self, fixture, response, when, test_client):
        if response.status_code != 405:
            fixture.fail("User {} got status code {} instead of a 405 'Method not allowed' when {}".format(
                when.user, response.status_code, when))

class ThenNotFound(NMTestUtilsThen):
    def __call__(self, fixture, response, when, test_client):
        if response.status_code != 404:
            fixture.fail("User {} got status code {} instead of a NotFound when {}".format(
                when.user, response.status_code, when))

class ThenRedirect(NMTestUtilsThen):
    target = None
    def __init__(self, target=None):
        self.target = target
    def __call__(self, fixture, response, when, test_client):
        if response.status_code != 302:
            fixture.fail("User {} got status code {} instead of a Redirect when {}".format(
                when.user, response.status_code, when))
        if self.target and not re.search(self.target, response["Location"]):
            fixture.fail("User {} got redirected to {} which does not match {}".format(
                when.user, response["Location"], self.target))


class NMTestUtilsMixin(object):
    def assertVisit(self, when, then, test_client=None):
        if test_client is None:
            test_client = Client()

        when.setUp(self)

        meth = getattr(test_client, when.method)
        kw = { "data": when.data }
        if when.data_content_type: kw["content_type"] = when.data_content_type
        if when.user:
            with override_settings(TEST_USER=when.user.username):
                response = meth(when.url, **kw)
        else:
            with override_settings(TEST_USER=None):
                response = meth(when.url, **kw)

        try:
            then(self, response, when, test_client)
        finally:
            when.tearDown(self)
