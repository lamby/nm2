from django.utils.timezone import now
from django.urls import reverse
from django.conf import settings
import requests
import datetime
import re
import os
from backend import const
from backend.shortcuts import build_absolute_uri
import backend.ops as op
import process.ops as pops
from backend import models as bmodels
from process import models as pmodels
import logging

log = logging.getLogger(__name__)

@op.Operation.register
class WATPing(op.Operation):
    person = op.PersonField()
    text = op.StringField()

    def __init__(self, **kw):
        kw.setdefault("audit_notes", "Sent WAT ping email")
        super().__init__(**kw)
        self._process = None

    def _execute(self):
        try:
            self._process = pmodels.Process.objects.get(person=self.person, applying_for=const.STATUS_EMERITUS_DD, closed_by__isnull=True)
        except pmodels.Process.DoesNotExist:
            self._process = pmodels.Process.objects.create(self.person, const.STATUS_EMERITUS_DD)
            self._process.hide_until = self.audit_time + datetime.timedelta(days=30)
            self._process.save()
        self._process.add_log(self.audit_author, self.audit_notes, is_public=True, logdate=self.audit_time)

    def _mock_execute(self):
        self._process = pmodels.Process(self.person, const.STATUS_EMERITUS_DD)
        self._process.hide_until = self.audit_time + datetime.timedelta(days=30)
        self._process.pk = 0

    def notify(self, request=None):
        import process.views
        ctx = {
            "visitor": self.audit_author,
            "person": self.person,
            "process": self._process,
            "process_url": build_absolute_uri(self._process.get_absolute_url(), request),
            "emeritus_url": process.views.Emeritus.get_nonauth_url(self.person, request),
            "cancel_url": build_absolute_uri(reverse("process_cancel", args=[self._process.pk]), request),
            "deadline": self._process.hide_until,
            "text": self.text,
        }

        from django.template.loader import render_to_string
        body = render_to_string("mia/mia_ping_email.txt", ctx).strip()

        mia_addr = "mia-{}@qa.debian.org".format(self.person.uid)

        from process.email import build_django_message
        msg = build_django_message(
            from_email=("Debian MIA team", "wat@debian.org"),
            to=[self.person.email],
            cc=[self._process.archive_email],
            bcc=[mia_addr, "wat@debian.org"],
            subject="WAT: Are you still active in Debian? ({})".format(self.person.uid),
            headers={
                "X-MIA-Summary": "out, wat; WAT by nm.d.o",
            },
            body=body)
        msg.send()


@op.Operation.register
class WATRemove(op.Operation):
    process = pops.ProcessField()
    text = op.StringField()

    def __init__(self, **kw):
        kw.setdefault("audit_notes", "Started remove process")
        super().__init__(**kw)

    def _execute(self):
        self.process.applying_for = const.STATUS_REMOVED_DD
        self.process.hide_until = self.audit_time + datetime.timedelta(days=15)
        self.process.save()

        requirement = self.process.requirements.get(type="intent")

        statement = pmodels.Statement(requirement=requirement)
        statement.uploaded_by = self.audit_author
        statement.uploaded_time = self.audit_time
        statement.statement = self.text
        statement.save()
        requirement.add_log(self.audit_author, self.audit_notes, True, action="add_statement", logdate=self.audit_time)

        requirement.approved_by = self.audit_author
        requirement.approved_time = self.audit_time
        requirement.save()
        requirement.add_log(self.audit_author, "Requirement automatically satisfied", True, action="req_approve", logdate=self.audit_time)

    def notify(self, request=None):
        import process.views
        ctx = {
            "visitor": self.audit_author,
            "person": self.process.person,
            "process": self.process,
            "process_url": build_absolute_uri(self.process.get_absolute_url(), request),
            "emeritus_url": process.views.Emeritus.get_nonauth_url(self.process.person, request),
            "cancel_url": build_absolute_uri(reverse("process_cancel", args=[self.process.pk]), request),
            "deadline": self.process.hide_until,
            "text": self.text,
        }

        from django.template.loader import render_to_string
        body = render_to_string("mia/mia_remove_email.txt", ctx).strip()

        mia_addr = "mia-{}@qa.debian.org".format(self.process.person.uid)

        from process.email import build_django_message
        msg = build_django_message(
            from_email=("Debian MIA team", "wat@debian.org"),
            to=["debian-private@lists.debian.org"],
            cc=[self.process.person.email, self.process.archive_email],
            bcc=[mia_addr, "wat@debian.org"],
            subject="Debian Project member MIA: {} ({})".format(
                self.process.person.fullname, self.process.person.uid
            ),
            headers={
                "X-MIA-Summary": "out; public removal pre-announcement",
            },
            body=body)
        msg.send()
