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
from backend import models as bmodels
from backend.unittest import BaseFixtureMixin, PersonFixtureMixin

class TestPersonPermissions(PersonFixtureMixin, TestCase):
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


class PatchExact(object):
    def __init__(self, text):
        if text:
            self.items = set(text.split())
        else:
            self.items = set()

    def apply(self, cur):
        if self.items: return set(self.items)
        return None


class PatchDiff(object):
    def __init__(self, text):
        self.added = set()
        self.removed = set()
        for change in text.split():
            if change[0] == "+":
                self.added.add(change[1:])
            elif change[0] == "-":
                self.removed.add(change[1:])
            else:
                raise RuntimeError("Changes {} contain {} that is nether an add nor a remove".format(changes, change))

    def apply(self, cur):
        if cur is None:
            cur = set(self.added)
        else:
            cur = (cur - self.removed) | self.added
        if not cur: return None
        return cur


class ExpectedPerms(object):
    def __init__(self, perms={}, advs={}):
        self.perms = {}
        for visitors, expected_perms in perms.items():
            for visitor in visitors.split():
                self.perms[visitor] = set(expected_perms.split())

        self.advs = {}
        for visitors, expected_targets in advs.items():
            for visitor in visitors.split():
                self.advs[visitor] = set(expected_targets.split())

    def _apply_diff(self, d, diff):
        for visitors, change in diff.items():
            for visitor in visitors.split():
                cur = change.apply(d.get(visitor, None))
                if not cur:
                    d.pop(visitor, None)
                else:
                    d[visitor] = cur

    def update_perms(self, diff):
        self._apply_diff(self.perms, diff)

    def set_perms(self, visitors, text):
        self.update_perms({ visitors: PatchExact(text) })

    def patch_perms(self, visitors, text):
        self.update_perms({ visitors: PatchDiff(text) })

    def update_advs(self, diff):
        self._apply_diff(self.advs, diff)

    def set_advs(self, visitors, text):
        self.update_advs({ visitors: PatchExact(text) })

    def patch_advs(self, visitors, text):
        self.update_advs({ visitors: PatchDiff(text) })


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

    def _test_perms(self, visited, perms):
        other_visitors = set(self.persons.keys())
        other_visitors.add(None)
        for visitor, expected_perms in perms.perms.items():
            other_visitors.discard(visitor)
            vperms = self.persons[visited].permissions_of(self.persons[visitor])
            self.assertPermsEqual(
                "{} visiting {}".format(visitor, visited), "permissions",
                expected_perms, vperms.perms)
        for visitor in other_visitors:
            vperms = self.persons[visited].permissions_of(self.persons[visitor] if visitor else None)
            self.assertPermsEqual(
                "{} visiting {}".format(visitor, visited), "permissions",
                [], vperms.perms)

        other_visitors = set(self.persons.keys())
        other_visitors.add(None)
        for visitor, expected_targets in perms.advs.items():
            other_visitors.discard(visitor)
            vperms = self.persons[visited].permissions_of(self.persons[visitor])
            self.assertPermsEqual(
                "{} advocating {}".format(visitor, visited), "target",
                    expected_targets, vperms.advocate_targets)
        for visitor in other_visitors:
            vperms = self.persons[visited].permissions_of(self.persons[visitor] if visitor else None)
            self.assertPermsEqual(
                "{} advocating {}".format(visitor, visited), "target",
                [], vperms.advocate_targets)


