# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from django.conf import settings
from django.core.urlresolvers import reverse
from django.db import models, transaction
import backend.models as bmodels
from backend.utils import cached_property
from backend import const
import re
import os
from collections import namedtuple

RequirementType = namedtuple("RequirementType", ("tag", "sdesc", "desc", "sort_order"))

REQUIREMENT_TYPES = (
    RequirementType("intent", "Intent", "Declaration of intent", 0),
    RequirementType("sc_dmup", "SC/DMUP", "SC/DFSG/DMUP agreement", 1),
    RequirementType("advocate", "Advocate", "Advocate", 2),
    RequirementType("keycheck", "Keycheck", "Key consistency checks", 3),
    RequirementType("am_ok", "AM report", "Application Manager report", 4),
)

REQUIREMENT_TYPES_CHOICES = [(x.tag, x.desc) for x in REQUIREMENT_TYPES]

REQUIREMENT_TYPES_DICT = { x.tag: x for x in REQUIREMENT_TYPES }


class ProcessVisitorPermissions(bmodels.PersonVisitorPermissions):
    def __init__(self, process, visitor):
        super(ProcessVisitorPermissions, self).__init__(process.person, visitor)
        self.process = process
        self.process_frozen = self.process.frozen_by is not None
        self.process_approved = self.process.approved_by is not None

        self.process_has_am_ok = self.process.requirements.filter(type="am_ok").exists()
        self.current_am_assignment = self.process.current_am_assignment
        if self.current_am_assignment is not None:
            self.is_current_am = self.current_am_assignment.am.person == self.visitor
        else:
            self.is_current_am = False

        if not self.process.closed and self.visitor is not None and not self.visitor.pending:
            self.add("add_log")

        if self.visitor is None:
            pass
        elif self.visitor.is_admin:
            self.add("view_mbox")
            self.add("view_private_log")
            if not self.process.closed:
                if not self.process_frozen:
                    self.add("proc_freeze")
                    if self.process_has_am_ok:
                        if self.current_am_assignment:
                            self.add("am_unassign")
                        else:
                            self.add("am_assign")
                elif self.process_approved:
                    self.add("proc_unapprove")
                else:
                    self.update(("proc_unfreeze", "proc_approve"))
        elif self.visitor == self.person:
            self.add("view_mbox")
            self.add("view_private_log")
        elif self.visitor.is_active_am:
            self.add("view_mbox")
            self.add("view_private_log")
        # TODO: advocates of this process can see the mailbox(?)
        #elif self.process.advocates.filter(pk=self.visitor.pk).exists():
        #    self.add("view_mbox")

        # The current AM can see fd comments in this process
        if self.is_current_am:
            self.add("fd_comments")
            self.add("view_private_log")
            if not self.process_frozen:
                self.add("am_unassign")


class RequirementVisitorPermissions(ProcessVisitorPermissions):
    def __init__(self, requirement, visitor):
        super(RequirementVisitorPermissions, self).__init__(requirement.process, visitor)
        self.requirement = requirement

        if self.visitor is None:
            pass
        elif self.visitor.is_admin:
            if not self.process.closed:
                if self.requirement.type != "keycheck":
                    self.add("edit_statements")
                self.add("req_unapprove" if self.requirement.approved_by else "req_approve")
        elif not self.process_frozen:
            if self.requirement.type == "intent":
                if self.visitor == self.person: self.add("edit_statements")
                if self.visitor.is_dd: self.add("req_unapprove" if self.requirement.approved_by else "req_approve")
            elif self.requirement.type == "sc_dmup":
                if self.visitor == self.person: self.add("edit_statements")
                if self.visitor.is_dd: self.add("req_unapprove" if self.requirement.approved_by else "req_approve")
            elif self.requirement.type == "advocate":
                if self.process.applying_for == const.STATUS_DC_GA:
                    if self.visitor.status in (const.STATUS_DM, const.STATUS_DM_GA, const.STATUS_DD_NU, const.STATUS_DD_U):
                        self.add("edit_statements")
                elif self.process.applying_for == const.STATUS_DM:
                    if self.visitor.status in (const.STATUS_DD_NU, const.STATUS_DD_U):
                        self.add("edit_statements")
                elif self.process.applying_for == const.STATUS_DM_GA:
                    if self.visitor == self.person or self.visitor.status in (const.STATUS_DD_NU, const.STATUS_DD_U):
                        self.add("edit_statements")
                elif self.process.applying_for == const.STATUS_DD_NU:
                    if self.visitor.status in (const.STATUS_DD_NU, const.STATUS_DD_U):
                        self.add("edit_statements")
                elif self.process.applying_for == const.STATUS_DD_U:
                    if self.visitor.status in (const.STATUS_DD_NU, const.STATUS_DD_U):
                        self.add("edit_statements")
                if self.visitor.is_dd: self.add("req_unapprove" if self.requirement.approved_by else "req_approve")
            elif self.requirement.type == "am_ok":
                if self.current_am_assignment:
                    if self.is_current_am:
                        self.add("edit_statements")
                    elif self.visitor.is_active_am:
                        self.add("req_unapprove" if self.requirement.approved_by else "req_approve")


