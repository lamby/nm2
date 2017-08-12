from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404
from backend.mixins import VisitPersonMixin
from . import models as pmodels

def compute_process_status(process, visitor, visit_perms=None):
    """
    Return a dict with the process status:
    {
        "requirements_ok": [list of Requirement],
        "requirements_missing": [list of Requirement],
        "log_first": Log,
        "log_last": Log,
    }
    """
    from process.models import REQUIREMENT_TYPES_DICT
    rok = []
    rnok = []
    requirements = {}
    for r in process.requirements.all():
        if r.approved_by:
            rok.append(r)
        else:
            rnok.append(r)
        requirements[r.type] = r

    # Compute the list of advocates
    adv = requirements.get("advocate", None)
    advocates = set()
    if adv is not None:
        for s in adv.statements.all():
            advocates.add(s.uploaded_by)

    log = process.log.order_by("logdate").select_related("changed_by", "requirement")
    if not (visitor is not None and visitor.is_admin) and (not visit_perms or "view_private_log" not in visit_perms):
        from django.db.models import Q
        log = log.filter(Q(is_public=True) | Q(changed_by=visitor))
    log = list(log)

    am_assignment = process.current_am_assignment

    if process.closed:
        summary = "Closed"
    elif process.frozen_by:
        if process.approved_by:
            summary = "Approved"
        else:
            summary = "Frozen for review"
    elif process.approved_by:
        summary = "Approved"
    elif not rnok:
        summary = "Waiting for review"
    elif am_assignment is not None:
        if am_assignment.paused:
            summary = "AM Hold"
        else:
            summary = "AM"
    else:
        summary = "Collecting requirements"

    return {
        "requirements": requirements,
        "requirements_sorted": sorted(list(requirements.values()), key=lambda x: REQUIREMENT_TYPES_DICT[x.type].sort_order),
        "requirements_ok": sorted(rok, key=lambda x: REQUIREMENT_TYPES_DICT[x.type].sort_order),
        "requirements_missing": sorted(rnok, key=lambda x: REQUIREMENT_TYPES_DICT[x.type].sort_order),
        "log_first": log[0] if log else None,
        "log_last": log[-1] if log else None,
        "log": log,
        "advocates": sorted(advocates, key=lambda x:x.uid),
        "summary": summary,
    }


class VisitProcessMixin(VisitPersonMixin):
    """
    Visit a person process. Adds self.person, self.process and
    self.visit_perms with the permissions the visitor has over the person
    """
    def get_person(self):
        return self.process.person

    def get_visit_perms(self):
        return self.process.permissions_of(self.visitor)

    def get_process(self):
        return get_object_or_404(pmodels.Process.objects.select_related("person"), pk=self.kwargs["pk"])

    def load_objects(self):
        self.process = self.get_process()
        super(VisitProcessMixin, self).load_objects()

    def get_context_data(self, **kw):
        ctx = super(VisitProcessMixin, self).get_context_data(**kw)
        ctx["process"] = self.process
        ctx["wikihelp"] = "https://wiki.debian.org/nm.debian.org/Process"
        return ctx

    def compute_process_status(self):
        return compute_process_status(self.process, self.visitor, self.visit_perms)
