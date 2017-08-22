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
        self._process.add_log(self.audit_author, self.audit_notes, is_public=True)

    def notify(self, request=None):
        from .email import notify_new_process
        notify_new_process(self._process, request)

    @property
    def new_process(self):
        return self._process


#@op.Operation.register
#class ProcessApprove(op.Operation):
#    def __init__(self, process, person, logtext=None):
#        if logtext is None: logtext = "Approved"
#        super().__init__(person, logtext)
#        self.process = process
#
#    def to_dict(self):
#        res = super().to_dict()
#        res["process"] = self.process
#        return res
#
#    def execute(self):
#        pass
#

@op.Operation.register
class ProcessClose(op.Operation):
    process = ProcessField()
    logdate = op.DatetimeField(null=True, default=now)

    def execute(self):
        self.process.add_log(self.audit_author, self.audit_notes, is_public=True, action="done", logdate=self.logdate)
        self.process.closed = self.logdate
        self.process.save()
        self.process.person.status = self.process.applying_for
        self.process.person.status_changed = self.logdate
        self.process.person.save(audit_author=self.audit_author, audit_notes=self.audit_notes)
        # Mail leader@debian.org as requested by mehdi via IRC on 2016-07-14
        if self.process.applying_for in (const.STATUS_DD_NU, const.STATUS_DD_U):
            notify_new_dd(self.process)