class ProcessManager(models.Manager):
    def compute_requirements(self, status, applying_for):
        """
        Compute the process requirements for person applying for applying_for
        """
        if status == applying_for:
            raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, status))
        if status == const.STATUS_DD_U:
            raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, status))

        requirements = ["intent", "sc_dmup"]
        if applying_for == const.STATUS_DC_GA:
            if status != const.STATUS_DC:
                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, status))
            requirements.append("advocate")
        elif applying_for == const.STATUS_DM:
            if status != const.STATUS_DC:
                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, status))
            requirements.append("advocate")
            requirements.append("keycheck")
        elif applying_for == const.STATUS_DM_GA:
            if status == const.STATUS_DC_GA:
                requirements.append("advocate")
                requirements.append("keycheck")
            elif status == const.STATUS_DM:
                # No extra requirement: the declaration of intents is
                # sufficient
                pass
            else:
                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, status))
        elif applying_for in (const.STATUS_DD_U, const.STATUS_DD_NU):
            if status != const.STATUS_DD_NU:
                requirements.append("keycheck")
                requirements.append("am_ok")
            if status not in (const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD):
                requirements.append("advocate")
        else:
            raise RuntimeError("Invalid applying_for value {}".format(applying_for))

        return requirements

    @transaction.atomic
    def create(self, person, applying_for, skip_requirements=False, **kw):
        """
        Create a new process and all its requirements
        """
        # Forbid pending persons to start processes
        if person.pending:
            raise RuntimeError("Invalid applying_for value {} for a person whose account is still pending".format(applying_for))

        # Check that no active process of the same kind exists
        if self.filter(person=person, applying_for=applying_for, closed__isnull=True).exists():
            raise RuntimeError("there is already an active process for {} to become {}".format(person, applying_for))

        # Compute requirements
        if skip_requirements:
            requirements = []
        else:
            requirements = self.compute_requirements(person.status, applying_for)

        # Create the new process
        res = self.model(person=person, applying_for=applying_for, **kw)
        # Save it to get an ID
        res.save(using=self._db)

        # Create the requirements
        for req in requirements:
            r = Requirement.objects.create(process=res, type=req)

        return res


