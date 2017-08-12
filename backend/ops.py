from django.utils.timezone import now, utc
from backend import const
from process.email import notify_new_dd
from . import models as bmodels
import datetime
import logging
import json

log = logging.getLogger(__name__)


class JSONSerializer(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, datetime.datetime):
            if o.tzinfo: o = o.astimezone(utc)
            return o.strftime("%Y-%m-%d %H:%M:%S")
        elif isinstance(o, datetime.date):
            return o.strftime("%Y-%m-%d")
        elif isinstance(o, bmodels.Person):
            return o.lookup_key
        else:
            return super(JSONSerializer, self).default(o)


def ensure_datetime(val):
    if isinstance(val, datetime.datetime): return val
    val = datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
    val = val.replace(tzinfo=utc)
    return val

def ensure_date(val):
    if isinstance(val, datetime.date): return val
    val = datetime.datetime.strptime(val, "%Y-%m-%d")
    return val.date()

def ensure_person(val):
    if isinstance(val, bmodels.Person):
        return val
    else:
        return bmodels.Person.lookup(val)

def ensure_old_process(val):
    if isinstance(val, bmodels.Process):
        return val
    else:
        return bmodels.Process.objects.get(pk=val)


class Operation(object):
    classes = {}

    def __init__(self, audit_author, audit_notes):
        self.audit_author = ensure_person(audit_author)
        self.audit_notes = audit_notes

    def to_dict(self):
        """
        Returns a dict with all the constructor arguments to recreate this
        operation
        """
        return {
            "audit_author": self.audit_author,
            "audit_notes": self.audit_notes,
        }

    def to_json(self, **kw):
        res = self.to_dict()
        res["Operation"] = self.__class__.__name__
        return json.dumps(res, cls=JSONSerializer, **kw)

    @classmethod
    def register(cls, _class):
        cls.classes[_class.__name__] = _class
        return _class

    @classmethod
    def from_json(cls, encoded):
        import process.ops as pops
        val = json.loads(encoded)
        _class = val.pop("Operation")
        Op = cls.classes[_class]
        return Op(**val)


@Operation.register
class CreateUser(Operation):
    def __init__(self, audit_author, audit_notes, **kw):
        super(CreateUser, self).__init__(audit_author, audit_notes)
        self.fpr = kw.pop("fpr", None)
        for field in ("last_login", "date_joined", "status_changed", "created"):
            if field in kw: kw[field] = ensure_datetime(kw[field])
        if "expires" in kw:
            kw["expires"] = ensure_date(kw["expires"])
        self.kwargs = kw

    def __str__(self):
        return "Create user {}".format(self.kwargs.get("email", "<missing email>"))

    def execute(self):
        p = bmodels.Person.objects.create_user(
            audit_author=self.audit_author,
            audit_notes=self.audit_notes,
            **self.kwargs)
        if self.fpr:
            fpr = p.fprs.create(
                fpr=self.fpr,
                is_active=True,
                audit_author=self.audit_author,
                audit_notes=self.audit_notes,
            )

    def to_dict(self):
        res = super(CreateUser, self).to_dict()
        if self.fpr: res["fpr"] = self.fpr
        res.update(**self.kwargs)
        return res


@Operation.register
class ChangeStatus(Operation):
    def __init__(self, audit_author, audit_notes, person, status, status_changed=None):
        super(ChangeStatus, self).__init__(audit_author, audit_notes)
        self.person = ensure_person(person)
        self.status = status
        self.status_changed = status_changed if status_changed else now()

    def __str__(self):
        return "Change status of {} to {}".format(self.person.lookup_key, self.status)

    def execute(self):
        import process.models as pmodels
        process = pmodels.Process.objects.create(
            person=self.person,
            applying_for=self.status,
            frozen_by=self.audit_author,
            frozen_time=self.status_changed,
            approved_by=self.audit_author,
            approved_time=self.status_changed,
            closed=self.status_changed,
            skip_requirements=True,
        )
        process.add_log(
            changed_by=self.audit_author,
            logtext=self.audit_notes,
            is_public=False,
            action="proc_approve",
            logdate=self.status_changed
        )
        self.person.status = self.status
        self.person.status_changed = self.status_changed
        self.person.save(
            audit_author=self.audit_author,
            audit_notes=self.audit_notes)

    def to_dict(self):
        res = super(ChangeStatus, self).to_dict()
        res["person"] = self.person
        res["status"] = self.status
        res["status_changed"] = self.status_changed
        return res


@Operation.register
class ChangeFingerprint(Operation):
    def __init__(self, audit_author, audit_notes, person, fpr):
        super(ChangeFingerprint, self).__init__(audit_author, audit_notes)
        self.person = ensure_person(person)
        self.fpr = fpr

    def __str__(self):
        return "Change fingerprint of {} to {}".format(self.person.lookup_key, self.fpr)

    def execute(self):
        fpr = self.person.fprs.create(
            fpr=self.fpr, is_active=True,
            audit_author=self.audit_author,
            audit_notes=self.audit_notes)

    def to_dict(self):
        res = super(ChangeFingerprint, self).to_dict()
        res["person"] = self.person
        res["fpr"] = self.fpr
        return res


@Operation.register
class CloseOldProcess(Operation):
    def __init__(self, audit_author, audit_notes, process, logtext, logdate=None):
        super(CloseOldProcess, self).__init__(audit_author, audit_notes)
        self.process = ensure_old_process(process)
        self.logtext = logtext
        self.logdate = logdate if logdate else now()

    def execute(self):
        l = bmodels.Log.for_process(self.process, changed_by=self.audit_author, logdate=self.logdate, logtext=self.logtext)
        l.save()
        self.process.progress = const.PROGRESS_DONE
        self.process.is_active = False
        self.process.save()
        self.process.person.status = self.process.applying_for
        self.process.person.status_changed = self.logdate
        self.process.person.save(audit_author=self.audit_author, audit_notes=self.logtext)
        # Mail leader@debian.org as requested by mehdi via IRC on 2016-07-14
        if self.process.applying_for in (const.STATUS_DD_NU, const.STATUS_DD_U):
            notify_new_dd(self.process)

    def to_dict(self):
        res = super(CloseOldProcess, self).to_dict()
        res["process"] = self.process.pk
        res["logtext"] = self.logtext
        res["logdate"] = self.logdate
        return res
