# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.translation import ugettext_lazy as _
from django import forms, http
from django.views.generic import TemplateView, FormView, View
from backend.mixins import VisitorMixin
from backend import const
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

        ctx["people"] = list(people.keys()) if people else None
        ctx["processes"] = processes
        ctx["wikihelp"] = "https://wiki.debian.org/nm.debian.org/Wizard/Advocate"
        return ctx

    def form_valid(self, form):
        return self.render_to_response(self.get_context_data(form=form))


class NewProcess(VisitorMixin, TemplateView):
    template_name = "wizard/newprocess.html"

    def get_context_data(self, **kw):
        ctx = super(NewProcess, self).get_context_data(**kw)
        target = self.kwargs["applying_for"]
        comments = []
        allowed = False

        if target == "dm":
            target_desc = "Become Debian Maintainer"
        elif target == "ga":
            target_desc = "Request guest account"
        elif target == "return":
            target_desc = "Return from Emeritus"
        else:
            target_desc = "Become {}".format(const.ALL_STATUS_DESCS[target])

        if self.visitor:
            whitelist = self.visitor.possible_new_statuses
            if target == "dm":
                if self.visitor.status in (const.STATUS_DM, const.STATUS_DM_GA):
                    comments.append("You are already a Debian Maintainer: problem solved!")
                elif self.visitor.status not in (const.STATUS_DC, const.STATUS_DC_GA):
                    comments.append("You are already a {}.".format(const.ALL_STATUS_DESCS[self.visitor.status]))
                else:
                    allowed = const.STATUS_DM in whitelist or const.STATUS_DM_GA in whitelist
                    if not allowed:
                        comments.append("You cannot start a new process for Debian Maintainer. Did you already start one?")
            elif target == "ga":
                if self.visitor.status not in (const.STATUS_DC, const.STATUS_DM):
                    comments.append("As a {}, you should already have access to porter machines.".format(const.ALL_STATUS_DESCS[self.visitor.status]))
                else:
                    allowed = const.STATUS_DC_GA in whitelist or const.STATUS_DM_GA in whitelist
                    if not allowed:
                        comments.append("You cannot request a guest account. Did you already request it?")
            elif target == "return":
                if self.visitor.status != const.STATUS_EMERITUS_DD:
                    comments.append("You seem to be {}, not an Emeritus DD.".format(const.ALL_STATUS_DESCS[self.visitor.status]))
                else:
                    allowed = True
            else:
                if target == self.visitor.status:
                    comments.append("You are already {}: problem solved!".format(
                        const.ALL_STATUS_DESCS[target]))
                else:
                    allowed = target in whitelist
                    if not allowed:
                        comments.append("You are currently {} and you cannot become {}.".format(
                            const.ALL_STATUS_DESCS[self.visitor.status],
                            const.ALL_STATUS_DESCS[target]))

        ctx["comments"] = comments
        ctx["allowed"] = allowed
        ctx["target_desc"] = target_desc
        return ctx