class Process(models.Model):
    person = models.ForeignKey(bmodels.Person, related_name="+")
    applying_for = models.CharField("target status", max_length=20, null=False, choices=[x[1:3] for x in const.ALL_STATUS])
    frozen_by = models.ForeignKey(bmodels.Person, related_name="+", blank=True, null=True, help_text=_("Person that froze this process for review, or NULL if it is still being worked on"))
    frozen_time = models.DateTimeField(null=True, blank=True, help_text=_("Date the process was frozen for review, or NULL if it is still being worked on"))
    approved_by = models.ForeignKey(bmodels.Person, related_name="+", blank=True, null=True, help_text=_("Person that reviewed this process and considered it complete, or NULL if not yet reviewed"))
    approved_time = models.DateTimeField(null=True, blank=True, help_text=_("Date the process was reviewed and considered complete, or NULL if not yet reviewed"))
    closed = models.DateTimeField(null=True, blank=True, help_text=_("Date the process was closed, or NULL if still open"))
    fd_comment = models.TextField("Front Desk comments", blank=True, default="")

    objects = ProcessManager()

    def __unicode__(self):
        return u"{} to become {}".format(self.person, self.applying_for)

    def get_absolute_url(self):
        return reverse("process_show", args=[self.pk])

    def get_admin_url(self):
        return reverse("admin:process_process_change", args=[self.pk])

    @property
    def a_link(self):
        from django.utils.safestring import mark_safe
        from django.utils.html import conditional_escape
        return mark_safe("<a href='{}'>→ {}</a>".format(
            conditional_escape(self.get_absolute_url()),
            conditional_escape(const.ALL_STATUS_DESCS[self.applying_for])))

    @property
    def can_advocate_self(self):
        return self.applying_for == const.STATUS_DM_GA and self.person.status == const.STATUS_DM

    @property
    def current_am_assignment(self):
        """
        Return the current Application Manager assignment for this process, or
        None if there is none.
        """
        try:
            return self.ams.get(unassigned_by__isnull=True)
        except AMAssignment.DoesNotExist:
            return None

    def compute_status(self):
        """
        Return a dict with the process status:
        {
            "requirements_ok": [list of Requirement],
            "requirements_missing": [list of Requirement],
            "log_first": Log,
            "log_last": Log,
        }
        """
        rok = []
        rnok = []
        requirements = {}
        for r in self.requirements.all():
            if r.approved_by:
                rok.append(r)
            else:
                rnok.append(r)
            requirements[r.type] = r

        # Compute the list of advocates
        adv = requirements.get("advocate", None)
        advocates = set()
        if adv is not None:
            for s in adv.statements.all():
                advocates.add(s.uploaded_by)

        log = list(self.log.order_by("logdate").select_related("changed_by", "requirement"))

        return {
            "requirements": requirements,
            "requirements_sorted": sorted(requirements.values(), key=lambda x: REQUIREMENT_TYPES_DICT[x.type].sort_order),
            "requirements_ok": sorted(rok, key=lambda x: REQUIREMENT_TYPES_DICT[x.type].sort_order),
            "requirements_missing": sorted(rnok, key=lambda x: REQUIREMENT_TYPES_DICT[x.type].sort_order),
            "log_first": log[0] if log else None,
            "log_last": log[-1] if log else None,
            "log": log,
            "advocates": sorted(advocates),
        }

    def permissions_of(self, visitor):
        """
        Compute which ProcessVisitorPermissions \a visitor has over this process
        """
        return ProcessVisitorPermissions(self, visitor)

    def add_log(self, changed_by, logtext, is_public=False, action="", logdate=None):
        """
        Add a log entry for this process
        """
        if logdate is None: logdate = now()
        return Log.objects.create(changed_by=changed_by, process=self, is_public=is_public, logtext=logtext, action=action, logdate=logdate)

    def get_statements_as_mbox(self):
        from .email import build_python_message


        # Generating mailboxes in python2 is surprisingly difficult and painful.
        # A lot of this code has been put together thanks to:
        # http://wordeology.com/computer/how-to-send-good-unicode-email-with-python.html
        import mailbox
        import email.utils
        import tempfile
        import time
        from email.header import Header

        with tempfile.NamedTemporaryFile(mode="wb+") as outfile:
            mbox = mailbox.mbox(path=outfile.name, create=True)

            for req in self.requirements.all():
                for stm in req.statements.all():
                    msg = build_python_message(
                        stm.uploaded_by,
                        subject="Signed statement for " + req.get_type_display(),
                        date=stm.uploaded_time,
                        body=stm.statement,
                        factory=mailbox.Message)
                    mbox.add(msg)

            mbox.close()

            outfile.seek(0)
            return outfile.read()

    @property
    def archive_email(self):
        return "archive-{}@nm.debian.org".format(self.pk)

    @property
    def mailbox_file(self):
        """
        The pathname of the archival mailbox, or None if it does not exist
        """
        PROCESS_MAILBOX_DIR = getattr(settings, "PROCESS_MAILBOX_DIR", "/srv/nm.debian.org/mbox/processes/")
        fname = os.path.join(PROCESS_MAILBOX_DIR, "process-{}.mbox".format(self.pk))
        if os.path.exists(fname):
            return fname
        return None

    @property
    def mailbox_mtime(self):
        """
        The mtime of the archival mailbox, or None if it does not exist
        """
        fname = self.mailbox_file
        if fname is None: return None
        return datetime.datetime.fromtimestamp(os.path.getmtime(fname))


