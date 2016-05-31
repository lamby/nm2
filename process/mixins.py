# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404
from backend.mixins import VisitPersonMixin
from . import models as pmodels


class VisitProcessMixin(VisitPersonMixin):
    """
    Visit a person process. Adds self.person, self.process and self.vperms with
    the permissions the visitor has over the person
    """
    def get_person(self):
        return self.process.person

    def get_vperms(self):
        return self.process.permissions_of(self.visitor)

    def get_process(self):
        return get_object_or_404(pmodels.Process, pk=self.kwargs["pk"])

    def load_objects(self):
        self.process = self.get_process()
        super(VisitProcessMixin, self).load_objects()

    def get_context_data(self, **kw):
        ctx = super(VisitProcessMixin, self).get_context_data(**kw)
        ctx["process"] = self.process
        return ctx
