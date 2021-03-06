"""
Test permissions
"""
from django.test import TestCase
from backend import const
from backend.test_common import *
from backend.unittest import PersonFixtureMixin, PageElements

class TestStatsPermissions(PersonFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestStatsPermissions, cls).setUpClass()
        cls.elements = PageElements()
        cls.elements.add_id("head_activity")
        cls.elements.add_id("head_lastlog")
        cls.elements.add_class("col_activity")
        cls.elements.add_class("col_lastlog")
        cls.processes.create("app", person=cls.persons.dm, applying_for=const.STATUS_DM_GA)

    @classmethod
    def __add_extra_tests__(cls):
        # Everyone can see stats
        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "oldam"):
            cls._add_method(cls._test_get_success, visitor, elements=())

        # But only AMs can see process-specific information
        for visitor in ("activeam", "fd", "dam"):
            cls._add_method(cls._test_get_success, visitor, elements=("head_activity", "head_lastlog", "col_activity", "col_lastlog"))

    def _test_get_success(self, visitor, elements):
        client = self.make_test_client(visitor)
        response = client.get(reverse("public_stats"))
        self.assertEqual(response.status_code, 200)
        self.assertContainsElements(response, self.elements, *elements)


class PermissionsTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def test_newnm(self):
        """
        newnm works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_newnm")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.values():
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
        for u in self.users.keys() - frozenset(("fd", "dam")):
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
        for u in self.users.keys() - frozenset(("fd", "dam")):
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
        for u in self.users.values():
            self.assertVisit(WhenView(user=u), ThenSuccess())

# TODO: url(r'^newnm/resend_challenge/(?P<key>[^/]+)$', 'newnm_resend_challenge', name="public_newnm_resend_challenge"),
# TODO: url(r'^newnm/confirm/(?P<nonce>[^/]+)$', 'newnm_confirm', name="public_newnm_confirm"),


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
        for u in self.users.keys() - frozenset(ams):
            self.assertVisit(WhenView(user=self.users[u]), ThenDoesNotSeeDetails())
        for u in ams:
            self.assertVisit(WhenView(user=self.users[u]), ThenSeesDetails())