class Requirement(models.Model):
    process = models.ForeignKey(Process, related_name="requirements")
    type = models.CharField(verbose_name=_("Requirement type"), max_length=16, choices=REQUIREMENT_TYPES_CHOICES)
    approved_by = models.ForeignKey(bmodels.Person, null=True, blank=True, help_text=_("Set to the person that reviewed and approved this requirement"))
    approved_time = models.DateTimeField(null=True, blank=True, help_text=_("When the requirement has been approved"))

    class Meta:
        unique_together = ("process", "type")
        ordering = ["type"]

    def __unicode__(self):
        return self.type_desc

    @property
    def type_desc(self):
        res = REQUIREMENT_TYPES_DICT.get(self.type, None)
        if res is None: return self.type
        return res.desc

    @property
    def type_sdesc(self):
        res = REQUIREMENT_TYPES_DICT.get(self.type, None)
        if res is None: return self.type
        return res.sdesc

    def get_absolute_url(self):
        return reverse("process_req_" + self.type, args=[self.process_id])

    def get_admin_url(self):
        return reverse("admin:process_requirement_change", args=[self.pk])

    @property
    def a_link(self):
        from django.utils.safestring import mark_safe
        from django.utils.html import conditional_escape
        return mark_safe("<a href='{}'>{}</a>".format(
            conditional_escape(self.get_absolute_url()),
            conditional_escape(REQUIREMENT_TYPES_DICT[self.type].desc)))

    def permissions_of(self, visitor):
        """
        Compute which permissions \a visitor has over this requirement
        """
        return RequirementVisitorPermissions(self, visitor)

    def add_log(self, changed_by, logtext, is_public=False, action=""):
        """
        Add a log entry for this requirement
        """
        return Log.objects.create(changed_by=changed_by, process=self.process, requirement=self, is_public=is_public, logtext=logtext, action=action)

    def compute_status(self):
        """
        Return a dict describing the status of this requirement.

        The dict can contain:
        {
            "satisfied": bool,
            "notes": [ ("class", "text") ],
        }
        """
        meth = getattr(self, "compute_status_" + self.type, None)
        if meth is None: return {}
        return meth()

    def _compute_warnings_own_statement(self, notes):
        """
        Check that the statement is signed with the current active key of the
        process' person
        """
        satisfied = False
        for s in self.statements.all().select_related("uploaded_by"):
            if s.uploaded_by != self.process.person:
                notes.append(("warn", "statement of intent uploaded by {} instead of the applicant".format(s.uploaded_by.lookup_key)))
            if s.fpr.person != self.process.person:
                notes.append(("warn", "statement of intent signed by {} instead of the applicant".format(s.fpr.person.lookup_key)))
            elif not s.fpr.is_active:
                notes.append(("warn", "statement of intent signed with key {} instead of the current active key".format(s.fpr.fpr)))
            satisfied = True
        return satisfied

    def compute_status_intent(self):
        notes = []
        satisfied = self._compute_warnings_own_statement(notes)
        return {
            "satisfied": satisfied,
            "notes": notes,
        }

    def compute_status_sc_dmup(self):
        notes = []
        satisfied = self._compute_warnings_own_statement(notes)
        return {
            "satisfied": satisfied,
            "notes": notes,
        }

    def compute_status_advocate(self):
        notes = []
        satisfied_count = 0
        can_advocate_self = self.process.can_advocate_self
        for s in self.statements.all().select_related("uploaded_by"):
            if not can_advocate_self and s.uploaded_by == self.process.person:
                notes.append(("warn", "statement signed by the applicant"))
            else:
                satisfied_count += 1
        if self.process.applying_for in (const.STATUS_DD_U, const.STATUS_DD_NU):
            if satisfied_count == 1:
                notes.append(("warn", "if possible, have more than 1 advocate"))
        return {
            "satisfied": satisfied_count > 0,
            "notes": notes,
        }

    def compute_status_am_ok(self):
        # Compute the latest AM
        latest_am = self.process.current_am_assignment
        if latest_am is None:
            try:
                latest_am = self.process.ams.order_by("-unassigned_time")[0]
            except IndexError:
                latest_am = None
        notes = []
        satisfied = False
        for s in self.statements.all().select_related("uploaded_by"):
            if latest_am is None:
                notes.append(("warn", "statement of intent signed by {} but no AMs have been assigned".format(s.uploaded_by.lookup_key)))
            elif s.uploaded_by != latest_am.am.person:
                notes.append(("warn", "statement of intent signed by {} instead of {} as the last assigned AM".format(s.uploaded_by.lookup_key, latest_am.am.person.lookup_key)))
            satisfied = True
        return {
            "satisfied": satisfied,
            "notes": notes,
        }

    def compute_status_keycheck(self):
        notes = []
        satisfied = True
        keycheck_results = None

        if not self.process.person.fpr:
            notes.append(("error", "no key is configured for {}".format(self.process.person.lookup_key)))
            satisfied = False
        else:
            from keyring.models import Key
            try:
                key = Key.objects.get_or_download(self.process.person.fpr)
            except RuntimeError as e:
                key = None
                notes.append(("error", "cannot run keycheck: " + str(e)))
                satisfied = False

            if key is not None:
                keycheck = key.keycheck()
                uids = []
                has_good_uid = False
                for ku in keycheck.uids:
                    uids.append({
                        "name": ku.uid.name.replace("@", ", "),
                        "remarks": " ".join(sorted(ku.errors)) if ku.errors else "ok",
                        "sigs_ok": ku.sigs_ok,
                        "sigs_no_key": len(ku.sigs_no_key),
                        "sigs_bad": len(ku.sigs_bad)
                    })
                    if not ku.errors and len(ku.sigs_ok) >= 2:
                        has_good_uid = True

                if not has_good_uid:
                    notes.append(("warn", "no UID found that fully satisfies requirements"))
                    satisfied = False

                keycheck_results = {
                    "main": {
                        "remarks": " ".join(sorted(keycheck.errors)) if keycheck.errors else "ok",
                    },
                    "uids": uids,
                    "updated": key.check_sigs_updated,
                }

                if keycheck.errors:
                    notes.append(("warn", "key has issues " + keycheck_results["main"]["remarks"]))
                    satisfied = False

        return {
            "satisfied": satisfied,
            "notes": notes,
            "keycheck": keycheck_results,
        }



