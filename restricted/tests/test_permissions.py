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
