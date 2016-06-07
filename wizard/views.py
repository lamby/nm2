# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _
from django import forms, http
from django.views.generic import TemplateView, FormView, View
from backend.mixins import VisitorMixin
import backend.models as bmodels
import process.models as pmodels
from collections import defaultdict, OrderedDict


class PersonForm(forms.Form):
    person = forms.CharField(label=_("Person"), required=False)


class Advocate(VisitorMixin, FormView):
    template_name = "wizard/advocate.html"
    form_class = PersonForm

    def get_context_data(self, **kw):
        from django.db.models import Q
        ctx = super(Advocate, self).get_context_data(**kw)
        people = None
        processes = None
        if hasattr(ctx["form"], "cleaned_data"):
            person = ctx["form"].cleaned_data["person"]
            if person:
                query = (Q(username__icontains=person) |
                         Q(cn__icontains=person) | Q(mn__icontains=person) |
                         Q(sn__icontains=person) | Q(email__icontains=person) |
                         Q(uid__icontains=person) |
                         Q(fprs__fpr__icontains=person))

                people = OrderedDict()
                for p in bmodels.Person.objects.filter(query).order_by("uid", "cn"):
                    people[p] = p

            if people:
                processes = OrderedDict()
                for process in pmodels.Process.objects.filter(closed__isnull=True).order_by("person__uid", "person__cn", "applying_for"):
                    person = people.pop(process.person, None)
                    if person is None: continue
                    try:
                        processes[process] = process.requirements.get(type="advocate").get_absolute_url()
                    except pmodels.Process.DoesNotExist:
                        processes[process] = None

        ctx["people"] = list(people.keys())
        ctx["processes"] = processes
        ctx["wikihelp"] = "https://wiki.debian.org/nm.debian.org/Wizard/Advocate"
        return ctx

    def form_valid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