class AMAssignment(models.Model):
    """
    AM assignment on a process
    """
    process = models.ForeignKey(Process, related_name="ams")
    am = models.ForeignKey(bmodels.AM)
    paused = models.BooleanField(default=False, help_text=_("Whether this process is paused and the AM is free to take another applicant in the meantime"))
    assigned_by = models.ForeignKey(bmodels.Person, related_name="+", help_text=_("Person who did the assignment"))
    assigned_time = models.DateTimeField(help_text=_("When the assignment happened"))
    unassigned_by = models.ForeignKey(bmodels.Person, related_name="+", blank=True, null=True, help_text=_("Person who did the unassignment"))
    unassigned_time = models.DateTimeField(blank=True, null=True, help_text=_("When the unassignment happened"))

    class Meta:
        ordering = ["-assigned_by"]

    def get_admin_url(self):
        return reverse("admin:process_amassignment_change", args=[self.pk])


class Statement(models.Model):
    """
    A signed statement
    """
    requirement = models.ForeignKey(Requirement, related_name="statements")
    fpr = models.ForeignKey(bmodels.Fingerprint, related_name="+", help_text=_("Fingerprint used to verify the statement"))
    statement = models.TextField(verbose_name=_("Signed statement"), blank=True)
    uploaded_by = models.ForeignKey(bmodels.Person, related_name="+", help_text=_("Person who uploaded the statement"))
    uploaded_time = models.DateTimeField(help_text=_("When the statement has been uploaded"))

    def __unicode__(self):
        return "{}:{}".format(self.fpr, self.requirement)

    def get_key(self):
        from keyring.models import Key
        return Key.objects.get_or_download(self.fpr.fpr)

    @property
    def statement_clean(self):
        """
        Return the statement without the OpenPGP wrapping
        """
        # https://tools.ietf.org/html/rfc4880#section-7
        return re.sub(r".*?-----BEGIN PGP SIGNED MESSAGE-----.*?\r\n\r\n(.+?)-----BEGIN PGP SIGNATURE-----.+", r"\1", self.statement, flags=re.DOTALL)


