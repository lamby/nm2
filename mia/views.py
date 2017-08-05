from django.utils.translation import ugettext as _
from django.views.generic import TemplateView
from django.utils.timezone import now
from backend.mixins import VisitorMixin
from backend.models import Person, Fingerprint
from backend import const
import datetime


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