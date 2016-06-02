# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from backend import const
from backend import models as bmodels
from backend.unittest import BaseFixtureMixin, PersonFixtureMixin, ExpectedPerms, NamedObjects, OldProcessFixtureMixin

class TestPersonPermissions(OldProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPersonPermissions, cls).setUpClass()
        cls.persons.create("applicant", status=const.STATUS_DC)
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.processes.create("applicant", person=cls.persons.applicant, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am)
        cls.persons.create("e_dd", status=const.STATUS_EMERITUS_DD)
        cls.persons.create("e_dm", status=const.STATUS_EMERITUS_DM)
        cls.persons.create("r_dd", status=const.STATUS_REMOVED_DD)
        cls.persons.create("r_dm", status=const.STATUS_REMOVED_DM)
        cls.persons.create("am_e_dd", status=const.STATUS_EMERITUS_DD)
        cls.persons.create("am_r_dd", status=const.STATUS_REMOVED_DD)
        cls.persons.create("applicant1", status=const.STATUS_DC)
        cls.processes.create("applicant1", person=cls.persons.applicant1, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am_e_dd)
        cls.persons.create("applicant2", status=const.STATUS_DC)
        cls.processes.create("applicant2", person=cls.persons.applicant2, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am_r_dd)

    def assertPerms(self, pname, perms):
        self.assertItemsEqual(self.persons[pname].perms, perms)

    def test_person(self):
        self.assertPerms("pending", [])
        self.assertPerms("dc", [])
        self.assertPerms("dc_ga", [])
        self.assertPerms("dm", [])
        self.assertPerms("dm_ga", [])
        self.assertPerms("applicant", [])
        self.assertPerms("dd_nu", ["am_candidate", "dd"])
        self.assertPerms("dd_u", ["am_candidate", "dd"])
        self.assertPerms("am", ["am", "dd"])
        self.assertPerms("e_dd", [])
        self.assertPerms("e_dm", [])
        self.assertPerms("r_dd", [])
        self.assertPerms("r_dm", [])
        self.assertPerms("am_e_dd", [])
        self.assertPerms("am_r_dd", [])
        self.assertPerms("fd", ["admin", "am", "dd"])
        self.assertPerms("dam", ["admin", "am", "dd"])


class TestVisitPersonMixin(object):
    def assertPermsEqual(self, action, perms_type, wanted, got):
        got = set(got)
        wanted = set(wanted)
        if got == wanted: return
        extra = got - wanted
        missing = wanted - got
        msg = []
        if missing: msg.append("misses {} {}".format(perms_type, ", ".join(sorted(missing))))
        if extra: msg.append("has extra {} {}".format(perms_type, ", ".join(sorted(extra))))
        self.fail(action + " " + " and ".join(msg))


