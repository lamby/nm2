from django.utils.timezone import now
from django.conf import settings
import requests
import datetime
import re
import os
from backend import const
from backend.shortcuts import build_absolute_uri
import backend.ops as op
from backend import models as bmodels
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


class StatementField(op.OperationField):
    def validate(self, val):
        if val is None: return val
        if isinstance(val, pmodels.Statement):
            return val
        else:
            return pmodels.Statement.objects.get(pk=val)

    def to_json(self, val):
        if val is None: return val
        return val.pk


class AMAssignmentField(op.OperationField):
    def validate(self, val):
        if val is None: return val
        if isinstance(val, pmodels.AMAssignment):
            return val
        else:
            return pmodels.AMAssignment.objects.get(pk=val)

    def to_json(self, val):
        if val is None: return val
        return val.pk


@op.Operation.register
class ProcessAddLogEntry(op.Operation):
    is_public = op.BooleanField()
    process = ProcessField(null=True)
    requirement = RequirementField(null=True)

    def __init__(self, **kw):
        if kw.get("process") is None and kw.get("requirement") is None:
            raise TypeError("one of `process` or `requirement` must be set in a ProcessAddLogEntry operation")
        super().__init__(**kw)
        self._log_entry = None

    def _execute(self):
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

    def _execute(self):
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

    def _execute(self):
        self.requirement.approved_by = self.audit_author
        self.requirement.approved_time = self.audit_time
        self.requirement.save()
        self.requirement.add_log(self.audit_author, self.audit_notes, action="req_approve", is_public=True, logdate=self.audit_time)


