# coding: utf-8




from django.test import TestCase, TransactionTestCase
from backend import const
from backend.test_common import *
from backend.unittest import PersonFixtureMixin, OldProcessFixtureMixin, PageElements
import backend.models as bmodels

class PermissionsTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(PermissionsTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_AM, advocates=[self.adv], manager=self.am)

    def test_ammain(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_ammain")
        allowed = frozenset(("am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_impersonate(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("impersonate", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenRedirect("^/$"))

    def test_db_export(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_db_export")
        allowed = frozenset(("dd_u", "dd_nu", "adv", "am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_db_export_full(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_db_export") + "?full"
        allowed = frozenset(("fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_mail_archive(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("download_mail_archive", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("app", "adv", "am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        # Success is a 404 because we did not create the file on disk
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenNotFound())

    def test_display_mail_archive(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("display_mail_archive", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("app", "adv", "am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        # Success is a 404 because we did not create the file on disk
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenNotFound())

    def test_minechangelogs(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_minechangelogs", kwargs={ "key": self.users["app"].lookup_key })
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys():
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())


class TestAMProfile(PersonFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestAMProfile, cls).setUpClass()
        cls.elements = PageElements()
        cls.elements.add_id("id_slots")
        cls.elements.add_id("id_is_am")
        cls.elements.add_id("id_is_fd")
        cls.elements.add_id("id_is_dam")
        cls.elements.add_id("id_fd_comment")
        cls.elements.add_id("fd_comments")

    @classmethod
    def __add_extra_tests__(cls):
        # Some users cannot access amprofile at all
        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r"):
            for visited in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "activeam", "oldam", "fd", "dam"):
                cls._add_method(cls._test_get_fail, visitor, visited)
                cls._add_method(cls._test_post_fail, visitor, visited)

        # Some users have no amprofile
        for visitor in ("activeam", "oldam", "fd", "dam"):
            for visited in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r"):
                cls._add_method(cls._test_get_fail, visitor, visited)
                cls._add_method(cls._test_post_fail, visitor, visited)

        # AMs / former AMs can only access self
        for visitor in ("activeam", "oldam"):
            for visited in ("activeam", "oldam", "fd", "dam"):
                if visitor == visited:
                    cls._add_method(cls._test_get_success, visitor, visited, elements=("id_slots", "id_is_am"))
                    cls._add_method(cls._test_post_success, visitor, visited, edited=("id_slots", "id_is_am"))
                else:
                    cls._add_method(cls._test_get_fail, visitor, visited)
                    cls._add_method(cls._test_post_fail, visitor, visited)

        # FD sees everything of everyone except the is_dam checkbox
        for visited in ("activeam", "oldam", "fd", "dam"):
            cls._add_method(cls._test_get_success, "fd", visited, elements=("id_slots", "id_is_am", "id_is_fd", "id_fd_comment", "fd_comments"))
            cls._add_method(cls._test_post_success, "fd", visited, edited=("id_slots", "id_is_am", "id_is_fd", "id_fd_comment", "fd_comments"))

        # DAM sees everything of everyone
        for visited in ("activeam", "oldam", "fd", "dam"):
            cls._add_method(cls._test_get_success, "dam", visited, elements=("id_slots", "id_is_am", "id_is_fd", "id_is_dam", "id_fd_comment", "fd_comments"))
            cls._add_method(cls._test_post_success, "dam", visited, edited=("id_slots", "id_is_am", "id_is_fd", "id_is_dam", "id_fd_comment", "fd_comments"))

    def _test_get_success(self, visitor, visited, elements):
        client = self.make_test_client(visitor)
        response = client.get(reverse("restricted_amprofile", args=[self.persons[visited].lookup_key]))
        self.assertEqual(response.status_code, 200)
        self.assertContainsElements(response, self.elements, *elements)

    def _test_get_fail(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.get(reverse("restricted_amprofile", args=[self.persons[visited].lookup_key]))
        self.assertPermissionDenied(response)

    def _test_post_success(self, visitor, visited, edited):
        client = self.make_test_client(visitor)
        visited = self.persons[visited]
        response = client.post(reverse("restricted_amprofile", args=[self.persons[visited].lookup_key]), data={
            "slots": visited.am.slots + 1,
            "is_am": not visited.am.is_am,
            "is_fd": not visited.am.is_fd,
            "is_dam": not visited.am.is_dam,
            "fd_comment": "new fd comment",
        })
        self.assertEqual(response.status_code, 200)
        newvisited = bmodels.Person.objects.get(pk=visited.pk)
        if "id_slots" in edited: self.assertEqual(newvisited.am.slots, visited.am.slots + 1)
        if "id_is_am" in edited: self.assertEqual(newvisited.am.is_am, not visited.am.is_am)
        if "id_is_fd" in edited: self.assertEqual(newvisited.am.is_fd, not visited.am.is_fd)
        if "id_is_dam" in edited: self.assertEqual(newvisited.am.is_dam, not visited.am.is_dam)
        if "fd_comments" in edited: self.assertEqual(newvisited.am.fd_comment, "new fd comment")

    def _test_post_fail(self, visitor, visited):
        client = self.make_test_client(visitor)
        visited = self.persons[visited]
        try:
            orig_am = bmodels.AM.objects.get(person__pk=visited.pk)
        except bmodels.AM.DoesNotExist:
            orig_am = None
        response = client.post(reverse("restricted_amprofile", args=[self.persons[visited].lookup_key]), data={
            "slots": 5,
            "is_am": True,
            "is_fd": True,
            "is_dam": True,
            "fd_comment": "new fd comment",
        })
        self.assertPermissionDenied(response)
        try:
            am = bmodels.AM.objects.get(person__pk=visited.pk)
        except bmodels.AM.DoesNotExist:
            am = None
        if orig_am is None:
            self.assertIsNone(am)
        if am is None:
            return
        self.assertEqual(visited.am.slots, am.slots)
        self.assertEqual(visited.am.is_am, am.is_am)
        self.assertEqual(visited.am.is_fd, am.is_fd)
        self.assertEqual(visited.am.is_dam, am.is_dam)
        self.assertEqual(visited.am.fd_comment, am.fd_comment)


class AssignAMTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(AssignAMTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.am_am = bmodels.AM.objects.create(person=self.am, slots=1, is_am=True)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_APP_OK, advocates=[self.adv])

    def test_assign_am(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("assign_am", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

        # TODO: post

class AssignAMAgainTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(AssignAMAgainTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_AM, manager=self.am, advocates=[self.adv])

    def test_assign_am(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("assign_am", kwargs={ "key": self.users["app"].lookup_key })
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.keys():
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())

        # TODO: post

