# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import BaseFixtureMixin, PersonFixtureMixin, ExpectedSets, NamedObjects, TestSet
import process.models as pmodels
from .common import ProcessFixtureMixin

#class TestPersonPermissions(PersonFixtureMixin, TestCase):
#    @classmethod
#    def setUpClass(cls):
#        super(TestPersonPermissions, cls).setUpClass()
#        cls.persons.create("applicant", status=const.STATUS_DC)
#        cls.persons.create("am", status=const.STATUS_DD_NU)
#        cls.processes.create("applicant", person=cls.persons.applicant, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am)
#        cls.persons.create("e_dd", status=const.STATUS_EMERITUS_DD)
#        cls.persons.create("e_dm", status=const.STATUS_EMERITUS_DM)
#        cls.persons.create("r_dd", status=const.STATUS_REMOVED_DD)
#        cls.persons.create("r_dm", status=const.STATUS_REMOVED_DM)
#        cls.persons.create("am_e_dd", status=const.STATUS_EMERITUS_DD)
#        cls.persons.create("am_r_dd", status=const.STATUS_REMOVED_DD)
#        cls.persons.create("applicant1", status=const.STATUS_DC)
#        cls.processes.create("applicant1", person=cls.persons.applicant1, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am_e_dd)
#        cls.persons.create("applicant2", status=const.STATUS_DC)
#        cls.processes.create("applicant2", person=cls.persons.applicant2, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am_r_dd)
#
#    def assertPerms(self, pname, perms):
#        self.assertItemsEqual(self.persons[pname].perms, perms)
#
#    def test_person(self):
#        self.assertPerms("pending", [])
#        self.assertPerms("dc", [])
#        self.assertPerms("dc_ga", [])
#        self.assertPerms("dm", [])
#        self.assertPerms("dm_ga", [])
#        self.assertPerms("applicant", [])
#        self.assertPerms("dd_nu", ["am_candidate", "dd"])
#        self.assertPerms("dd_u", ["am_candidate", "dd"])
#        self.assertPerms("am", ["am", "dd"])
#        self.assertPerms("e_dd", [])
#        self.assertPerms("e_dm", [])
#        self.assertPerms("r_dd", [])
#        self.assertPerms("r_dm", [])
#        self.assertPerms("am_e_dd", [])
#        self.assertPerms("am_r_dd", [])
#        self.assertPerms("fd", ["admin", "am", "dd"])
#        self.assertPerms("dam", ["admin", "am", "dd"])


class ProcExpected(object):
    def __init__(self):
        self.starts = TestSet()
        self.proc = ExpectedSets("{visitor} visiting app's process", "{problem} permissions {mismatch}")
        self.intent = ExpectedSets("{visitor} visiting app's intent requirement", "{problem} permissions {mismatch}")
        self.sc_dmup = ExpectedSets("{visitor} visiting app's sc_dmup requirement", "{problem} permissions {mismatch}")
        self.advocate = ExpectedSets("{visitor} visiting app's advocate requirement", "{problem} permissions {mismatch}")
        self.keycheck = ExpectedSets("{visitor} visiting app's keycheck requirement", "{problem} permissions {mismatch}")
        self.am_ok = ExpectedSets("{visitor} visiting app's am_ok requirement", "{problem} permissions {mismatch}")