@op.Operation.register
class RequirementUnapprove(op.Operation):
    requirement = RequirementField()

    def _execute(self):
        self.requirement.approved_by = None
        self.requirement.approved_time = None
        self.requirement.save()
        self.requirement.add_log(self.audit_author, self.audit_notes, action="req_unapprove", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessFreeze(op.Operation):
    process = ProcessField()

    def _execute(self):
        self.process.frozen_by = self.audit_author
        self.process.frozen_time = self.audit_time
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_freeze", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessUnfreeze(op.Operation):
    process = ProcessField()

    def _execute(self):
        self.process.frozen_by = None
        self.process.frozen_time = None
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_unfreeze", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessApprove(op.Operation):
    process = ProcessField()
    approved_time = op.DatetimeField(null=True, default=now)

    def _execute(self):
        self.process.approved_by = self.audit_author
        self.process.approved_time = self.audit_time
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_approve", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessUnapprove(op.Operation):
    process = ProcessField()

    def _execute(self):
        self.process.approved_by = None
        self.process.approved_time = None
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_unapprove", is_public=True, logdate=self.audit_time)


@op.Operation.register
class ProcessClose(op.Operation):
    process = ProcessField()

    def _execute(self):
        self.process.add_log(self.audit_author, self.audit_notes, is_public=True, action="done", logdate=self.audit_time)
        self.process.closed_by = self.audit_author
        self.process.closed_time = self.audit_time
        self.process.save()
        self.process.person.status = self.process.applying_for
        self.process.person.status_changed = self.audit_time
        self.process.person.save(audit_author=self.audit_author, audit_notes=self.audit_notes)
        # Mail leader@debian.org as requested by mehdi via IRC on 2016-07-14
        if self.process.applying_for in (const.STATUS_DD_NU, const.STATUS_DD_U):
            from .email import notify_new_dd
            notify_new_dd(self.process)


@op.Operation.register
class ProcessAssignAM(op.Operation):
    process = ProcessField()
    am = op.AMField()

    def __init__(self, **kw):
        if "audit_notes" not in kw:
            kw["audit_notes"] = "Assigned AM {}".format(kw["am"].person.lookup_key)
        super().__init__(**kw)
        self._assignment = None

    def _execute(self):
        requirement = self.process.requirements.get(type="am_ok")
        current = self.process.current_am_assignment
        if current is not None:
            current.unassigned_by = self.audit_author
            current.unassigned_time = self.audit_time
            current.save()
            requirement.add_log(self.audit_author, "Unassigned AM {}".format(current.am.person.lookup_key), is_public=True, action="unassign_am", logdate=self.audit_time)

        self._assignment = pmodels.AMAssignment.objects.create(
            process=self.process,
            am=self.am,
            assigned_by=self.audit_author,
            assigned_time=self.audit_time)

        if not self.am.is_am:
            self.am.is_am = True
            self.am.save()

        requirement.add_log(self.audit_author, self.audit_notes, is_public=True, action="assign_am", logdate=self.audit_time)

    def notify(self, request=None):
        from .email import notify_am_assigned
        notify_am_assigned(self._assignment, request=request)


@op.Operation.register
class ProcessUnassignAM(op.Operation):
    assignment = AMAssignmentField()

    def __init__(self, **kw):
        if "audit_notes" not in kw:
            kw["audit_notes"] = "Unassigned AM {}".format(kw["assignment"].am.person.uid)
        super().__init__(**kw)

    def _execute(self):
        requirement = self.assignment.process.requirements.get(type="am_ok")
        self.assignment.unassigned_by = self.audit_author
        self.assignment.unassigned_time = self.audit_time
        self.assignment.save()
        requirement.add_log(self.audit_author, self.audit_notes, is_public=True, action="unassign_am", logdate=self.audit_time)


@op.Operation.register
class ProcessStatementAdd(op.Operation):
    requirement = RequirementField()
    statement = op.StringField()

    def __init__(self, **kw):
        kw.setdefault("audit_notes", "Added a new statement")
        super().__init__(**kw)
        self._statement = None

    def _execute(self):
        self._statement = pmodels.Statement(requirement=self.requirement, fpr=self.audit_author.fingerprint)
        self._statement.uploaded_by = self.audit_author
        self._statement.uploaded_time = self.audit_time
        self._statement.statement = self.statement
        self._statement.save()

        self.requirement.add_log(self.audit_author, self.audit_notes, True, action="add_statement", logdate=self.audit_time)

        # Check if the requirement considers itself satisfied now, and
        # auto-mark approved accordingly
        status = self.requirement.compute_status()
        if status["satisfied"]:
            try:
                robot = bmodels.Person.objects.get(username="__housekeeping__")
            except bmodels.Person.DoesNotExist:
                robot = self.audit_author
            self.requirement.approved_by = robot
            self.requirement.approved_time = self.audit_time
        else:
            self.requirement.approved_by = None
            self.requirement.approved_time = None
        self.requirement.save()

        if self.requirement.approved_by:
            self.requirement.add_log(self.requirement.approved_by, "New statement received, the requirement seems satisfied", True, action="req_approve", logdate=self.audit_time)

    def notify(self, request=None):
        if self.requirement.type not in ("intent", "advocate", "am_ok"):
            return
        from .email import notify_new_statement
        notify_new_statement(self._statement, request=request, cc_nm=(self.requirement.type=="am_ok"), notify_ml="newmaint")


@op.Operation.register
class ProcessStatementRemove(op.Operation):
    statement = StatementField()

    def __init__(self, **kw):
        kw.setdefault("audit_notes", "Removed a statement")
        super().__init__(**kw)

    def _execute(self):
        self.statement.requirement.add_log(self.audit_author, self.audit_notes, True, action="del_statement", logdate=self.audit_time)
        self.statement.delete()


@op.Operation.register
class ProcessApproveRT(op.Operation):
    class RTError(Exception):
        def __init__(self, msg, rt_lines):
            super().__init__(msg)
            self.rt_lines = rt_lines

    process = ProcessField()
    rt_id = op.StringField(null=True, default="ticket/new")
    rt_queue = op.StringField(null=True)
    rt_requestor = op.StringField(null=True)
    rt_subject = op.StringField(null=True)
    rt_cc = op.StringField(null=True)
    rt_text = op.StringField(null=True)

    def __init__(self, **kw):
        kw.setdefault("audit_notes", "Process approved")
        super().__init__(**kw)
        only_guest_account = self.only_needs_guest_account(self.process)

        if only_guest_account:
            self.set_null_field("rt_queue", "DSA - Incoming")
            self.set_null_field("rt_subject", "Guest account on porter machines for {}".format(self.process.person.fullname))
        else:
            self.set_null_field("rt_queue", "Keyring")
            self.set_null_field("rt_subject", "{} to become {}".format(self.process.person.fullname, const.ALL_STATUS_DESCS[self.process.applying_for]))

        cc = [self.process.person.email, self.process.archive_email]
        if self.process.applying_for == "dm":
            self.set_null_field("rt_requestor", "nm@debian.org")
            cc.append("nm@debian.org")
        else:
            self.set_null_field("rt_requestor", "da-manager@debian.org")
            cc.append("da-manager@debian.org")
        self.set_null_field("rt_cc", ", ".join(cc))

    @classmethod
    def only_needs_guest_account(cls, process):
        if process.person.status == const.STATUS_DC:
            if process.applying_for == const.STATUS_DC_GA:
                return True
        elif process.person.status == const.STATUS_DM:
            if process.applying_for == const.STATUS_DM_GA:
                return True
        return False

    def _execute(self):
        # Build RT API request
        # See https://rt-wiki.bestpractical.com/wiki/REST
        lines = []
        lines.append("id: " + self.rt_id)
        lines.append("Queue: " + self.rt_queue)
        lines.append("Requestor: " + self.rt_requestor)
        lines.append("Subject: " + self.rt_subject)
        lines.append("Cc: " + self.rt_cc)
        lines.append("Text:")
        for line in self.rt_text.splitlines():
            lines.append(" " + line)

        # Submit RT API request
        args = {"data": { "content": "\n".join(lines) } }

        bundle="/etc/ssl/ca-debian/ca-certificates.crt"
        if os.path.exists(bundle):
            args["verify"] = bundle

        rt_user = getattr(settings, "RT_USER", None)
        rt_pass = getattr(settings, "RT_PASS", None)
        if rt_user is not None and rt_pass is not None:
            args["params"] = { "user": rt_user, "pass": rt_pass }

        res = requests.post("https://rt.debian.org/REST/1.0/ticket/new", **args)
        res.raise_for_status()

        # Validate the RT result
        res_lines = res.text.splitlines()
        ver, status, text = res_lines[0].split(None, 2)

        if int(status) != 200:
            raise self.RTError("RT status code is not 200", res_lines)

        mo = re.match("# Ticket (\d+) created.", res_lines[2])
        if not mo:
            raise self.RTError("Could not find ticket number is response", res_lines)

        # Update the process
        self.process.rt_ticket = int(mo.group(1))
        self.process.rt_request = self.rt_text
        self.process.approved_by = self.audit_author
        self.process.approved_time = self.audit_time
        self.process.save()
        self.process.add_log(self.audit_author, self.audit_notes, action="proc_approve", is_public=True, logdate=self.audit_time)

    def notify(self, request=None):
        from process.email import _to_django_addr
        from django.core.mail import EmailMessage

        if self.process.applying_for in (const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD):
            if self.process.applying_for == const.STATUS_EMERITUS_DD:
                mia_summary = "in, retired; emeritus via nm.d.o"
            elif self.process.applying_for == const.STATUS_REMOVED_DD:
                mia_summary = "in, removed; removed via nm.d.o"
            msg = EmailMessage(
                from_email=_to_django_addr(self.audit_author),
                to=["mia-{}@qa.debian.org".format(self.process.person.uid)],
                cc=[self.process.archive_email],
                subject=self.rt_subject,
                body=self.rt_text,
                headers={"X-MIA-Summary": mia_summary},
            )
            msg.send()


@op.Operation.register
class RequestEmeritus(op.Operation):
    person = op.PersonField()
    statement = op.StringField()

    def __init__(self, **kw):
        kw.setdefault("audit_notes", "Requested to become emeritus")
        super().__init__(**kw)
        self._statement = None

    def _execute(self):
        try:
            process = pmodels.Process.objects.get(person=self.person, applying_for__in=(const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD))
        except pmodels.Process.DoesNotExist:
            process = pmodels.Process.objects.create(self.person, const.STATUS_EMERITUS_DD)
            process.add_log(self.audit_author, self.audit_notes, is_public=True, logdate=self.audit_time)

        if process.applying_for == const.STATUS_REMOVED_DD:
            raise RuntimeError("emeritus process is now a process for account removal: please contact wat@debian.org")

        requirement = process.requirements.get(type="intent")

        statement = pmodels.Statement(requirement=requirement)
        statement.uploaded_by = self.audit_author
        statement.uploaded_time = self.audit_time
        statement.statement = self.statement
        statement.save()
        requirement.add_log(self.audit_author, "Added a statement", True, action="add_statement", logdate=self.audit_time)

        requirement.approved_by = self.audit_author
        requirement.approved_time = self.audit_time
        requirement.save()
        requirement.add_log(self.audit_author, "Requirement automatically approved", True, action="req_approve", logdate=self.audit_time)

        process.hide_until = self.audit_time + datetime.timedelta(days=5)
        process.save()

        self._statement = statement

    def notify(self, request=None):
        # See /srv/qa.debian.org/mia/README
        from .email import notify_new_statement
        return notify_new_statement(self._statement, request=request, cc_nm=False, notify_ml="private", mia="in, retired; emeritus via nm.d.o")

    def _mock_execute(self, request=None):
        try:
            process = pmodels.Process.objects.get(person=self.person, applying_for__in=(const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD))
            requirement = process.requirements.get(type="intent")
        except pmodels.Process.DoesNotExist:
            process = pmodels.Process(self.person, const.STATUS_EMERITUS_DD)
            process.pk = 1
            requirement = pmodels.Requirement(process=process, type="ident")
            requirement.pk = 2

        self._statement = pmodels.Statement(requirement=requirement, uploaded_by=self.audit_author, uploaded_time=self.audit_time, statement=self.statement)
        self._statement.pk = 3


@op.Operation.register
class ProcessCancel(op.Operation):
    process = ProcessField()
    is_public = op.BooleanField()
    statement = op.StringField()

    def __init__(self, **kw):
        kw.setdefault("audit_notes", "Process canceled")
        super().__init__(**kw)

    def _execute(self):
        self.process.add_log(self.audit_author, self.statement, action="proc_close", is_public=self.is_public, logdate=self.audit_time)
        self.process.closed_by = self.audit_author
        self.process.closed_time = self.audit_time
        self.process.hide_until = None
        self.process.save()


@op.Operation.register
class ProcessCancelEmeritus(ProcessCancel):
    def notify(self, request=None):
        from .email import build_django_message

        process = self.process

        url = build_absolute_uri(process.get_absolute_url(), request)

        body = """{op.statement}

{op.audit_author.fullname} (via nm.debian.org)
"""
        body += "-- \n"
        body += "{url}\n"
        body = body.format(op=self, url=url)

        cc = [process.person, process.archive_email]
        if self.is_public:
            subject = "{}: new public log entry".format(process.person.fullname)
        else:
            subject = "{}: new private log entry".format(process.person.fullname)

        msg = build_django_message(
            self.audit_author,
            to="nm@debian.org",
            cc=cc,
            bcc=["mia-{}@qa.debian.org".format(process.person.uid)],
            subject=subject,
            headers={
                # See /srv/qa.debian.org/mia/README
                "X-MIA-Summary": "in, ok; still active via nm.d.o",
            },
            body=body)
        msg.send()