class TestVisitPersonNoProcess(PersonFixtureMixin, TestVisitPersonMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        cls._add_method(cls._test_perms, "pending", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements",
            "pending dd_nu dd_u": "view_person_audit_log",
        }))

        cls._add_method(cls._test_perms, "dc", perms=ExpectedPerms({
            "fd dam dc": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements",
            "dd_nu dd_u": "view_person_audit_log",
        }, {
            "fd dam dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "dm dm_ga": "dc_ga",
        }))

        cls._add_method(cls._test_perms, "dc_ga", perms=ExpectedPerms({
            "fd dam dc_ga": "update_keycheck edit_bio view_person_audit_log see_agreements",
            "dd_nu dd_u": "view_person_audit_log",
        }, {
            "fd dam dd_nu dd_u": "dm_ga dd_u dd_nu",
        }))

        cls._add_method(cls._test_perms, "dm", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements",
            "dm": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements",
            "dd_nu dd_u": "view_person_audit_log",
        }, advs={
            "fd dam dd_nu dd_u": "dm_ga dd_u dd_nu",
            "dm dm_ga": "dm_ga",
        }))

        cls._add_method(cls._test_perms, "dm_ga", perms=ExpectedPerms({
            "fd dam dm_ga": "update_keycheck edit_bio view_person_audit_log see_agreements",
            "dd_nu dd_u": "view_person_audit_log",
        }, advs={
            "fd dam dd_nu dd_u": "dd_u dd_nu",
        }))

        cls._add_method(cls._test_perms, "dd_nu", perms=ExpectedPerms({
            "fd dam dd_nu": "update_keycheck edit_bio view_person_audit_log see_agreements",
            "dd_u": "view_person_audit_log",
        }))

        cls._add_method(cls._test_perms, "dd_u", perms=ExpectedPerms({
            "fd dam dd_u": "update_keycheck edit_bio view_person_audit_log see_agreements",
            "dd_nu": "view_person_audit_log",
        }))

        cls._add_method(cls._test_perms, "fd", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_bio view_person_audit_log see_agreements",
            "dd_nu dd_u": "view_person_audit_log",
        }))

        cls._add_method(cls._test_perms, "dam", perms=ExpectedPerms({
            "fd dam": "update_keycheck edit_bio view_person_audit_log see_agreements",
            "dd_nu dd_u": "view_person_audit_log",
        }))