#class TestPermsRequirementIntent(ProcessFixtureMixin, TestCase):
#    @classmethod
#    def __add_extra_tests__(cls):
#        # Process list is visible by anyone
#        for src, tgt in get_all_process_types():
#            cls._add_method(cls._test_requirement, src, tgt)
#
#    def _test_requirement(self, src_state, applying_for):
#        self.persons.create("app", status=src_state)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=applying_for)
#
#        expected_advs = ExpectedSets("{visitor} advocating app", "{problem} target {mismatch}")
#        expected.advs.set("fd dam dd_nu dd_u", "dc_ga dm dd_u dd_nu")
#        expected_perms = ExpectedSets("{visitor} visiting app's intent requirement", "{problem} permissions {mismatch}")
#        expected.perms.set("fd dam app", "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements edit_statements view_mbox request_new_status")
#
#        # Requirement just created
#        req = pmodels.Requirement.objects.get(process=self.processes, type="intent")
#
#
#        self.assertIsNone(req.approved_by)
#        self.assertIsNone(req.approved_time)
#
#        # Anyone can see the requirement page
#        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "fd", "dam", None):
#            client = self.make_test_client(visitor)
#            response = client.get(req.get_absolute_url())
#            self.assertEquals(response.status_code, 200)
#
#        # Only the applicant, FD and DAM can upload a statement
#        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "fd", "dam", None):
#        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "fd", "dam", None):
#            client = self.make_test_client(visitor)
#            response = client.get(req.get_absolute_url())
#            self.assertEquals(response.status_code, 200)


    #url(r'^(?P<pk>\d+)/intent$', views.ReqIntent.as_view(), name="process_req_intent"),
    #url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/create$', views.StatementCreate.as_view(), name="process_statement_create"),
    #url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/(?P<st>\d+)/edit$', views.StatementEdit.as_view(), name="process_statement_edit"),
    #url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/(?P<st>\d+)/raw$', views.StatementRaw.as_view(), name="process_statement_raw"),
    #url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/add_log$', views.AddProcessLog.as_view(), name="process_add_requirement_log"),

    #class Requirement(models.Model):
    #    process = models.ForeignKey(Process, related_name="requirements")
    #    type = models.CharField(verbose_name=_("Requirement type"), max_length=16, choices=REQUIREMENT_TYPES_CHOICES)
    #    approved_by = models.ForeignKey(bmodels.Person, null=True, blank=True, help_text=_("Set to the person that reviewed and approved this requirement"))
    #    approved_time = models.DateTimeField(null=True, blank=True, help_text=_("When the requirement has been approved"))
    #class Statement(models.Model):
    #    requirement = models.ForeignKey(Requirement, related_name="statements")
    #    fpr = models.ForeignKey(bmodels.Fingerprint, related_name="+", help_text=_("Fingerprint used to verify the statement"))
    #    statement = models.TextField(verbose_name=_("Signed statement"), blank=True)
    #    uploaded_by = models.ForeignKey(bmodels.Person, related_name="+", help_text=_("Person who uploaded the statement"))
    #    uploaded_time = models.DateTimeField(help_text=_("When the statement has been uploaded"))
    #class Log(models.Model):
    #    changed_by = models.ForeignKey(bmodels.Person, related_name="+", null=True)
    #    process = models.ForeignKey(Process, related_name="log")
    #    requirement = models.ForeignKey(Requirement, related_name="log", null=True, blank=True)
    #    is_public = models.BooleanField(default=False)
    #    logdate = models.DateTimeField(default=now)
    #    action = models.CharField(max_length=16, blank=True, help_text=_("Action performed with this log entry, if any"))
    #    logtext = models.TextField(blank=True, default="")

    # add statement (app, fd, dam)
    # remove statement (app if own, fd, dam)
    # edit statement (app if own, fd, dam)
    # approve
    # log comments
    # freeze process and ensure it's unchangeable


class TestVisitApplicant(ProcessFixtureMixin, TestCase):
    def assertPerms(self, perms):
        # Check advocacy targets
        can_start = set(self.persons.app.possible_new_statuses)
        if can_start != perms.starts:
            extra = can_start - perms.starts
            missing = perms.starts - can_start
            msgs = []
            if missing: msgs.append("missing: {}".format(", ".join(missing)))
            if extra: msgs.append("extra: {}".format(", ".join(extra)))
            self.fail("adv startable processes mismatch: " + "; ".join(msgs))

        # If the process has not yet been created, we skip testing it
        if "app" not in self.processes: return

        # Check process permissions
        for visitor in perms.proc.visitors:
            visit_perms = self.processes.app.permissions_of(self.persons[visitor])
            perms.proc.assertEqual(self, visitor, visit_perms)
        for visitor in perms.proc.select_others(self.persons):
            visit_perms = self.processes.app.permissions_of(self.persons[visitor] if visitor else None)
            perms.proc.assertEmpty(self, visitor, visit_perms)

        # Check requirements
        for req in ("intent", "sc_dmup", "advocate", "keycheck", "am_ok"):
            p = getattr(perms, req, None)
            if p is None: continue
            wanted = p.combine(perms.proc)

            requirement = pmodels.Requirement.objects.get(process=self.processes.app, type=req)
            for visitor in wanted.visitors:
                visit_perms = requirement.permissions_of(self.persons[visitor])
                wanted.assertEqual(self, visitor, visit_perms)
            for visitor in wanted.select_others(self.persons):
                visit_perms = requirement.permissions_of(self.persons[visitor] if visitor else None)
                wanted.assertEmpty(self, visitor, visit_perms)