class Log(models.Model):
    """
    A log entry about anything that happened during a process
    """
    changed_by = models.ForeignKey(bmodels.Person, related_name="+", null=True)
    process = models.ForeignKey(Process, related_name="log")
    requirement = models.ForeignKey(Requirement, related_name="log", null=True, blank=True)
    is_public = models.BooleanField(default=False)
    logdate = models.DateTimeField(default=now)
    action = models.CharField(max_length=16, blank=True, help_text=_("Action performed with this log entry, if any"))
    logtext = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-logdate"]

    def __unicode__(self):
        return u"{}: {}".format(self.logdate, self.logtext)

    @property
    def previous(self):
        """
        Return the previous log entry for this process.
        """
        try:
            return Log.objects.filter(logdate__lt=self.logdate, process=self.process).order_by("-logdate")[0]
        except IndexError:
            return None


#def post_save_log(sender, **kw):
#    log = kw.get('instance', None)
#    if sender is not Log or not log or kw.get('raw', False):
#        return
#    if 'created' not in kw:
#        # this is a django BUG
#        return
#    if kw.get('created'):
#        # checks for progress transition
#        previous_log = log.previous
#        if previous_log is None or previous_log.progress == log.progress:
#            return
#
#        ### evaluate the progress transition to notify applicant
#        ### remember we are during Process.save() method execution
#        maybe_notify_applicant_on_progress(log, previous_log)
#
#post_save.connect(post_save_log, sender=Log, dispatch_uid="Log_post_save_signal")

# - signed agreement with SC/DFSG/DMUP
# - signed declaration of intent


#DC -> DC+ga needs at least:
# - signed agreement with SC/DFSG/DMUP
# - signed declaration of intent
# - signed advocacy from a DM or DD
#
#DM -> DC+ga needs at least:
# - signed agreement with SC/DFSG/DMUP
# - signed declaration of intent
#
#DC -> DM, and DC+ga -> DM+ga, need at least:
# - signed agreement with SC/DFSG/DMUP
# - signed declaration of intent
# - signed advocacy from a DD
# - keycheck ok
#
#* -> DD needs at least:
# - signed agreement with SC/DFSG/DMUP
# - signed declaration of intent (which we currently miss)
# - signed advocacy from a DD
# - keycheck ok
# - signed approval from an AM
#
#DD emeritus -> DD needs at least:
# - signed agreement with SC/DFSG/DMUP
# - signed declaration of intent (which we currently miss)
# - keycheck ok
# - signed approval from an AM?

# Requirements:
#
# Signed agreement:
#  - signed statement of the right type, with the right fingerprint
#
# Declaration of intent:
#  - signed statement of the right type
#
# Advocacies (plural):
#  - signed statement of the right type
#
# AM report:
#  - signed statement of the right type
#
# Keycheck:
#  - boolean (or signed statement?) entered by FD/DAM


