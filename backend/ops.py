# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.timezone import now
from backend import const
from . import models as bmodels

class Operation(object):
    def __init__(self, audit_author, audit_notes):
        self.audit_author = audit_author
        self.audit_notes = audit_notes


class CreateUser(Operation):
    def __init__(self, audit_author, audit_notes, **kw):
        super(CreateUser, self).__init__(audit_author, audit_notes)
        self.fpr = kw.pop("fpr", None)
        self.kwargs = kw

    def __str__(self):
        return "Create user {}".format(self.kwargs.get("email", "<missing email>"))

    def execute(self):
        p = bmodels.Person.objects.create_user(
            audit_author=self.audit_author,
            audit_notes=self.audit_notes,
            **self.kwargs)
        if self.fpr:
            fpr = p.fingerprints.create(
                fpr=self.fpr,
                is_active=True,
                audit_author=self.audit_author,
                audit_notes=self.audit_notes,
            )


class ChangeStatus(Operation):
    def __init__(self, audit_author, audit_notes, person, status, status_changed=None):
        super(ChangeStatus, self).__init__(audit_author, audit_notes)
        self.person = person
        self.status = status
        self.status_changed = status_changed if status_changed else now()

    def __str__(self):
        return "Change status of {} to {}".format(self.person.lookup_key, self.status)

    def execute(self):
        self.person.status = self.status
        self.person.status_changed = self.status_changed
        self.person.save(
            audit_author=self.audit_author,
            audit_notes=self.audit_notes)


class ChangeFingerprint(Operation):
    def __init__(self, audit_author, audit_notes, person, fpr):
        super(ChangeFingerprint, self).__init__(audit_author, audit_notes)
        self.person = person
        self.fpr = fpr

    def __str__(self):
        return "Change fingerprint of {} to {}".format(self.person.lookup_key, self.fpr)

    def execute(self):
        fpr = self.person.fprs.create(
            fpr=self.fpr, is_active=True,
            audit_author=self.audit_author,
            audit_notes=self.audit_notes)


class CloseOldProcess(Operation):
    def __init__(self, audit_author, audit_notes, process, logtext, logdate=None):
        super(CloseOldProcess, self).__init__(audit_author, audit_notes)
        self.process = process
        self.logtext = logtext
        self.logdate = logdate if logdate else now()

    def execute(self):
        l = bmodels.Log.for_process(self.process, changed_by=self.audit_author, logdate=self.logdate, logtext=self.logtext)
        l.save()
        self.process.progress = const.PROGRESS_DONE
        self.process.is_active = False
        self.process.save()
