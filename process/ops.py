# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.timezone import now
from backend import const
from backend.ops import Operation
from . import models as pmodels
import logging

log = logging.getLogger(__name__)

def ensure_process(val):
    if isinstance(val, pmodels.Process):
        return val
    else:
        return pmodels.Process.objects.get(pk=val)


@Operation.register
class CloseProcess(Operation):
    def __init__(self, audit_author, audit_notes, process, logtext, logdate=None):
        super(CloseProcess, self).__init__(audit_author, audit_notes)
        self.process = ensure_process(process)
        self.logtext = logtext
        self.logdate = logdate if logdate else now()

    def execute(self):
        self.process.add_log(self.audit_author, self.logtext, is_public=True, action="done", logdate=self.logdate)
        self.process.closed = self.logdate
        self.process.save()

    def to_dict(self):
        res = super(CloseProcess, self).to_dict()
        res["process"] = self.process.pk
        res["logtext"] = self.logtext
        res["logdate"] = self.logdate
        return res