##    def assertApplicantPermsInitialProcess(self, expected):
##        for p in (const.PROGRESS_APP_NEW, const.PROGRESS_APP_RCVD, const.PROGRESS_APP_HOLD, const.PROGRESS_ADV_RCVD, const.PROGRESS_POLL_SENT):
##            self.processes.app.progress = p
##            self.processes.app.save()
##            self.assertApplicantPerms(expected)
##
##    def assertApplicantPermsHasAdvocate(self, expected):
##        for p in (const.PROGRESS_APP_OK,):
##            self.processes.app.progress = p
##            self.processes.app.save()
##            self.assertApplicantPerms(expected)
##
##    def assertApplicantPermsAMApproved(self, expected):
##        for p in (const.PROGRESS_AM_OK, const.PROGRESS_FD_HOLD, const.PROGRESS_FD_OK, const.PROGRESS_DAM_HOLD, const.PROGRESS_DAM_OK):
##            self.processes.app.progress = p
##            self.processes.app.save()
##            self.assertApplicantPerms(expected)
##
##    def assertApplicantPermsFinal(self, expected):
##        for p in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED):
##            self.processes.app.progress = p
##            self.processes.app.is_active = False
##            self.processes.app.save()
##            self.assertApplicantPerms(expected)


#        requirements = ["intent", "sc_dmup"]
#        if applying_for == const.STATUS_DC_GA:
#            if person.status != const.STATUS_DC:
#                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, person.status))
#            requirements.append("advocate")
#        elif applying_for == const.STATUS_DM:
#            if person.status != const.STATUS_DC:
#                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, person.status))
#            requirements.append("advocate")
#            requirements.append("keycheck")
#        elif applying_for == const.STATUS_DM_GA:
#            if person.status == const.STATUS_DC_GA:
#                requirements.append("advocate")
#                requirements.append("keycheck")
#            elif person.status == const.STATUS_DM:
#                # No extra requirement: the declaration of intents is
#                # sufficient
#                pass
#            else:
#                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, person.status))
#        elif applying_for in (const.STATUS_DD_U, const.STATUS_DD_NU):
#            if person.status != const.STATUS_DD_NU:
#                requirements.append("keycheck")
#                requirements.append("am_ok")
#            if person.status not in (const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD):
#                requirements.append("advocate")
#        else:
#            raise RuntimeError("Invalid applying_for value {}".format(applying_for))

    def _freeze_process(self, visitor):
        """
        Set a process as frozen for FD/DAM review
        """
        self.processes.app.frozen_by = self.persons[visitor]
        self.processes.app.frozen_time = now()
        self.processes.app.save()

    def _approve_process(self, visitor):
        """
        Set a process as approved by DAM
        """
        self.processes.app.approved_by = self.persons[visitor]
        self.processes.app.approved_time = now()
        self.processes.app.save()

    def _close_process(self):
        """
        Finalize a process
        """
        self.processes.app.closed = now()
        self.processes.app.save()
        self.persons.app.status = self.processes.app.applying_for
        self.persons.app.save(audit_skip=True)

    def test_dc_dcga_adv_dm(self):
        """
        Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
        """
        self.persons.create("app", status=const.STATUS_DC)
        expected = ProcExpected()
        expected.starts.set("dc_ga dm dd_u dd_nu")
        self.assertPerms(expected)

        # Start process
        self.persons.create("adv", status=const.STATUS_DM)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DC_GA)
        expected.starts.patch("-dc_ga")
        expected.proc.set("fd dam", "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status proc_freeze")
        expected.proc.set("app", "update_keycheck edit_bio edit_ldap view_person_audit_log view_mbox request_new_status")
        expected.proc.set("dd_nu dd_u", "view_person_audit_log update_keycheck")
        expected.proc.patch("dc dc_ga dm dm_ga dd_nu dd_u dd_e dd_r fd dam app adv", "+add_log")
        expected.intent.patch("fd dam app", "+edit_statements")
        expected.intent.patch("fd dam dd_nu dd_u", "+req_approve +req_unapprove")
        expected.sc_dmup.patch("fd dam app", "+edit_statements")
        expected.sc_dmup.patch("fd dam dd_nu dd_u", "+req_approve +req_unapprove")
        expected.advocate.patch("fd dam adv dd_nu dd_u dm dm_ga", "+edit_statements")
        expected.advocate.patch("fd dam dd_nu dd_u", "+req_approve +req_unapprove")
        expected.keycheck = None
        expected.am_ok = None
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.proc.patch("fd dam", "-proc_freeze +proc_unfreeze +proc_approve")
        expected.proc.patch("app", "-edit_bio -edit_ldap")
        expected.intent.patch("app", "-edit_statements")
        expected.intent.patch("dd_nu dd_u", "-req_approve -req_unapprove")
        expected.sc_dmup.patch("app", "-edit_statements")
        expected.sc_dmup.patch("dd_nu dd_u", "-req_approve -req_unapprove")
        expected.advocate.patch("adv dd_nu dd_u dm dm_ga", "-edit_statements")
        expected.advocate.patch("dd_nu dd_u", "-req_approve -req_unapprove")
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.proc.patch("fd dam", "-proc_unfreeze -proc_approve +proc_unapprove")

        # Finalize
        self._close_process()
        expected.starts.patch("-dc_ga -dm +dm_ga")
        expected.proc.patch("fd dam", "-edit_ldap -proc_unapprove")
        expected.proc.patch("dc dc_ga dm dm_ga dd_nu dd_u dd_e dd_r fd dam app adv", "-add_log")
        expected.intent.patch("fd dam", "-edit_statements -req_approve -req_unapprove")
        expected.sc_dmup.patch("fd dam", "-edit_statements -req_approve -req_unapprove")
        expected.advocate.patch("fd dam", "-edit_statements -req_approve -req_unapprove")
        self.assertPerms(expected)

        # TODO: test log actions
        # TODO: intent with no statements
        # TODO: intent with a statement
        # TODO: intent approved
        # TODO: probably better, test requirements separately (like, intent and
        #       sc_dmup are the same for everyone)
        #       then here just test what happens when the various steps are
        #       completed, or the AM is assigned

