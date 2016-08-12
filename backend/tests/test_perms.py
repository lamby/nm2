# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from backend import const
from backend import models as bmodels
from backend.unittest import BaseFixtureMixin, PersonFixtureMixin, ExpectedPerms, ExpectedSets, OldProcessFixtureMixin

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


class TestVisitPersonNoProcess(OldProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        cls._add_method(cls._test_perms, "pending", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log fd_comments",
            "activeam": "update_keycheck edit_bio edit_ldap view_person_audit_log",
            "pending": "update_keycheck edit_email edit_bio",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dc", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log request_new_status fd_comments",
            "dc": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio edit_ldap view_person_audit_log",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dc_ga", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "dc_ga": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dm", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log request_new_status fd_comments",
            "dm": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio edit_ldap view_person_audit_log",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dm_ga", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "dm_ga": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dd_nu", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "dd_nu": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dd_u", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log fd_comments",
            "dd_u": "update_keycheck edit_email edit_bio view_person_audit_log",
            "activeam dd_u": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "fd", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

        cls._add_method(cls._test_perms, "dam", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log fd_comments",
            "activeam": "view_person_audit_log update_keycheck edit_bio",
            "dd_nu dd_u": "view_person_audit_log update_keycheck",
        }))

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


class ProcExpected(object):
    def __init__(self, testcase):
        self.proc = ExpectedSets(testcase, "{visitor} visiting app's process", "{problem} permissions {mismatch}")

    def patch_generic_process_started(self):
        self.proc.patch("dd_nu dd_u activeam fd dam app adv", "+view_person_audit_log +update_keycheck")
        self.proc.patch("fd dam app", "+view_mbox +request_new_status +edit_bio +edit_email")
        self.proc.patch("fd dam", "+fd_comments")
        self.proc.patch("activeam", "+view_mbox +edit_bio")

    def patch_generic_process_has_advocate(self):
        self.proc.patch("adv", "+view_mbox +update_keycheck +view_person_audit_log")

    def patch_generic_process_am_approved(self):
        self.proc.patch("activeam app", "-edit_ldap -edit_bio")

    def patch_generic_process_final(self):
        self.proc.patch("app activeam", "+edit_bio")
        self.proc.patch("fd dam app", "-edit_ldap")


class TestVisitApplicant(OldProcessFixtureMixin, TestCase):
    def assertApplicantPerms(self, perms):
        perms.proc.assertMatches(self.processes.app)

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

    def test_dc_ddnu(self):
        """
        Test all visit combinations for an applicant from dc to dd_nu, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_APP_RCVD)

        expected = ProcExpected(self)
        expected.patch_generic_process_started()
        expected.proc.patch("activeam fd dam app", "+edit_ldap")
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_generic_process_am_approved()
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
        self.assertApplicantPermsFinal(expected)

    def test_dcga_ddnu(self):
        """
        Test all visit combinations for an applicant from dc_ga to dd_nu, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC_GA)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_APP_RCVD)

        expected = ProcExpected(self)
        expected.patch_generic_process_started()
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_generic_process_am_approved()
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
        self.assertApplicantPermsFinal(expected)

    def test_dc_ddu(self):
        """
        Test all visit combinations for an applicant from dc to dd_u, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)

        expected = ProcExpected(self)
        expected.patch_generic_process_started()
        expected.proc.patch("activeam fd dam app", "+edit_ldap")
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_generic_process_am_approved()
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
        expected.proc.patch("fd dam app", "-request_new_status")
        self.assertApplicantPermsFinal(expected)

    def test_dcga_ddu(self):
        """
        Test all visit combinations for an applicant from dc_ga to dd_u, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC_GA)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)

        expected = ProcExpected(self)
        expected.patch_generic_process_started()
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_generic_process_am_approved()
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
        expected.proc.patch("fd dam app", "-request_new_status")
        self.assertApplicantPermsFinal(expected)

    def test_dm_ddu(self):
        """
        Test all visit combinations for an applicant from dm to dd_u, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DM)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)

        expected = ProcExpected(self)
        expected.patch_generic_process_started()
        expected.proc.patch("activeam fd dam app", "+edit_ldap")
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_generic_process_am_approved()
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
        expected.proc.patch("fd dam app", "-request_new_status")
        self.assertApplicantPermsFinal(expected)

    def test_dmga_ddu(self):
        """
        Test all visit combinations for an applicant from dm to dd_u, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DM_GA)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)

        expected = ProcExpected(self)
        expected.patch_generic_process_started()
        expected.proc.patch("fd dam app", "-request_new_status")
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_generic_process_am_approved()
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
        self.assertApplicantPermsFinal(expected)
