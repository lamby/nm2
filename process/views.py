# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.utils.timezone import now
from django.db import transaction
from backend.mixins import VisitorMixin, VisitPersonMixin
from .mixins import VisitProcessMixin
import datetime
from . import models as pmodels


class List(VisitorMixin, TemplateView):
    """
    List active and recently closed processes
    """
    template_name = "process/list.html"

    def get_context_data(self, **kw):
        ctx = super(List, self).get_context_data(**kw)
        ctx["current"] = pmodels.Process.objects.filter(closed__isnull=True).order_by("applying_for")
        cutoff = now() - datetime.timedelta(days=30)
        ctx["last"] = pmodels.Process.objects.filter(closed__gte=cutoff).order_by("-closed")
        return ctx


class Create(VisitPersonMixin, View):
    """
    Create a new process
    """
    def post(self, request, *args, **kw):
        applying_for = kw["applying_for"]
        # TODO: ensure visitor can create processes for person
        # TODO: ensure that applying_for is a valid new process for person
        with transaction.atomic():
            p = pmodels.Process.objects.create(self.person, applying_for)
            p.log(self.visitor, "Process create", is_public=True)
        return redirect(p.get_absolute_url())


class Show(VisitProcessMixin, TemplateView):
    pass
# TODO: show process

# TODO: update requirement
