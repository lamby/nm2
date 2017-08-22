from django.utils.timezone import now
from backend import const
import backend.ops as op
from .email import notify_new_dd
from . import models as pmodels
import logging

log = logging.getLogger(__name__)


class ProcessField(op.OperationField):
    def validate(self, val):
        if val is None: return val
        if isinstance(val, pmodels.Process):
            return val
        else:
            return pmodels.Process.objects.get(pk=val)

    def to_json(self, val):
        if val is None: return val
        return val.pk


class RequirementField(op.OperationField):
    def validate(self, val):
        if val is None: return val
        if isinstance(val, pmodels.Requirement):
            return val
        else:
            return pmodels.Requirement.objects.get(pk=val)

    def to_json(self, val):
        if val is None: return val
        return val.pk


@op.Operation.register
class LogStatement(op.Operation):
    is_public = op.BooleanField()
    process = ProcessField(null=True)
    requirement = RequirementField(null=True)

    def __init__(self, **kw):
        if kw.get("process") is None and kw.get("requirement") is None:
            raise TypeError("one of `process` or `requirement` must be set in a LogStatement operation")
        super().__init__(**kw)
        self._log_entry = None

    def execute(self):
        if self.process is not None:
            target = self.process
        else:
            target = self.requirement
        self._log_entry = target.add_log(self.audit_author, self.audit_notes, is_public=self.is_public, logdate=self.audit_time)

    def notify(self, request=None):
        from .email import notify_new_log_entry
        notify_new_log_entry(self._log_entry, request)


@op.Operation.register
class ProcessCreate(op.Operation):
    person = op.PersonField()
    applying_for = op.PersonStatusField()
    creator = op.PersonField()

    def __init__(self, **kw):
        creator = kw.get("creator")
        if creator is None:
            kw["creator"] = creator =  kw["person"]
        kw.setdefault("audit_author", creator)
        kw.setdefault("audit_notes", "Process created")
        super().__init__(**kw)
        self._process = None

    def execute(self):
        self._process = pmodels.Process.objects.create(self.person, self.applying_for)
        self._process.add_log(self.audit_author, self.audit_notes, is_public=True, logdate=self.audit_time)

    def notify(self, request=None):
        from .email import notify_new_process
        notify_new_process(self._process, request)

    @property
    def new_process(self):
        return self._process


@op.Operation.register
class RequirementApprove(op.Operation):
    requirement = RequirementField()

    def execute(self):
        self.requirement.approved_by = self.audit_author
        self.requirement.approved_time = self.audit_time
        self.requirement.save()
        self.requirement.add_log(self.audit_author, self.audit_notes, action="req_approve", is_public=True, logdate=self.audit_time)


@op.Operation.register
class RequirementUnapprove(op.Operation):
    requirement = RequirementField()

    def execute(self):
        self.requirement.approved_by = None
        self.requirement.approved_time = None
        self.requirement.save()
        self.requirement.add_log(self.audit_author, self.audit_notes, action="req_unapprove", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessFreeze(op.Operation):
    process = ProcessField()

    def execute(self):
        self.process.frozen_by = self.audit_author
        self.process.frozen_time = self.audit_time
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_freeze", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessUnfreeze(op.Operation):
    process = ProcessField()

    def execute(self):
        self.process.frozen_by = None
        self.process.frozen_time = None
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_unfreeze", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessApprove(op.Operation):
    process = ProcessField()
    approved_time = op.DatetimeField(null=True, default=now)

    def execute(self):
        self.process.approved_by = self.audit_author
        self.process.approved_time = self.audit_time
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_approve", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessUnapprove(op.Operation):
    process = ProcessField()

    def execute(self):
        self.process.approved_by = None
        self.process.approved_time = None
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_unapprove", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessClose(op.Operation):
    process = ProcessField()

    def execute(self):
        self.process.add_log(self.audit_author, self.audit_notes, is_public=True, action="done", logdate=self.audit_time)
        self.process.closed = self.audit_time
        self.process.save()
        self.process.person.status = self.process.applying_for
        self.process.person.status_changed = self.audit_time
        self.process.person.save(audit_author=self.audit_author, audit_notes=self.audit_notes)
        # Mail leader@debian.org as requested by mehdi via IRC on 2016-07-14
        if self.process.applying_for in (const.STATUS_DD_NU, const.STATUS_DD_U):
            notify_new_dd(self.process)
