# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from . import models as bmodels
from . import const
from django.core.urlresolvers import reverse
from django.test import Client
from django.utils.timezone import now
import datetime
import re

class NMBasicFixtureMixin(object):
    def setUp(self):
        super(NMBasicFixtureMixin, self).setUp()

        self.users = {}

        def _make_user(tag, status, alioth=False, **kw):
            if alioth:
                remote_user = "NM::DEBIAN:{}-guest@users.alioth.debian.org".format(tag)
                uid = tag + "-guest"
            else:
                remote_user = "NM::DEBIAN:{}".format(tag)
                uid = tag
            res = bmodels.Person.objects.create(cn=tag.capitalize(),
                                        uid=uid,
                                        email=tag + "@example.org",
                                        status=status,
                                        **kw)
            res.remote_user = remote_user
            self.users[tag] = res
            return res

        # anonymous
        # pending account
        _make_user("pending", const.STATUS_MM, expires=now() + datetime.timedelta(days=1), pending="12345", alioth=True)
        # non-dd non-applicant
        _make_user("bystander", const.STATUS_MM, alioth=True)
        # non-dd applicant
        applicant = _make_user("applicant", const.STATUS_MM_GA, alioth=True, fd_comment="FD_COMMENTS")
        # dd
        _make_user("dd", const.STATUS_DD_NU)
        # dd advocate,
        adv = _make_user("adv", const.STATUS_DD_NU)
        # dd advocate of a past process,
        adv_past = _make_user("adv_past", const.STATUS_DD_NU)
        # am of applicant
        am =_make_user("am", const.STATUS_DD_NU)
        am_am = bmodels.AM.objects.create(person=am, slots=1)
        proc = bmodels.Process.objects.create(person=applicant,
                                       applying_as=const.STATUS_MM_GA,
                                       applying_for=const.STATUS_DD_NU,
                                       progress=const.PROGRESS_AM,
                                       manager=am_am,
                                       is_active=True)
        proc.advocates.add(adv)
        # am not of applicant
        am_other = _make_user("am_other", const.STATUS_DD_NU)
        bmodels.AM.objects.create(person=am_other, slots=1)
        # am of a past process
        am_past = _make_user("am_past", const.STATUS_DD_NU)
        am_am_past = bmodels.AM.objects.create(person=am_past, slots=1)
        proc = bmodels.Process.objects.create(person=applicant,
                                       applying_as=const.STATUS_MM,
                                       applying_for=const.STATUS_MM_GA,
                                       progress=const.PROGRESS_DONE,
                                       manager=am_am_past,
                                       is_active=False)
        proc.advocates.add(adv_past)
        # fd
        fd = _make_user("fd", const.STATUS_DD_NU)
        bmodels.AM.objects.create(person=fd, is_fd=True)
        # dam
        dam = _make_user("dam", const.STATUS_DD_NU)
        bmodels.AM.objects.create(person=dam, is_fd=True, is_dam=True)


# Inspired from http://blog.liw.fi/posts/yarn/

class NMTestUtilsWhen(object):
    method = "get"
    url = None
    user = None
    data = None # Optional dict with GET or POST data

    def __init__(self, method=None, url=None, user=None, data=None, **kw):
        """
        Set up the parameters used by assertVisit to make a request
        """
        # Override the class defaults with the constructor arguments
        if method is not None: self.method = method
        if self.url is None or url is not None: self.url = url
        if self.user is None or user is not None: self.user = user
        if self.data is None or data is not None: self.data = data
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

class ThenNotFound(NMTestUtilsThen):
    def __call__(self, fixture, response, when, test_client):
        if response.status_code != 404:
            fixture.fail("User {} got status code {} instead of a NotFound when {}".format(
                when.user, response.status_code, when))

class NMTestUtilsMixin(object):
    def assertVisit(self, when, then, test_client=None):
        if test_client is None:
            test_client = Client()

        when.setUp(self)

        meth = getattr(test_client, when.method)
        if when.user is None:
            response = meth(when.url, data=when.data)
        else:
            response = meth(when.url, data=when.data, REMOTE_USER=when.user.remote_user)

        try:
            then(self, response, when, test_client)
        finally:
            when.tearDown(self)
