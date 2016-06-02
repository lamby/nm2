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


class ProcExpected(object):
    def __init__(self, testcase):
        self.starts = TestSet()
        self.proc = ExpectedSets(testcase, "{visitor} visiting app's process", "{problem} permissions {mismatch}")
        self.intent = ExpectedSets(testcase, "{visitor} visiting app's intent requirement", "{problem} permissions {mismatch}")
        self.sc_dmup = ExpectedSets(testcase, "{visitor} visiting app's sc_dmup requirement", "{problem} permissions {mismatch}")
        self.advocate = ExpectedSets(testcase, "{visitor} visiting app's advocate requirement", "{problem} permissions {mismatch}")
        self.keycheck = ExpectedSets(testcase, "{visitor} visiting app's keycheck requirement", "{problem} permissions {mismatch}")
        self.am_ok = ExpectedSets(testcase, "{visitor} visiting app's am_ok requirement", "{problem} permissions {mismatch}")

    def patch_generic_process_started(self):
        self.proc.set("app dd_nu dd_u activeam fd dam", "update_keycheck view_person_audit_log")
        self.proc.patch("activeam fd dam app", "+edit_bio +edit_ldap +view_mbox")
        self.proc.patch("fd dam app", "+request_new_status")
        self.proc.patch("fd dam", "+proc_freeze")
        self.proc.patch("dc dc_ga dm dm_ga dd_nu dd_u dd_e dd_r activeam fd dam app", "+add_log")
        self.intent.patch("fd dam app", "+edit_statements")
        self.intent.patch("activeam fd dam dd_nu dd_u", "+req_approve")
        self.sc_dmup.patch("fd dam app", "+edit_statements")
        self.sc_dmup.patch("activeam fd dam dd_nu dd_u", "+req_approve")
        if self.advocate is not None:
            self.advocate.patch("activeam fd dam dd_nu dd_u", "+edit_statements +req_approve")
        if self.keycheck is not None:
            pass
        if self.am_ok is not None:
            self.proc.set("am", "update_keycheck view_person_audit_log edit_bio edit_ldap view_mbox add_log")
            self.intent.patch("am", "+req_approve")
            self.sc_dmup.patch("am", "+req_approve")
            if self.advocate:
                self.advocate.patch("am", "+edit_statements +req_approve")
            self.am_ok.patch("fd dam", "+edit_statements +req_approve")

    def patch_generic_process_frozen(self):
        self.proc.patch("fd dam", "-proc_freeze +proc_unfreeze +proc_approve")
        self.proc.patch("activeam app", "-edit_bio -edit_ldap")
        self.intent.patch("app", "-edit_statements")
        self.intent.patch("activeam dd_nu dd_u", "-req_approve")
        self.sc_dmup.patch("app", "-edit_statements")
        self.sc_dmup.patch("activeam dd_nu dd_u", "-req_approve")
        if self.advocate is not None:
            self.advocate.patch("activeam dd_nu dd_u dm dm_ga", "-edit_statements")
            self.advocate.patch("activeam dd_nu dd_u", "-req_approve")
        if self.keycheck is not None:
            pass
        if self.am_ok is not None:
            self.proc.patch("am", "-edit_bio -edit_ldap")
            self.intent.patch("am", "-req_approve")
            self.sc_dmup.patch("am", "-req_approve")
            self.advocate.patch("am", "-edit_statements -req_approve")
            self.am_ok.patch("am", "-edit_statements")
            self.am_ok.patch("activeam", "-req_approve")

    def patch_generic_process_approved(self):
        self.proc.patch("fd dam", "-proc_unfreeze -proc_approve +proc_unapprove")

    def patch_generic_process_closed(self):
        self.proc.patch("fd dam", "-proc_unapprove")
        self.proc.patch("dc dc_ga dm dm_ga dd_nu dd_u dd_e dd_r activeam fd dam app", "-add_log")
        self.intent.patch("fd dam", "-edit_statements -req_approve")
        self.sc_dmup.patch("fd dam", "-edit_statements -req_approve")
        if self.advocate is not None:
            self.advocate.patch("fd dam", "-edit_statements -req_approve")
        if self.keycheck is not None:
            pass
        if self.am_ok is not None:
            self.proc.patch("am", "-add_log")
            self.am_ok.patch("fd dam", "-edit_statements -req_approve")


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
        perms.proc.assertMatches(self.processes.app)

        # Check requirements
        for req in ("intent", "sc_dmup", "advocate", "keycheck", "am_ok"):
            p = getattr(perms, req, None)
            if p is None: continue
            wanted = p.combine(perms.proc)

            requirement = pmodels.Requirement.objects.get(process=self.processes.app, type=req)
            wanted.assertMatches(requirement)

    def _assign_am(self, visitor):
        pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons[visitor], assigned_time=now())

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

    def test_dc_dcga(self):
        """
        Test all visit combinations for an applicant from dc to dc_ga
        """
        expected = ProcExpected(self)
        expected.keycheck = None
        expected.am_ok = None

        # Apply
        self.persons.create("app", status=const.STATUS_DC)
        expected.starts.set("dc_ga dm dd_u dd_nu")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DC_GA)
        expected.patch_generic_process_started()
        expected.starts.patch("-dc_ga")
        expected.proc.patch("fd dam", "+edit_ldap")
        expected.proc.patch("app", "+edit_ldap")
        expected.advocate.patch("dm dm_ga", "+edit_statements")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        expected.advocate.patch("dm dm_ga", "-edit_statements")
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        expected.starts.patch("-dc_ga -dm +dm_ga")
        expected.proc.patch("fd dam", "-edit_ldap")
        self.assertPerms(expected)

    def test_dm_dmga(self):
        """
        Test all visit combinations for an applicant from dm to dm_ga
        """
        expected = ProcExpected(self)
        expected.advocate = None
        expected.keycheck = None
        expected.am_ok = None

        # Apply
        self.persons.create("app", status=const.STATUS_DM)
        expected.starts.set("dm_ga dd_u")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM_GA)
        expected.patch_generic_process_started()
        expected.starts.patch("-dm_ga")
        expected.proc.patch("fd dam", "+edit_ldap")
        expected.proc.patch("app", "+edit_ldap")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        expected.starts.patch("-dm_ga")
        expected.proc.patch("fd dam", "-edit_ldap")
        self.assertPerms(expected)

    def test_dc_dm(self):
        """
        Test all visit combinations for an applicant from dc to dm
        """
        expected = ProcExpected(self)
        expected.keycheck = None
        expected.am_ok = None

        # Apply
        self.persons.create("app", status=const.STATUS_DC)
        expected.starts.set("dc_ga dm dd_u dd_nu")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DM)
        expected.patch_generic_process_started()
        expected.starts.patch("-dm")
        expected.proc.patch("fd dam", "+edit_ldap")
        expected.proc.patch("app", "+edit_ldap")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        expected.starts.patch("-dc_ga -dm +dm_ga -dd_nu")
        self.assertPerms(expected)

    def test_dc_ddnu(self):
        """
        Test all visit combinations for an applicant from dc to dd_nu
        """
        expected = ProcExpected(self)
        expected.keycheck = None

        # Apply
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("am", status=const.STATUS_DD_NU)
        self.ams.create("am", person=self.persons.am)
        expected.starts.set("dc_ga dm dd_u dd_nu")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_NU)
        expected.patch_generic_process_started()
        expected.starts.patch("-dd_nu")
        expected.proc.patch("fd dam", "+edit_ldap")
        expected.proc.patch("app", "+edit_ldap")
        self.assertPerms(expected)

        # Assign manager
        self._assign_am("fd")
        expected.proc.patch("am", "+edit_bio +edit_ldap")
        expected.am_ok.patch("am", "+edit_statements")
        expected.am_ok.patch("activeam", "+req_approve")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        expected.starts.patch("-dc_ga -dm -dd_nu")
        expected.proc.patch("fd dam", "-edit_ldap")
        self.assertPerms(expected)

    def test_dcga_ddnu(self):
        """
        Test all visit combinations for an applicant from dc_ga to dd_nu
        """
        expected = ProcExpected(self)
        expected.keycheck = None

        # Apply
        self.persons.create("app", status=const.STATUS_DC_GA)
        self.persons.create("am", status=const.STATUS_DD_NU)
        self.ams.create("am", person=self.persons.am)
        expected.starts.set("dm_ga dd_u dd_nu")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_NU)
        expected.patch_generic_process_started()
        expected.starts.patch("-dd_nu")
        expected.proc.patch("app am activeam fd dam", "-edit_ldap")
        self.assertPerms(expected)

        # Assign manager
        self._assign_am("fd")
        expected.proc.patch("am", "+edit_bio")
        expected.am_ok.patch("am", "+edit_statements")
        expected.am_ok.patch("activeam", "+req_approve")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        expected.starts.patch("-dm_ga -dd_nu")
        self.assertPerms(expected)

    def test_dc_ddu(self):
        """
        Test all visit combinations for an applicant from dc to dd_u
        """
        expected = ProcExpected(self)
        expected.keycheck = None

        # Apply
        self.persons.create("app", status=const.STATUS_DC)
        self.persons.create("am", status=const.STATUS_DD_NU)
        self.ams.create("am", person=self.persons.am)
        expected.starts.set("dc_ga dm dd_u dd_nu")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U)
        expected.patch_generic_process_started()
        expected.starts.patch("-dd_u")
        expected.proc.patch("fd dam", "+edit_ldap")
        expected.proc.patch("app", "+edit_ldap")
        self.assertPerms(expected)

        # Assign manager
        self._assign_am("fd")
        expected.proc.patch("am", "+edit_bio +edit_ldap")
        expected.am_ok.patch("am", "+edit_statements")
        expected.am_ok.patch("activeam", "+req_approve")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        expected.starts.patch("-dc_ga -dm -dd_nu -dd_u")
        expected.proc.patch("fd dam", "-edit_ldap")
        expected.proc.patch("app fd dam", "-edit_ldap -request_new_status")
        self.assertPerms(expected)

    def test_dcga_ddu(self):
        """
        Test all visit combinations for an applicant from dc_ga to dd_u
        """
        expected = ProcExpected(self)
        expected.keycheck = None

        # Apply
        self.persons.create("app", status=const.STATUS_DC_GA)
        self.persons.create("am", status=const.STATUS_DD_NU)
        self.ams.create("am", person=self.persons.am)
        expected.starts.set("dm_ga dd_u dd_nu")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U)
        expected.patch_generic_process_started()
        expected.starts.patch("-dd_u")
        expected.proc.patch("app am activeam fd dam", "-edit_ldap")
        self.assertPerms(expected)

        # Assign manager
        self._assign_am("fd")
        expected.proc.patch("am", "+edit_bio")
        expected.am_ok.patch("am", "+edit_statements")
        expected.am_ok.patch("activeam", "+req_approve")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        expected.starts.patch("-dm_ga -dd_nu -dd_u")
        expected.proc.patch("app fd dam", "-edit_ldap -request_new_status")
        self.assertPerms(expected)

    def test_dm_ddu(self):
        """
        Test all visit combinations for an applicant from dm to dd_u
        """
        expected = ProcExpected(self)
        expected.keycheck = None

        # Apply
        self.persons.create("app", status=const.STATUS_DM)
        self.persons.create("am", status=const.STATUS_DD_NU)
        self.ams.create("am", person=self.persons.am)
        expected.starts.set("dm_ga dd_u")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U)
        expected.patch_generic_process_started()
        expected.starts.patch("-dd_u")
        expected.proc.patch("fd dam", "+edit_ldap")
        expected.proc.patch("app", "+edit_ldap")
        self.assertPerms(expected)

        # Assign manager
        self._assign_am("fd")
        expected.proc.patch("am", "+edit_bio +edit_ldap")
        expected.am_ok.patch("am", "+edit_statements")
        expected.am_ok.patch("activeam", "+req_approve")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        expected.starts.patch("-dm_ga -dd_u")
        expected.proc.patch("fd dam", "-edit_ldap")
        expected.proc.patch("app fd dam", "-edit_ldap -request_new_status")
        self.assertPerms(expected)


    def test_dmga_ddu(self):
        """
        Test all visit combinations for an applicant from dm to dd_u
        """
        expected = ProcExpected(self)
        expected.keycheck = None

        # Apply
        self.persons.create("app", status=const.STATUS_DM_GA)
        self.persons.create("am", status=const.STATUS_DD_NU)
        self.ams.create("am", person=self.persons.am)
        expected.starts.set("dd_u")
        self.assertPerms(expected)
        self.processes.create("app", person=self.persons.app, applying_for=const.STATUS_DD_U)
        expected.patch_generic_process_started()
        expected.starts.patch("-dd_u")
        expected.proc.patch("app am activeam fd dam", "-edit_ldap")
        expected.proc.patch("app fd dam", "-edit_ldap -request_new_status")
        self.assertPerms(expected)

        # Assign manager
        self._assign_am("fd")
        expected.proc.patch("am", "+edit_bio")
        expected.am_ok.patch("am", "+edit_statements")
        expected.am_ok.patch("activeam", "+req_approve")
        self.assertPerms(expected)

        # Freeze for review
        self._freeze_process("fd")
        expected.patch_generic_process_frozen()
        self.assertPerms(expected)

        # Approve
        self._approve_process("dam")
        expected.patch_generic_process_approved()

        # Finalize
        self._close_process()
        expected.patch_generic_process_closed()
        self.assertPerms(expected)



#class RequirementTestMixin(ProcessFixtureMixin):
    # Changes according to:
    # visitor (admin, dd, active am, applicant, dm (if applying for GA) (for advocate), current am (for am_ok)
    # state of the requirement (approved or not)
    # presence of statements
    # uploader of statement
    # state of the process (frozen or not)







        # TODO: intent with no statements
        # TODO: intent with a statement
        # TODO: intent approved
        # TODO: probably better, test requirements separately (like, intent and
        #       sc_dmup are the same for everyone)
        #       then here just test what happens when the various steps are
        #       completed, or the AM is assigned



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