#class ProcessManager(models.Manager):
#    def create_instant_process(self, person, new_status, steps):
#        """
#        Create a process for the given person to get new_status, with the given
#        log entries. The 'process' field of the log entries in steps will be
#        filled by this function.
#
#        Return the newly created Process instance.
#        """
#        if not steps:
#            raise ValueError("steps should not be empty")
#
#        if not all(isinstance(s, Log) for s in steps):
#            raise ValueError("all entries of steps must be instances of Log")
#
#        # Create a process
#        pr = Process(
#            person=person,
#            applying_as=person.status,
#            applying_for=new_status,
#            progress=steps[-1].progress,
#            is_active=steps[-1].progress not in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED),
#        )
#        pr.save()
#
#        # Save all log entries
#        for l in steps:
#            l.process = pr
#            l.save()
#
#        return pr
#
#class Process(models.Model):
#    """
#    A process through which a person gets a new status
#
#    There can be multiple 'Process'es per Person, but only one of them can be
#    active at any one time. This is checked during maintenance.
#    """
#    class Meta:
#        db_table = "process"
#
#    # Custom manager
#    objects = ProcessManager()
#
#    person = models.ForeignKey(Person, related_name="processes")
#    # 1.3-only: person = models.ForeignKey(Person, related_name="processes", on_delete=models.CASCADE)
#
#    applying_as = models.CharField("original status", max_length=20, null=False,
#                                    choices=[x[1:3] for x in const.ALL_STATUS])
#    applying_for = models.CharField("target status", max_length=20, null=False,
#                                    choices=[x[1:3] for x in const.ALL_STATUS])
#    progress = models.CharField(max_length=20, null=False,
#                                choices=[x[1:3] for x in const.ALL_PROGRESS])
#
#    # This is NULL until one gets a manager
#    manager = models.ForeignKey(AM, related_name="processed", null=True, blank=True)
#    # 1.3-only: manager = models.ForeignKey(AM, related_name="processed", null=True, on_delete=models.PROTECT)
#
#    advocates = models.ManyToManyField(Person, related_name="advocated", blank=True,
#                                limit_choices_to={ "status__in": (const.STATUS_DD_U, const.STATUS_DD_NU) })
#
#    # True if progress NOT IN (PROGRESS_DONE, PROGRESS_CANCELLED)
#    is_active = models.BooleanField(null=False, default=False)
#
#    archive_key = models.CharField("mailbox archive key", max_length=128, null=False, unique=True)
#
#    def save(self, *args, **kw):
#        if not self.archive_key:
#            ts = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
#            if self.person.uid:
#                self.archive_key = "-".join((ts, self.applying_for, self.person.uid))
#            else:
#                self.archive_key = "-".join((ts, self.applying_for, self.person.email))
#        super(Process, self).save(*args, **kw)
#
#    def __unicode__(self):
#        return u"{} to become {} ({})".format(
#            unicode(self.person),
#            const.ALL_STATUS_DESCS.get(self.applying_for, self.applying_for),
#            const.ALL_PROGRESS_DESCS.get(self.progress, self.progress),
#        )
#
#    def __repr__(self):
#        return "{} {}->{}".format(
#            self.person.lookup_key,
#            self.person.status,
#            self.applying_for)
#
#    @models.permalink
#    def get_absolute_url(self):
#        return ("public_process", (), dict(key=self.lookup_key))
#
#    @property
#    def lookup_key(self):
#        """
#        Return a key that can be used to look up this process in the database
#        using Process.lookup.
#
#        Currently, this is the email if the process is active, else the id.
#        """
#        # If the process is active, and we only have one process, use the
#        # person's lookup key. In all other cases, use the process ID
#        if self.is_active:
#            if self.person.processes.filter(is_active=True).count() == 1:
#                return self.person.lookup_key
#            else:
#                return str(self.id)
#        else:
#            return str(self.id)
#
#    @classmethod
#    def lookup(cls, key):
#        # Key can either be a Process ID or a person's lookup key
#        if key.isdigit():
#            try:
#                return cls.objects.get(id=int(key))
#            except cls.DoesNotExist:
#                return None
#        else:
#            # If a person's lookup key is used, and there is only one active
#            # process, return that one. Else, return the most recent process.
#            p = Person.lookup(key)
#            if p is None:
#                return None
#
#            # If we reach here, either we have one process, or a new process
#            # has been added # changed since the URL was generated. We have an
#            # ambiguous situation, which we handle blissfully arbitrarily
#            res = p.active_processes
#            if res: return res[0]
#
#            try:
#                from django.db.models import Max
#                return p.processes.annotate(last_change=Max("log__logdate")).order_by("-last_change")[0]
#            except IndexError:
#                return None
#
#    @classmethod
#    def lookup_or_404(cls, key):
#        from django.http import Http404
#        res = cls.lookup(key)
#        if res is not None:
#            return res
#        raise Http404
#
#    @property
#    def mailbox_file(self):
#        """
#        The pathname of the archival mailbox, or None if it does not exist
#        """
#        fname = os.path.join(PROCESS_MAILBOX_DIR, self.archive_key) + ".mbox"
#        if os.path.exists(fname):
#            return fname
#        return None
#
#    @property
#    def mailbox_mtime(self):
#        """
#        The mtime of the archival mailbox, or None if it does not exist
#        """
#        fname = self.mailbox_file
#        if fname is None: return None
#        return datetime.datetime.fromtimestamp(os.path.getmtime(fname))
#
#    @property
#    def archive_email(self):
#        if self.person.uid:
#            key = self.person.uid
#        else:
#            key = self.person.email.replace("@", "=")
#        return "archive-{}@nm.debian.org".format(key)
#
#    def permissions_of(self, visitor):
#        """
#        Compute which ProcessVisitorPermissions \a visitor has over this process
#        """
#        return ProcessVisitorPermissions(self, visitor)
#
#    class DurationStats(object):
#        AM_STATUSES = frozenset((const.PROGRESS_AM_HOLD, const.PROGRESS_AM))
#
#        def __init__(self):
#            self.first = None
#            self.last = None
#            self.last_progress = None
#            self.total_am_time = 0
#            self.total_amhold_time = 0
#            self.last_am_time = 0
#            self.last_amhold_time = 0
#            self.last_am_history = []
#            self.last_log_text = None
#
#        def process_last_am_history(self, end=None):
#            """
#            Compute AM duration stats.
#
#            end is the datetime of the end of the AM stats period. If None, the
#            current datetime is used.
#            """
#            if not self.last_am_history: return
#            if end is None:
#                end = datetime.datetime.utcnow()
#
#            time_for_progress = dict()
#            period_start = None
#            for l in self.last_am_history:
#                if period_start is None:
#                    period_start = l
#                elif l.progress != period_start.progress:
#                    days = (l.logdate - period_start.logdate).days
#                    time_for_progress[period_start.progress] = \
#                            time_for_progress.get(period_start.progress, 0) + days
#                    period_start = l
#
#            if period_start:
#                days = (end - period_start.logdate).days
#                time_for_progress[period_start.progress] = \
#                        time_for_progress.get(period_start.progress, 0) + days
#
#            self.last_am_time = time_for_progress.get(const.PROGRESS_AM, 0)
#            self.last_amhold_time = time_for_progress.get(const.PROGRESS_AM_HOLD, 0)
#            self.total_am_time += self.last_am_time
#            self.total_amhold_time += self.last_amhold_time
#
#            self.last_am_history = []
#
#        def process_log(self, l):
#            """
#            Process a log entry. Log entries must be processed in cronological
#            order.
#            """
#            if self.first is None: self.first = l
#
#            if l.progress in self.AM_STATUSES:
#                if self.last_progress not in self.AM_STATUSES:
#                    self.last_am_time = 0
#                    self.last_amhold_time = 0
#                self.last_am_history.append(l)
#            elif self.last_progress in self.AM_STATUSES:
#                self.process_last_am_history(end=l.logdate)
#
#            self.last = l
#            self.last_progress = l.progress
#
#        def stats(self):
#            """
#            Compute a dict with statistics
#            """
#            # Process pending AM history items: happens when the last log has
#            # AM_STATUSES status
#            self.process_last_am_history()
#            if self.last is not None and self.first is not None:
#                total_duration = (self.last.logdate-self.first.logdate).days
#            else:
#                total_duration = None
#
#            return dict(
#                # Date the process started
#                log_first=self.first,
#                # Date of the last log entry
#                log_last=self.last,
#                # Total duration in days
#                total_duration=total_duration,
#                # Days spent in AM
#                total_am_time=self.total_am_time,
#                # Days spent in AM_HOLD
#                total_amhold_time=self.total_amhold_time,
#                # Days spent in AM with the last AM
#                last_am_time=self.last_am_time,
#                # Days spent in AM_HOLD with the last AM
#                last_amhold_time=self.last_amhold_time,
#                # Last nonempty log text
#                last_log_text=self.last_log_text,
#            )
#
#    def duration_stats(self):
#        stats_maker = self.DurationStats()
#        for l in self.log.order_by("logdate"):
#            stats_maker.process_log(l)
#        return stats_maker.stats()
#
#    def annotate_with_duration_stats(self):
#        s = self.duration_stats()
#        for k, v in s.iteritems():
#            setattr(self, k, v)
#
#    def finalize(self, logtext, tstamp=None, audit_author=None, audit_notes=None):
#        """
#        Bring the process to completion, by setting its progress to DONE,
#        adding a log entry and updating the person status.
#        """
#        if self.progress != const.PROGRESS_DAM_OK:
#            raise ValueError("cannot finalise progress {}: status is {} instead of {}".format(
#                unicode(self), self.progress, const.PROGRESS_DAM_OK))
#
#        if tstamp is None:
#            tstamp = datetime.datetime.utcnow()
#
#        self.progress = const.PROGRESS_DONE
#        self.person.status = self.applying_for
#        self.person.status_changed = tstamp
#        l = Log(
#            changed_by=None,
#            process=self,
#            progress=self.progress,
#            logdate=tstamp,
#            logtext=logtext
#        )
#        l.save()
#        self.save()
#        self.person.save(audit_author=audit_author, audit_notes=audit_notes)
