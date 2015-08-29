# coding: utf8
"""
Test permissions
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from backend import const
from backend.test_common import *

class PermissionsTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def test_newnm(self):
        """
        newnm works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_newnm")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

    def test_stats(self):
        """
        stats works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_stats")
        class ThenSeesDetails(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenSeesDetails, self).__call__(fixture, response, when, test_client)
                if b"<th>Last log entry</th>" not in response.content:
                    fixture.fail("details not visible by {} when {}".format(when.user, when))
        class ThenDoesNotSeeDetails(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenDoesNotSeeDetails, self).__call__(fixture, response, when, test_client)
                if b"<th>Last log entry</th>" in response.content:
                    fixture.fail("details are visible by {} when {}".format(when.user, when))
        self.assertVisit(WhenView(), ThenDoesNotSeeDetails())
        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenView(user=self.users[u]), ThenDoesNotSeeDetails())
        for u in ("fd", "dam"):
            self.assertVisit(WhenView(user=self.users[u]), ThenSeesDetails())

    def test_stats_latest(self):
        """
        stats/latest works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_stats_latest")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

    def test_findperson(self):
        """
        findperson works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_findperson")
        class ThenSeesDetails(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenSeesDetails, self).__call__(fixture, response, when, test_client)
                if b'id="search_form_submit"' not in response.content:
                    fixture.fail("details not visible by {} when {}".format(when.user, when))
        class ThenDoesNotSeeDetails(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenDoesNotSeeDetails, self).__call__(fixture, response, when, test_client)
                if b'id="search_form_submit"' in response.content:
                    fixture.fail("details are visible by {} when {}".format(when.user, when))
        self.assertVisit(WhenView(), ThenDoesNotSeeDetails())
        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenView(user=self.users[u]), ThenDoesNotSeeDetails())
        for u in ("fd", "dam"):
            self.assertVisit(WhenView(user=self.users[u]), ThenSeesDetails())

        # Test POST
        class WhenPost(NMTestUtilsWhen):
            method = "post"
            url = reverse("public_findperson")
            data = {
                "cn": "Test",
                "email": "test@example.org",
                "status": const.STATUS_DC,
                "username": "test-guest@users.alioth.debian.org",
            }
            def setUp(self, fixture):
                super(WhenPost, self).setUp(fixture)
                bmodels.Person.objects.filter(email="test@example.org").delete()
            def tearDown(self, fixture):
                super(WhenPost, self).tearDown(fixture)
                bmodels.Person.objects.filter(email="test@example.org").delete()
        class ThenCreatesUser(ThenRedirect):
            target = "/public/person/"
            def __call__(self, fixture, response, when, test_client):
                super(ThenCreatesUser, self).__call__(fixture, response, when, test_client)
                if not bmodels.Person.objects.filter(email="test@example.org").exists():
                    fixture.fail("the user has notbeen created by {} when {}".format(when.user, when))

        self.assertVisit(WhenPost(), ThenForbidden())
        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenPost(user=self.users[u]), ThenForbidden())
        for u in ("fd", "dam"):
            self.assertVisit(WhenPost(user=self.users[u]), ThenCreatesUser())

    def test_people(self):
        """
        stats/latest works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("people")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

    def test_process(self):
        """
        process works for all users
        """
        class WhenViewOther(NMTestUtilsWhen):
            def setUp(self, fixture):
                super(WhenViewOther, self).setUp(fixture)
                self.person = bmodels.Person.objects.create_user(cn="Other", email="other@example.org", status=const.STATUS_DC, audit_skip=True)
                self.process = bmodels.Process.objects.create(person=self.person,
                                               applying_as=const.STATUS_DC,
                                               applying_for=const.STATUS_DD_NU,
                                               progress=const.PROGRESS_APP_OK,
                                               is_active=True)
                self.url = reverse("public_process", kwargs={ "key": self.process.lookup_key })

            def tearDown(self, fixture):
                super(WhenViewOther, self).setUp(fixture)
                self.process.delete()
                self.person.delete()

        self.assertVisit(WhenViewOther(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenViewOther(user=u), ThenSuccess())

        # TODO: test visiting various combinations (applicant, dd, advocate and
        #       so on) and check what info are present in the page
        # TODO: test submission of info changes

    def test_progress(self):
        """
        progress works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_progress", kwargs={ "progress": "app_ok" })
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

# TODO: url(r'^newnm/resend_challenge/(?P<key>[^/]+)$', 'newnm_resend_challenge', name="public_newnm_resend_challenge"),
# TODO: url(r'^newnm/confirm/(?P<nonce>[^/]+)$', 'newnm_confirm', name="public_newnm_confirm"),

# TODO: Compatibility
#    url(r'^whoisam$', 'managers', name="public_whoisam"),
#    url(r'^nmstatus/(?P<key>[^/]+)$', 'process', name="public_nmstatus"),
#    url(r'^nmlist$', 'processes', name="public_nmlist"),

class ProcessesTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(ProcessesTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.am_am = bmodels.AM.objects.create(person=self.am)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_APP_RCVD)

    def test_processes(self):
        """
        processes works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("processes")
        class ThenSeesFDComments(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenSeesFDComments, self).__call__(fixture, response, when, test_client)
                if b"FD_COMMENTS" not in response.content:
                    fixture.fail("FD comments not visible by {} when {}".format(when.user, when))
        class ThenDoesNotSeeFDComments(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenDoesNotSeeFDComments, self).__call__(fixture, response, when, test_client)
                if b"FD_COMMENTS" in response.content:
                    fixture.fail("FD comments are visible by {} when {}".format(when.user, when))

        self.assertVisit(WhenView(), ThenDoesNotSeeFDComments())
        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenView(user=self.users[u]), ThenDoesNotSeeFDComments())
        for u in ("fd", "dam"):
            self.assertVisit(WhenView(user=self.users[u]), ThenSeesFDComments())


class ManagersTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(ManagersTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.am_am = bmodels.AM.objects.create(person=self.am)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_APP_RCVD)

    def test_managers(self):
        """
        managers works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("managers")
        class ThenSeesDetails(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenSeesDetails, self).__call__(fixture, response, when, test_client)
                if b"<th>Hold</th>" not in response.content:
                    fixture.fail("details not visible by {} when {}".format(when.user, when))
        class ThenDoesNotSeeDetails(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenDoesNotSeeDetails, self).__call__(fixture, response, when, test_client)
                if b"<th>Hold</th>" in response.content:
                    fixture.fail("details are visible by {} when {}".format(when.user, when))
        self.assertVisit(WhenView(), ThenDoesNotSeeDetails())
        ams = ("am", "fd", "dam")
        for u in self.users.viewkeys() - frozenset(ams):
            self.assertVisit(WhenView(user=self.users[u]), ThenDoesNotSeeDetails())
        for u in ams:
            self.assertVisit(WhenView(user=self.users[u]), ThenSeesDetails())