class TestVisitPersonNoProcess(OldProcessFixtureMixin, TestVisitPersonMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        cls._add_method(cls._test_perms, "pending", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_bio edit_ldap view_person_audit_log",
            "pending": "view_person_audit_log update_keycheck edit_bio",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dc", perms=ExpectedPerms({
            "fd dam dc": "update_keycheck edit_bio edit_ldap view_person_audit_log request_new_status",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, {
            "fd dam dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "dm dm_ga": "dc_ga",
        }))

        cls._add_method(cls._test_perms, "dc_ga", perms=ExpectedPerms({
            "fd dam dc_ga": "update_keycheck edit_bio view_person_audit_log request_new_status",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, {
            "fd dam dd_nu dd_u": "dm_ga dd_u dd_nu",
        }))

        cls._add_method(cls._test_perms, "dm", perms=ExpectedPerms({
            "fd dam dm": "update_keycheck edit_bio edit_ldap view_person_audit_log request_new_status",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam dd_nu dd_u": "dm_ga dd_u dd_nu",
            "dm dm_ga": "dm_ga",
        }))

        cls._add_method(cls._test_perms, "dm_ga", perms=ExpectedPerms({
            "fd dam dm_ga": "update_keycheck edit_bio view_person_audit_log request_new_status",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam dd_nu dd_u": "dd_u dd_nu",
        }))

        cls._add_method(cls._test_perms, "dd_nu", perms=ExpectedPerms({
            "fd dam dd_nu": "update_keycheck edit_bio view_person_audit_log request_new_status",
            "dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dd_u", perms=ExpectedPerms({
            "fd dam dd_u": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "fd", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_bio view_person_audit_log request_new_status",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dam", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

    def _test_perms(self, visited, perms):
        other_visitors = set(self.persons.keys())
        other_visitors.add(None)
        for visitor, expected_perms in perms.perms.items():
            other_visitors.discard(visitor)
            visit_perms = self.persons[visited].permissions_of(self.persons[visitor])
            self.assertPermsEqual(
                "{} visiting {}".format(visitor, visited), "permissions",
                expected_perms, visit_perms)
        for visitor in other_visitors:
            visit_perms = self.persons[visited].permissions_of(self.persons[visitor] if visitor else None)
            self.assertPermsEqual(
                "{} visiting {}".format(visitor, visited), "permissions",
                [], visit_perms)

        other_visitors = set(self.persons.keys())
        other_visitors.add(None)
        for visitor, expected_targets in perms.advs.items():
            other_visitors.discard(visitor)
            visit_perms = self.persons[visited].permissions_of(self.persons[visitor])
            self.assertPermsEqual(
                "{} advocating {}".format(visitor, visited), "target",
                    expected_targets, visit_perms.advocate_targets)
        for visitor in other_visitors:
            visit_perms = self.persons[visited].permissions_of(self.persons[visitor] if visitor else None)
            self.assertPermsEqual(
                "{} advocating {}".format(visitor, visited), "target",
                [], visit_perms.advocate_targets)


class TestVisitApplicant(OldProcessFixtureMixin, TestVisitPersonMixin, TestCase):
    def assertApplicantPerms(self, perms):
        other_visitors = set(self.persons.keys())
        other_visitors.add(None)
        for visitor, expected_perms in perms.perms.items():
            other_visitors.discard(visitor)
            visit_perms = self.processes.app.permissions_of(self.persons[visitor])
            self.assertPermsEqual(
                "{} visiting app process".format(visitor), "permissions",
                expected_perms, visit_perms)
        for visitor in other_visitors:
            visit_perms = self.processes.app.permissions_of(self.persons[visitor] if visitor else None)
            self.assertPermsEqual(
                "{} visiting app process".format(visitor), "permissions",
                [], visit_perms)

        other_visitors = set(self.persons.keys())
        other_visitors.add(None)
        for visitor, expected_targets in perms.advs.items():
            other_visitors.discard(visitor)
            visit_perms = self.processes.app.permissions_of(self.persons[visitor])
            self.assertPermsEqual(
                "{} advocating app".format(visitor), "target",
                expected_targets, visit_perms.advocate_targets)
        for visitor in other_visitors:
            visit_perms = self.processes.app.permissions_of(self.persons[visitor] if visitor else None)
            self.assertPermsEqual(
                "{} advocating app".format(visitor), "target",
                [], visit_perms.advocate_targets)

    def assertApplicantPermsInitialProcess(self, expected):
        for p in (const.PROGRESS_APP_NEW, const.PROGRESS_APP_RCVD, const.PROGRESS_APP_HOLD, const.PROGRESS_ADV_RCVD, const.PROGRESS_POLL_SENT):
            self.processes.app.progress = p
            self.processes.app.save()
            self.assertApplicantPerms(expected)

    def assertApplicantPermsHasAdvocate(self, expected):
        for p in (const.PROGRESS_APP_OK,):
            self.processes.app.progress = p
            self.processes.app.save()
            self.assertApplicantPerms(expected)

    def assertApplicantPermsAMApproved(self, expected):
        for p in (const.PROGRESS_AM_OK, const.PROGRESS_FD_HOLD, const.PROGRESS_FD_OK, const.PROGRESS_DAM_HOLD, const.PROGRESS_DAM_OK):
            self.processes.app.progress = p
            self.processes.app.save()
            self.assertApplicantPerms(expected)

    def assertApplicantPermsFinal(self, expected):
        for p in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED):
            self.processes.app.progress = p
            self.processes.app.is_active = False
            self.processes.app.save()
            self.assertApplicantPerms(expected)

    def test_dc_dcga_adv_dm(self):
        """
        Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("adv", status=const.STATUS_DM)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DC_GA, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "adv dm dm_ga": "dc_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "view_mbox")
        expected.patch_advs("adv", "-dc_ga")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.patch_advs("fd dam dd_nu dd_u", "-dc_ga")
        expected.patch_advs("dm dm_ga", "-dc_ga")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-edit_ldap")
        expected.patch_advs("fd dam dd_nu dd_u", "-dm +dm_ga")
        self.assertApplicantPermsFinal(expected)

    def test_dc_dcga_adv_dd(self):
        """
        Test all visit combinations for an applicant from dc to dc_ga, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DC_GA, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "dm dm_ga": "dc_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dc_ga")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.patch_advs("fd dam dd_nu dd_u", "-dc_ga")
        expected.patch_advs("dm dm_ga", "-dc_ga")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-edit_ldap")
        expected.patch_advs("fd dam adv dd_nu dd_u", "-dm +dm_ga")
        self.assertApplicantPermsFinal(expected)

    def test_dm_dmga_adv_self(self):
        """
        Test all visit combinations for an applicant from dm to dm_ga, with self as advocate
        """
        self.persons.create("app", status=const.STATUS_DM)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM_GA, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam dd_nu dd_u": "dm_ga dd_u dd_nu",
            "app dm dm_ga": "dm_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.app)
        expected.patch_advs("app", "-dm_ga")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.patch_advs("fd dam dd_nu dd_u", "-dm_ga")
        expected.patch_advs("dm dm_ga", "-dm_ga")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-edit_ldap")
        self.assertApplicantPermsFinal(expected)

    def test_dm_dmga_adv_dd(self):
        """
        Test all visit combinations for an applicant from dm to dm_ga, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DM)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM_GA, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
            "app dm dm_ga": "dm_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dm_ga")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.set_perms("adv", "view_person_audit_log update_keycheck view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dm_ga")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-edit_ldap")
        self.assertApplicantPermsFinal(expected)

    def test_dc_dm(self):
        """
        Test all visit combinations for an applicant from dc to dm, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "dm dm_ga": "dc_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dm")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.set_perms("adv", "view_person_audit_log update_keycheck view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dm")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_ldap +edit_bio")
        expected.patch_advs("fd dam dd_nu dd_u app adv dm dm_ga", "-dc_ga +dm_ga")
        self.assertApplicantPermsFinal(expected)

    def test_dc_ddnu(self):
        """
        Test all visit combinations for an applicant from dc to dd_nu, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "dm dm_ga": "dc_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dd_nu -dd_u")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.set_perms("adv", "view_person_audit_log update_keycheck view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-edit_ldap")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dc_ga -dm")
        self.assertApplicantPermsFinal(expected)

    def test_dcga_ddnu(self):
        """
        Test all visit combinations for an applicant from dc_ga to dd_nu, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC_GA)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio view_person_audit_log view_mbox request_new_status",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dd_nu -dd_u")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.set_perms("adv", "view_person_audit_log update_keycheck view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dm_ga")
        self.assertApplicantPermsFinal(expected)

    def test_dc_ddu(self):
        """
        Test all visit combinations for an applicant from dc to dd_u, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "dm dm_ga": "dc_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dd_nu -dd_u")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.set_perms("adv", "view_person_audit_log update_keycheck view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-edit_ldap -request_new_status")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dc_ga -dm")
        self.assertApplicantPermsFinal(expected)

    def test_dcga_ddu(self):
        """
        Test all visit combinations for an applicant from dc_ga to dd_u, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC_GA)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio view_person_audit_log view_mbox request_new_status",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dd_nu -dd_u")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.set_perms("adv", "view_person_audit_log update_keycheck view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-request_new_status")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dm_ga")
        self.assertApplicantPermsFinal(expected)

    def test_dm_ddu(self):
        """
        Test all visit combinations for an applicant from dm to dd_u, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DM)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
            "dm dm_ga app": "dm_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dd_nu -dd_u")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap -edit_bio")
        expected.set_perms("adv", "view_person_audit_log update_keycheck view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-edit_ldap -request_new_status")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dm_ga")
        self.assertApplicantPermsFinal(expected)

    def test_dmga_ddu(self):
        """
        Test all visit combinations for an applicant from dm to dd_u, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DM_GA)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio view_person_audit_log view_mbox",
            "adv dd_nu dd_u": "view_person_audit_log update_keycheck",
        }, advs={
            "fd dam adv dd_nu dd_u": "dd_u dd_nu",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck view_person_audit_log view_mbox")
        expected.patch_advs("adv", "-dd_nu -dd_u")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_bio")
        expected.set_perms("adv", "view_person_audit_log update_keycheck view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("app", "+edit_bio")
        expected.patch_perms("fd dam app", "-request_new_status")
        self.assertApplicantPermsFinal(expected)
