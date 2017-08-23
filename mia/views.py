from django.utils.translation import ugettext as _
from django import forms, http
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from django.utils.timezone import now
from backend.mixins import VisitorMixin, VisitPersonMixin
from process.mixins import VisitProcessMixin
from backend.models import Person, Fingerprint
from backend import const
import datetime
from . import ops as mops


class Uploaders(VisitorMixin, TemplateView):
    """
    List inactive uploaders
    """
    template_name = "mia/uploaders.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)

        days = int(self.request.GET.get("days", 365 * 2))
        ctx["days"] = days

        # Map each Person to the Fingerprint with the most recent last_upload
        by_person = {}
        for fpr in Fingerprint.objects.filter(person__status=const.STATUS_DD_U).select_related("person"):
            if fpr.last_upload is None: continue
            old = by_person.get(fpr.person)
            if old is None or old.last_upload < fpr.last_upload:
                by_person[fpr.person] = fpr

        today = now().date()
        fprs = []
        for fpr in by_person.values():
            if (today - fpr.last_upload).days < days: continue
            fprs.append(fpr)
        fprs.sort(key=lambda f:f.last_upload)
        ctx["fprs"] = fprs

        ctx["no_fpr"] = Person.objects.filter(status__in=(const.STATUS_DD_NU, const.STATUS_DD_U), fprs__isnull=True).order_by("uid")

        return ctx


class Voters(VisitorMixin, TemplateView):
    """
    List inactive voters
    """
    template_name = "mia/voters.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)

        days = int(self.request.GET.get("days", 365 * 2))
        ctx["days"] = days

        # Map each Person to the Fingerprint with the most recent last_upload
        today = now().date()
        people = []
        for person in Person.objects.filter(status__in=(const.STATUS_DD_U, const.STATUS_DD_NU)):
            if person.last_vote is None:
                last = person.status_changed.date()
            else:
                last = person.last_vote
            if (today - last).days < days: continue
            people.append(person)

        fallback_sort_date = datetime.date(1970, 1, 1)
        people.sort(key=lambda p:(p.last_vote or fallback_sort_date))
        ctx["people"] = people
        return ctx


class MIAPingForm(forms.Form):
    email = forms.CharField(
        required=True,
        label=_("Email introduction"),
        widget=forms.Textarea(attrs=dict(rows=10, cols=80))
    )


class MIAPing(VisitPersonMixin, FormView):
    require_visitor = "admin"
    template_name = "process/miaping.html"
    form_class = MIAPingForm

    def get_initial(self):
        initial = super().get_initial()
        initial["email"] = """
We are currently in the process of checking the activity of accounts
in the Debian LDAP, after the MIA team has contacted you already.
""".strip()
        return initial

    def form_valid(self, form):
        op = mops.WATPing(audit_author=self.visitor, person=self.person, text=form.cleaned_data["email"])
        op.execute(self.request)
        return redirect(op._process.get_absolute_url())


class MIARemoveForm(forms.Form):
    email = forms.CharField(
        required=True,
        label=_("Email introduction"),
        widget=forms.Textarea(attrs=dict(rows=10, cols=80))
    )


class MIARemove(VisitProcessMixin, FormView):
    require_visitor = "admin"
    template_name = "process/miaremove.html"
    form_class = MIARemoveForm

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["status"] = self.compute_process_status()
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        initial["email"] = """
We've sent the last warning email on {:%Y-%m-%d}, with no response.
""".format(self.process.started).strip()
        return initial

    def form_valid(self, form):
        op = mops.WATRemove(audit_author=self.visitor, process=self.process, text=form.cleaned_data["email"])
        op.execute(self.request)
        return redirect(self.process.get_absolute_url())