#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dc_ga")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u", "-dc_ga")
#        expected.patch_advs("dm dm_ga", "-dc_ga")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam app", "-edit_ldap")
#        expected.patch_advs("fd dam dd_nu dd_u", "-dm +dm_ga")
#        self.assertApplicantPermsFinal(expected)

#    def test_dc_dcga_adv_dd(self):
#        """
#        Test all visit combinations for an applicant from dc to dc_ga, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DC)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DC_GA, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements edit_statements view_mbox request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
#            "dm dm_ga": "dc_ga",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dc_ga")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u", "-dc_ga")
#        expected.patch_advs("dm dm_ga", "-dc_ga")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam app", "-edit_ldap")
#        expected.patch_advs("fd dam adv dd_nu dd_u", "-dm +dm_ga")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dm_dmga_adv_self(self):
#        """
#        Test all visit combinations for an applicant from dm to dm_ga, with self as advocate
#        """
#        self.persons.create("app", status=const.STATUS_DM)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM_GA, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements edit_statements view_mbox request_new_status",
#            "dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam dd_nu dd_u": "dm_ga dd_u dd_nu",
#            "app dm dm_ga": "dm_ga",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.app)
#        expected.patch_advs("app", "-dm_ga")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.patch_advs("fd dam dd_nu dd_u", "-dm_ga")
#        expected.patch_advs("dm dm_ga", "-dm_ga")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam app", "-edit_ldap")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dm_dmga_adv_dd(self):
#        """
#        Test all visit combinations for an applicant from dm to dm_ga, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DM)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM_GA, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements edit_statements view_mbox request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
#            "app dm dm_ga": "dm_ga",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dm_ga")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dm_ga")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam app", "-edit_ldap")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dc_dm(self):
#        """
#        Test all visit combinations for an applicant from dc to dm, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DC)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements edit_statements view_mbox request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
#            "dm dm_ga": "dc_ga",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dm")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dm")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("app", "+edit_ldap")
#        expected.patch_advs("fd dam dd_nu dd_u app adv dm dm_ga", "-dc_ga +dm_ga")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dc_ddnu(self):
#        """
#        Test all visit combinations for an applicant from dc to dd_nu, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DC)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements edit_statements view_mbox request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
#            "dm dm_ga": "dc_ga",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dd_nu -dd_u")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam app", "-edit_ldap")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dc_ga -dm")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dcga_ddnu(self):
#        """
#        Test all visit combinations for an applicant from dc_ga to dd_nu, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DC_GA)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio view_person_audit_log see_statements view_mbox edit_statements request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dd_nu -dd_u")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dm_ga")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dc_ddu(self):
#        """
#        Test all visit combinations for an applicant from dc to dd_u, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DC)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements edit_statements view_mbox request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dc_ga dm dd_u dd_nu",
#            "dm dm_ga": "dc_ga",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dd_nu -dd_u")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam app", "-edit_ldap -request_new_status")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dc_ga -dm")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dcga_ddu(self):
#        """
#        Test all visit combinations for an applicant from dc_ga to dd_u, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DC_GA)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio view_person_audit_log see_statements view_mbox edit_statements request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dd_nu -dd_u")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam app", "-request_new_status")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dm_ga")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dm_ddu(self):
#        """
#        Test all visit combinations for an applicant from dm to dd_u, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DM)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements edit_statements view_mbox request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dm_ga dd_u dd_nu",
#            "dm dm_ga app": "dm_ga",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio edit_ldap view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dd_nu -dd_u")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.patch_perms("app", "-edit_ldap")
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam adv app", "-edit_ldap -request_new_status")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga adv", "-dm_ga")
#        self.assertApplicantPermsFinal(expected)
#
#    def test_dmga_ddu(self):
#        """
#        Test all visit combinations for an applicant from dm to dd_u, with a dd advocate
#        """
#        self.persons.create("app", status=const.STATUS_DM_GA)
#        self.persons.create("adv", status=const.STATUS_DD_NU)
#        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U, progress=const.PROGRESS_APP_RCVD)
#
#        expected = ExpectedPerms({
#            "fd dam app": "update_keycheck edit_bio view_person_audit_log see_statements view_mbox edit_statements request_new_status",
#            "adv dd_nu dd_u": "view_person_audit_log",
#        }, advs={
#            "fd dam adv dd_nu dd_u": "dd_u dd_nu",
#        })
#        self.assertApplicantPermsInitialProcess(expected)
#
#        self.processes.app.advocates.add(self.persons.adv)
#        expected.set_perms("adv", "update_keycheck edit_bio view_person_audit_log see_statements view_mbox")
#        expected.patch_advs("adv", "-dd_nu -dd_u")
#        self.assertApplicantPermsHasAdvocate(expected)
#
#        expected.set_perms("adv", "view_person_audit_log view_mbox")
#        expected.patch_advs("fd dam dd_nu dd_u app dm dm_ga", "-dd_nu -dd_u")
#        self.assertApplicantPermsAMApproved(expected)
#
#        self.persons.app.status = self.processes.app.applying_for
#        self.persons.app.save(audit_skip=True)
#        expected.patch_perms("fd dam app", "-request_new_status")
#        self.assertApplicantPermsFinal(expected)
