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
        cls.persons.create("r_dd", status=const.STATUS_REMOVED_DD)
        cls.persons.create("am_e_dd", status=const.STATUS_EMERITUS_DD)
        cls.persons.create("am_r_dd", status=const.STATUS_REMOVED_DD)
        cls.persons.create("applicant1", status=const.STATUS_DC)
        cls.processes.create("applicant1", person=cls.persons.applicant1, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am_e_dd)
        cls.persons.create("applicant2", status=const.STATUS_DC)
        cls.processes.create("applicant2", person=cls.persons.applicant2, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am_r_dd)

    def assertPerms(self, pname, perms):
        self.assertCountEqual(self.persons[pname].perms, perms)

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
        self.assertPerms("r_dd", [])
        self.assertPerms("am_e_dd", [])
        self.assertPerms("am_r_dd", [])
        self.assertPerms("fd", ["admin", "am", "dd"])
        self.assertPerms("dam", ["admin", "am", "dd"])


class TestVisitPersonNoProcess(OldProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        cls._add_method(cls._test_perms, "pending", perms={
            "fd dam": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log fd_comments",
            "activeam": "update_keycheck edit_bio edit_ldap view_person_audit_log",
            "pending": "update_keycheck edit_email edit_bio",
            "dd_nu dd_u oldam": "view_person_audit_log update_keycheck",
        })

        cls._add_method(cls._test_perms, "dc", perms={
            "fd dam": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log request_new_status fd_comments",
            "dc": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio edit_ldap view_person_audit_log",
            "dd_nu dd_u oldam": "view_person_audit_log update_keycheck",
        })

        cls._add_method(cls._test_perms, "dc_ga", perms={
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "dc_ga": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu dd_u oldam": "view_person_audit_log update_keycheck",
        })

        cls._add_method(cls._test_perms, "dm", perms={
            "fd dam": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log request_new_status fd_comments",
            "dm": "update_keycheck edit_email edit_bio edit_ldap view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio edit_ldap view_person_audit_log",
            "dd_nu dd_u oldam": "view_person_audit_log update_keycheck",
        })

        cls._add_method(cls._test_perms, "dm_ga", perms={
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "dm_ga": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu dd_u oldam": "view_person_audit_log update_keycheck",
        })

        cls._add_method(cls._test_perms, "dd_nu", perms={
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "dd_nu": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_u oldam": "view_person_audit_log update_keycheck",
        })

        cls._add_method(cls._test_perms, "dd_u", perms={
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "dd_u": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu oldam": "view_person_audit_log update_keycheck",
        })

        cls._add_method(cls._test_perms, "fd", perms={
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "activeam": "update_keycheck edit_bio view_person_audit_log",
            "dd_nu dd_u oldam": "view_person_audit_log update_keycheck",
        })

        cls._add_method(cls._test_perms, "dam", perms={
            "fd dam": "update_keycheck edit_email edit_bio view_person_audit_log request_new_status fd_comments",
            "activeam": "view_person_audit_log update_keycheck edit_bio",
            "dd_nu dd_u oldam": "view_person_audit_log update_keycheck",
        })

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
        perms = ExpectedPerms(perms)
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
        self.proc.patch("dd_nu dd_u oldam activeam fd dam app adv", "+view_person_audit_log +update_keycheck")
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
        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        expected.patch_generic_process_am_approved()
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
        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        expected.patch_generic_process_am_approved()
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
        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        expected.patch_generic_process_am_approved()
        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
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
        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        expected.patch_generic_process_am_approved()
        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
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
        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        expected.patch_generic_process_am_approved()
        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
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
        self.processes.app.advocates.add(self.persons.adv)
        expected.patch_generic_process_has_advocate()
        expected.patch_generic_process_am_approved()
        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_generic_process_final()
        self.assertApplicantPermsFinal(expected)