class TestVisitApplicant(PersonFixtureMixin, TestVisitPersonMixin, TestCase):
    def assertApplicantPerms(self, perms):
        other_visitors = set(self.persons.keys())
        other_visitors.add(None)
        for visitor, expected_perms in perms.perms.items():
            other_visitors.discard(visitor)
            vperms = self.processes.app.permissions_of(self.persons[visitor])
            self.assertPermsEqual(
                "{} visiting app process".format(visitor), "permissions",
                expected_perms, vperms.perms)
        for visitor in other_visitors:
            vperms = self.processes.app.permissions_of(self.persons[visitor] if visitor else None)
            self.assertPermsEqual(
                "{} visiting app process".format(visitor), "permissions",
                [], vperms.perms)

        other_visitors = set(self.persons.keys())
        other_visitors.add(None)
        for visitor, expected_targets in perms.advs.items():
            other_visitors.discard(visitor)
            vperms = self.processes.app.permissions_of(self.persons[visitor])
            self.assertPermsEqual(
                "{} advocating app".format(visitor), "target",
                expected_targets, vperms.advocate_targets)
        for visitor in other_visitors:
            vperms = self.processes.app.permissions_of(self.persons[visitor] if visitor else None)
            self.assertPermsEqual(
                "{} advocating app".format(visitor), "target",
                [], vperms.advocate_targets)

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
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements view_mbox",
            "dd_nu dd_u": "view_person_audit_log",
        }, advs={
            "fd dam dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "adv dm dm_ga": "dc_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements view_mbox")
        expected.patch_advs("adv", "-dc_ga")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap")
        expected.set_perms("adv", "view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u", "-dc_ga")
        expected.patch_advs("dm dm_ga", "-dc_ga")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("fd dam app", "-edit_ldap -edit_agreements")
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
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements view_mbox",
            "adv dd_nu dd_u": "view_person_audit_log",
        }, advs={
            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
            "dm dm_ga": "dc_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements view_mbox")
        expected.patch_advs("adv", "-dc_ga")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap")
        expected.set_perms("adv", "view_person_audit_log view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u", "-dc_ga")
        expected.patch_advs("dm dm_ga", "-dc_ga")
        self.assertApplicantPermsAMApproved(expected)

        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("fd dam app", "-edit_ldap -edit_agreements")
        expected.patch_advs("fd dam adv dd_nu dd_u", "-dm +dm_ga")
        self.assertApplicantPermsFinal(expected)

    def test_dm_dmga_adv_self(self):
        """
        Test all visit combinations for an applicant from dm to dm_ga, with self as advocate
        """
        self.persons.create("app", status=const.STATUS_DM)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM_GA, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements view_mbox",
            "dd_nu dd_u": "view_person_audit_log",
        }, advs={
            "fd dam dd_nu dd_u": "dm_ga dd_u dd_nu",
            "app dm dm_ga": "dm_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.app)
        expected.patch_advs("app", "-dm_ga")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap")
        expected.patch_advs("fd dam dd_nu dd_u", "-dm_ga")
        expected.patch_advs("dm dm_ga", "-dm_ga")
        self.assertApplicantPermsAMApproved(expected)

        # Final states
        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("fd dam app", "-edit_ldap -edit_agreements")
        self.assertApplicantPermsFinal(expected)

    def test_dm_dmga_adv_dd(self):
        """
        Test all visit combinations for an applicant from dm to dm_ga, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DM)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM_GA, progress=const.PROGRESS_APP_RCVD)

        expected = ExpectedPerms({
            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements view_mbox",
            "adv dd_nu dd_u": "view_person_audit_log",
        }, advs={
            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
            "app dm dm_ga": "dm_ga",
        })
        self.assertApplicantPermsInitialProcess(expected)

        self.processes.app.advocates.add(self.persons.adv)
        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements view_mbox")
        expected.patch_advs("adv", "-dm_ga")
        self.assertApplicantPermsHasAdvocate(expected)

        expected.patch_perms("app", "-edit_ldap")
        expected.set_perms("adv", "view_person_audit_log view_mbox")
        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dm_ga")
        self.assertApplicantPermsAMApproved(expected)

        # Final states
        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        expected.patch_perms("fd dam app", "-edit_ldap -edit_agreements")
        self.assertApplicantPermsFinal(expected)

    def test_dc_dm(self):
        """
        Test all visit combinations for an applicant from dc to dm, with a dd advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("adv", status=const.STATUS_DD_NU)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM, progress=const.PROGRESS_APP_RCVD)

        # States without advocates and AMs
        for p in (const.PROGRESS_APP_NEW, const.PROGRESS_APP_RCVD, const.PROGRESS_APP_HOLD, const.PROGRESS_ADV_RCVD, const.PROGRESS_POLL_SENT):
            self.processes.app.progress = p
            self.processes.app.save()
            self.assertApplicantPerms(ExpectedPerms({
                "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements",
                "adv dd_nu dd_u": "view_person_audit_log",
            }, advs={
                "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
                "dm dm_ga": "dc_ga",
            }))

        # States with advocates and no AMs
        self.processes.app.advocates.add(self.persons.adv)
        for p in (const.PROGRESS_APP_OK,):
            self.processes.app.progress = p
            self.processes.app.save()
            self.assertApplicantPerms(ExpectedPerms({
                "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements",
                "adv": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements",
                "dd_nu dd_u": "view_person_audit_log",
            }, advs={
                "fd dam dd_nu dd_u": "dc_ga dm dd_u dd_nu",
                "adv": "dc_ga dd_u dd_nu",
                "dm dm_ga": "dc_ga",
            }))

        # States after the AM
        for p in (const.PROGRESS_FD_HOLD, const.PROGRESS_FD_OK, const.PROGRESS_DAM_HOLD, const.PROGRESS_DAM_OK):
            self.processes.app.progress = p
            self.processes.app.save()
            self.assertApplicantPerms(ExpectedPerms({
                "fd dam": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements",
                "app": "update_keycheck edit_bio view_person_audit_log see_agreements edit_agreements",
                "adv dd_nu dd_u": "view_person_audit_log",
            }, advs={
                "fd dam adv dd_nu dd_u": "dc_ga dd_u dd_nu",
                "dm dm_ga": "dc_ga",
            }))

        # Final states
        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)
        for p in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED):
            self.processes.app.progress = p
            self.processes.app.is_active = False
            self.processes.app.save()
            self.assertApplicantPerms(ExpectedPerms({
                "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_agreements edit_agreements",
                "adv dd_nu dd_u": "view_person_audit_log",
            }, advs={
                "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
                "app dm dm_ga": "dm_ga",
            }))

    #@classmethod
    #def setUpClass(cls):
    #    super(TestVisitApplicant, cls).setUpClass()
    #    cls.persons.create("am", status=const.STATUS_DD_NU)
    #    cls.ams.create("am", person=cls.persons.am)

