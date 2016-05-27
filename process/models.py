# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import now
from django.core.urlresolvers import reverse
from django.db import models, transaction
import backend.models as bmodels
from backend.utils import cached_property
import statements.models as smodels
from backend import const

REQUIREMENT_TYPES = (
    ( "intent", "Declaration of intent" ),
    ( "sc_dmup", "SC/DFSG/DMUP agreement" ),
    ( "advocate", "Advocate" ),
    ( "keycheck", "Key consistency checks" ),
    ( "am_ok", "Application Manager report" ),
)

REQUIREMENT_TYPES_DICT = dict(REQUIREMENT_TYPES)


class ProcessVisitorPermissions(bmodels.PersonVisitorPermissions):
    def __init__(self, process, visitor):
        super(ProcessVisitorPermissions, self).__init__(process.person, visitor)
        self.process = process

    @cached_property
    def _can_view_email(self):
        """
        The visitor can view the process's email archive
        """
        if self.visitor is None: return False
        # Any admins
        if self.visitor.is_admin: return True
        # The person themselves
        if self.visitor.pk == self.person.pk: return True
        # Any AM
        if self.visitor.am_or_none: return True
        # The advocates
        # TODO return self.process.advocates.filter(pk=self.visitor.pk).exists()
        return False

    def _compute_perms(self):
        res = super(ProcessVisitorPermissions, self)._compute_perms()
        if self._can_view_email: res.add("view_mbox")
        return res


class ProcessManager(models.Manager):
    def compute_requirements(self, person, applying_for):
        """
        Compute the process requirements for person applying for applying_for
        """
        if person.status == applying_for:
            raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, person.status))
        if person.pending:
            raise RuntimeError("Invalid applying_for value {} for a person whose account is still pending".format(applying_for))
        if person.status == const.STATUS_DD_U:
            raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, person.status))

        requirements = ["intent", "sc_dmup"]
        if applying_for == const.STATUS_DC_GA:
            if person.status != const.STATUS_DC:
                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, person.status))
            requirements.append("advocate")
        elif applying_for == const.STATUS_DM:
            if person.status != const.STATUS_DC:
                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, person.status))
            requirements.append("advocate")
            requirements.append("keycheck")
        elif applying_for == const.STATUS_DM_GA:
            if person.status == const.STATUS_DC_GA:
                requirements.append("advocate")
                requirements.append("keycheck")
            elif person.status == const.STATUS_DM:
                # No extra requirement: the declaration of intents is
                # sufficient
                pass
            else:
                raise RuntimeError("Invalid applying_for value {} for a person with status {}".format(applying_for, person.status))
        elif applying_for in (const.STATUS_DD_U, const.STATUS_DD_NU):
            if person.status != const.STATUS_DD_NU:
                requirements.append("keycheck")
                requirements.append("am_ok")
            if person.status not in (const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD):
                requirements.append("advocate")
        else:
            raise RuntimeError("Invalid applying_for value {}".format(applying_for))

        return requirements

    @transaction.atomic
    def create(self, person, applying_for):
        """
        Create a new process and all its requirements
        """
        # Check that no active process of the same kind exists
        if self.filter(person=person, applying_for=applying_for, closed__isnull=True).exists():
            raise RuntimeError("there is already an active process for {} to become {}".format(person, applying_for))

        # Compute requirements
        requirements = self.compute_requirements(person, applying_for)

        # Create the new process
        res = self.model(person=person, applying_for=applying_for)
        # Save it to get an ID
        res.save(using=self._db)

        # Create the requirements
        for req in requirements:
            r = Requirement.objects.create(process=res, type=req, is_ok=False)

        return res


class Process(models.Model):
    person = models.ForeignKey(bmodels.Person, related_name="+")
    applying_for = models.CharField("target status", max_length=20, null=False, choices=[x[1:3] for x in const.ALL_STATUS])
    completed = models.DateTimeField(null=True, help_text=_("Date the process was reviewed and considered complete, or NULL if not complete"))
    closed = models.DateTimeField(null=True, help_text=_("Date the process was closed, or NULL if still open"))
    fd_comment = models.TextField("Front Desk comments", blank=True, default="")

    objects = ProcessManager()

    def __unicode__(self):
        return u"{} to become {}".format(self.person, self.applying_for)

    def get_absolute_url(self):
        return reverse("process_show", args=[self.pk])

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
        for r in self.requirements.all():
            if r.is_ok:
                rok.append(r)
            else:
                rnok.append(r)
        return {
            "requirements_ok": rok,
            "requirements_missing": rnok,
            "log_first": self.log.order_by("logdate")[0],
            "log_last": self.log.order_by("-logdate")[0],
        }

    def permissions_of(self, visitor):
        """
        Compute which ProcessVisitorPermissions \a visitor has over this process
        """
        return ProcessVisitorPermissions(self, visitor)

    def add_log(self, changed_by, logtext, is_public=False):
        """
        Add a log entry for this process
        """
        return Log.objects.create(changed_by=changed_by, process=self, is_public=is_public, logtext=logtext)


class Requirement(models.Model):
    process = models.ForeignKey(Process, related_name="requirements")
    type = models.CharField(verbose_name=_("Requirement type"), max_length=16, choices=REQUIREMENT_TYPES)
    is_ok = models.BooleanField(null=False, default=False)

    class Meta:
        unique_together = ("process", "type")
        ordering = ["type"]

    def __unicode__(self):
        return REQUIREMENT_TYPES_DICT.get(self.type, self.type)


class Statement(models.Model):
    """
    A signed statement
    """
    requirement = models.ForeignKey(Requirement, related_name="statements")
    fpr = models.ForeignKey(bmodels.Fingerprint, related_name="+", help_text=_("Fingerprint used to verify the statement"))
    statement = models.TextField(verbose_name=_("Signed statement"), blank=True)
    statement_verified = models.DateTimeField(null=True, help_text=_("When the statement has been verified to have valid wording (NULL if it has not)"))
    uploaded_by = models.ForeignKey(bmodels.Person, null=True, related_name="+", help_text=_("Person who uploaded the statement"))

    def __unicode__(self):
        return "{}:{}".format(self.fpr, self.type)

    @property
    def status(self):
        if self.statement_verified: return "verified"
        if self.statement: return "unverified"
        return "missing"

    def get_key(self):
        from keyring.models import Key
        return Key.objects.get_or_download(self.fpr.fpr)


class Log(models.Model):
    """
    A log entry about anything that happened during a process
    """
    changed_by = models.ForeignKey(bmodels.Person, related_name="+", null=True)
    process = models.ForeignKey(Process, related_name="log")
    is_public = models.BooleanField(default=False)
    logdate = models.DateTimeField(default=now)
    logtext = models.TextField(blank=True, default="")

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
