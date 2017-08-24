from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from django.conf import settings
from django.urls import reverse
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
                if not self.process.closed:
                    self.add("proc_close")
        elif self.visitor == self.person:
            self.add("view_mbox")
            if not self.process.closed:
                self.add("proc_close")
        elif self.visitor.is_am:
            self.add("view_mbox")
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
                    elif self.visitor.is_am:
                        self.add("req_unapprove" if self.requirement.approved_by else "req_approve")


class ProcessManager(models.Manager):
    def compute_requirements(self, status, applying_for):
        """
        Compute the process requirements for person applying for applying_for
        """
        if status == applying_for:
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
            if status == const.STATUS_DD_U:
                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, status))
            if status != const.STATUS_DD_NU:
                requirements.append("keycheck")
                requirements.append("am_ok")
            if status not in (const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD):
                requirements.append("advocate")
        elif applying_for == const.STATUS_EMERITUS_DD:
            if status not in (const.STATUS_DD_NU, const.STATUS_DD_U):
                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, status))
            # Only intent is required to become emeritus
            requirements = ["intent"]
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
        if self.filter(person=person, applying_for=applying_for, closed_time__isnull=True).exists():
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

    def in_early_stage(self):
        """
        Return processes that are in an early stage, that is, that still have
        an unapproved intent, sc_dmup or advocate requirement.
        """
        reqs = Requirement.objects.filter(type__in=("intent", "sc_dmup", "advocate"), approved_by__isnull=True).exclude(process__applying_for__in=(const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD))
        return self.get_queryset().filter(closed_time__isnull=True, frozen_by__isnull=True, approved_by__isnull=True, requirements__in=reqs).distinct()


class Process(models.Model):
    person = models.ForeignKey(bmodels.Person, related_name="+")
    applying_for = models.CharField("target status", max_length=20, null=False, choices=[x[1:3] for x in const.ALL_STATUS])
    started = models.DateTimeField(auto_now_add=True, verbose_name='process started')
    frozen_by = models.ForeignKey(bmodels.Person, related_name="+", blank=True, null=True, help_text=_("Person that froze this process for review, or NULL if it is still being worked on"))
    frozen_time = models.DateTimeField(null=True, blank=True, help_text=_("Date the process was frozen for review, or NULL if it is still being worked on"))
    approved_by = models.ForeignKey(bmodels.Person, related_name="+", blank=True, null=True, help_text=_("Person that reviewed this process and considered it complete, or NULL if not yet reviewed"))
    approved_time = models.DateTimeField(null=True, blank=True, help_text=_("Date the process was reviewed and considered complete, or NULL if not yet reviewed"))
    closed_by = models.ForeignKey(bmodels.Person, related_name="+", blank=True, null=True, help_text=_("Person that closed this process, or NULL if still open"))
    closed_time = models.DateTimeField(null=True, blank=True, help_text=_("Date the process was closed, or NULL if still open"))
    fd_comment = models.TextField("Front Desk comments", blank=True, default="")
    rt_request = models.TextField("RT request text", blank=True, default="")
    rt_ticket =  models.IntegerField("RT request ticket", null=True, blank=True)

    objects = ProcessManager()

    def __str__(self):
        return "{} to become {}".format(self.person, self.applying_for)

    def get_absolute_url(self):
        return reverse("process_show", args=[self.pk])

    def get_admin_url(self):
        return reverse("admin:process_process_change", args=[self.pk])

    @property
    def frozen(self):
        return self.frozen_by is not None

    @property
    def approved(self):
        return self.approved_by is not None

    @property
    def closed(self):
        return self.closed_by is not None

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
            return self.ams.select_related("am", "am__person").get(unassigned_by__isnull=True)
        except AMAssignment.DoesNotExist:
            return None

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

    def __str__(self):
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

    def add_log(self, changed_by, logtext, is_public=False, action="", logdate=None):
        """
        Add a log entry for this requirement
        """
        if logdate is None: logdate = now()
        return Log.objects.create(changed_by=changed_by, process=self.process, requirement=self, is_public=is_public, logtext=logtext, action=action, logdate=logdate)

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
            if not s.fpr:
                notes.append(("warn", "statement of intent not signed"))
            elif s.fpr.person != self.process.person:
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
                try:
                    keycheck = key.keycheck()
                except RuntimeError as e:
                    notes.append(("error", "cannot run keycheck: " + str(e)))
                    satisfied = False
                else:
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
    fpr = models.ForeignKey(bmodels.Fingerprint, related_name="+", null=True, help_text=_("Fingerprint used to verify the statement"))
    statement = models.TextField(verbose_name=_("Signed statement"), blank=True)
    uploaded_by = models.ForeignKey(bmodels.Person, related_name="+", help_text=_("Person who uploaded the statement"))
    uploaded_time = models.DateTimeField(help_text=_("When the statement has been uploaded"))

    def __str__(self):
        return "{}:{}".format(self.fpr, self.requirement)

    def get_key(self):
        from keyring.models import Key
        return Key.objects.get_or_download(self.fpr.fpr)

    @property
    def statement_clean(self):
        """
        Return the statement without the OpenPGP wrapping
        """
        msg = self.rfc3156
        if msg is None:
            return re.sub(r".*?-----BEGIN PGP SIGNED MESSAGE-----.*?\r\n\r\n(.+?)-----BEGIN PGP SIGNATURE-----.+", r"\1", self.statement, flags=re.DOTALL)
        else:
            if not msg.parsed:
                return self.statement
            else:
                return msg.text.get_payload(decode=True)

    @property
    def rfc3156(self):
        """
        If the statement is an email, parse it as rfc3156, else return None
        """
        # https://tools.ietf.org/html/rfc4880#section-7
        if self.statement.strip().startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
            return None

        from keyring.openpgp import RFC3156
        res = RFC3156(self.statement.encode("utf-8"))
        if not res.parsed:
            return None
        return res


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

    def __str__(self):
        return "{}: {}".format(self.logdate, self.logtext)

    @property
    def previous(self):
        """
        Return the previous log entry for this process.
        """
        try:
            return Log.objects.filter(logdate__lt=self.logdate, process=self.process).order_by("-logdate")[0]
        except IndexError:
            return None
