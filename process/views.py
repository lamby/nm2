from django.utils.translation import ugettext as _
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.utils.timezone import now
from django.db import transaction
from django import forms, http
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.urls import reverse, reverse_lazy
from collections import OrderedDict
from rest_framework import viewsets
from backend.shortcuts import build_absolute_uri
from backend.mixins import VisitorMixin, VisitPersonMixin, TokenAuthMixin
from backend import const
import backend.models as bmodels
from .mixins import VisitProcessMixin, RequirementMixin, StatementMixin
import datetime
import re
import json
import os
import requests
from six.moves import shlex_quote
from . import models as pmodels
from .forms import StatementForm
from .serializers import ProcessSerializer
from . import ops as pops


class ProcessViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Export process information
    """
    queryset = pmodels.Process.objects.filter(closed__isnull=True).order_by("started")
    serializer_class = ProcessSerializer


class List(VisitorMixin, TemplateView):
    """
    List active and recently closed processes
    """
    template_name = "process/list.html"

    def get_context_data(self, **kw):
        ctx = super(List, self).get_context_data(**kw)
        ctx["current"] = pmodels.Process.objects.filter(closed__isnull=True).order_by("applying_for").select_related("person")
        cutoff = now() - datetime.timedelta(days=30)
        ctx["last"] = pmodels.Process.objects.filter(closed__gte=cutoff).order_by("-closed").select_related("person")
        return ctx


class Create(VisitPersonMixin, FormView):
    """
    Create a new process
    """
    require_visit_perms = "request_new_status"
    template_name = "process/create.html"

    def get_context_data(self, **kw):
        ctx = super(Create, self).get_context_data(**kw)
        current = []
        current.extend(pmodels.Process.objects.filter(person=self.person, closed__isnull=True))
        ctx["current"] = current
        ctx["wikihelp"] = "https://wiki.debian.org/nm.debian.org/Process/Start"
        return ctx

    def get_form_class(self):
        whitelist = self.person.possible_new_statuses
        choices = [(x.tag, x.ldesc) for x in const.ALL_STATUS if x.tag in whitelist]
        if not choices: raise PermissionDenied
        class Form(forms.Form):
            applying_for = forms.ChoiceField(label=_("Apply for status"), choices=choices, required=True)
        return Form

    def form_valid(self, form):
        applying_for = form.cleaned_data["applying_for"]
        if applying_for == const.STATUS_EMERITUS_DD:
            return redirect(reverse("process_emeritus", args=[self.person.lookup_key]))

        op = pops.ProcessCreate(person=self.person, applying_for=applying_for, audit_author=self.visitor)
        op.execute(self.request)

        return redirect(op.new_process.get_absolute_url())


class Show(VisitProcessMixin, TemplateView):
    """
    Show a process
    """
    template_name = "process/show.html"

    def get_context_data(self, **kw):
        ctx = super(Show, self).get_context_data(**kw)
        ctx["status"] = self.compute_process_status()
        return ctx


class AddProcessLog(VisitProcessMixin, View):
    """
    Add an entry to the process or requirement log
    """
    @transaction.atomic
    def post(self, request, *args, **kw):
        logtext = request.POST.get("logtext", "").strip()
        action = request.POST.get("add_action", "undefined")
        req_type = request.POST.get("req_type", None)
        is_public = True

        if req_type:
            requirement = get_object_or_404(pmodels.Requirement, process=self.process, type=req_type)
            target = requirement
        else:
            requirement = None
            target = self.process

        visit_perms = target.permissions_of(self.visitor)

        op = None
        if action in ("log_private", "log_public"):
            if "add_log" not in visit_perms: raise PermissionDenied
            if logtext:
                op_args = {}
                if req_type:
                    op_args["requirement"] = requirement
                else:
                    op_args["process"] = self.process
                op = pops.ProcessAddLogEntry(
                    audit_author=self.visitor,
                    audit_notes=logtext,
                    is_public=action == "log_public",
                    **op_args)
        elif action == "log_public":
            if "add_log" not in visit_perms: raise PermissionDenied
            action = ""
        elif action == "req_unapprove":
            if action not in visit_perms: raise PermissionDenied
            op = pops.RequirementUnapprove(audit_author=self.visitor, audit_notes=logtext or "Requirement unapproved", requirement=requirement)
        elif action == "req_approve":
            if action not in visit_perms: raise PermissionDenied
            op = pops.RequirementApprove(audit_author=self.visitor, audit_notes=logtext or "Requirement approved", requirement=requirement)
        elif action == "proc_freeze":
            if action not in visit_perms: raise PermissionDenied
            op = pops.ProcessFreeze(audit_author=self.visitor, audit_notes=logtext or "Process frozen for review", process=self.process)
        elif action == "proc_unfreeze":
            if action not in visit_perms: raise PermissionDenied
            op = pops.ProcessUnfreeze(audit_author=self.visitor, audit_notes=logtext or "Process unfrozen for further work", process=self.process)
        elif action == "proc_approve":
            if action not in visit_perms: raise PermissionDenied
            op = pops.ProcessApprove(audit_author=self.visitor, audit_notes=logtext or "Process approved", process=self.process)
        elif action == "proc_unapprove":
            if action not in visit_perms: raise PermissionDenied
            op = pops.ProcessUnapprove(audit_author=self.visitor, audit_notes=logtext or "Process unapproved", process=self.process)

        if op is not None:
            op.execute(self.request)

        return redirect(target.get_absolute_url())


class ReqIntent(RequirementMixin, TemplateView):
    type = "intent"
    template_name = "process/req_intent.html"


class ReqAgreements(RequirementMixin, TemplateView):
    type = "sc_dmup"
    template_name = "process/req_sc_dmup.html"


class ReqKeycheck(RequirementMixin, TemplateView):
    type = "keycheck"
    template_name = "process/req_keycheck.html"


class ReqAdvocate(RequirementMixin, TemplateView):
    type = "advocate"
    template_name = "process/req_advocate.html"

    def get_context_data(self, **kw):
        ctx = super(ReqAdvocate, self).get_context_data(**kw)
        ctx["warn_dm_preferred"] = self.process.applying_for == const.STATUS_DD_U and self.process.person.status not in (const.STATUS_DM, const.STATUS_DM_GA)
        return ctx


class ReqAM(RequirementMixin, TemplateView):
    type = "am_ok"
    template_name = "process/req_am_ok.html"


class AssignAM(RequirementMixin, TemplateView):
    require_visit_perms = "am_assign"
    type = "am_ok"
    template_name = "process/assign_am.html"

    def pre_dispatch(self):
        super(AssignAM, self).pre_dispatch()
        if self.process.current_am_assignment is not None:
            raise PermissionDenied

    def get_context_data(self, **kw):
        ctx = super(AssignAM, self).get_context_data(**kw)
        ctx["ams"] = bmodels.AM.list_available(free_only=False)
        return ctx

    def post(self, request, *args, **kw):
        am_key = request.POST.get("am", None)
        am = bmodels.AM.lookup_or_404(am_key)
        op = pops.ProcessAssignAM(audit_author=self.visitor, process=self.process, am=am)
        op.execute(self.request)
        return redirect(self.requirement.get_absolute_url())


class UnassignAM(RequirementMixin, View):
    require_visit_perms = "am_unassign"
    type = "am_ok"
    def post(self, request, *args, **kw):
        current = self.process.current_am_assignment
        if current is not None:
            op = pops.ProcessUnassignAM(audit_author=self.visitor, assignment=current)
            op.execute(self.request)
        return redirect(self.requirement.get_absolute_url())


class StatementCreate(RequirementMixin, FormView):
    form_class = StatementForm
    require_visit_perms = "edit_statements"
    template_name = "process/statement_create.html"

    def load_objects(self):
        super().load_objects()
        self.blurb = self.get_blurb()
        if self.blurb:
            self.blurb = ["For nm.debian.org, at {:%Y-%m-%d}:".format(now())] + self.blurb

    def check_permissions(self):
        super().check_permissions()
        if self.requirement.process.applying_for in (const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD):
            raise PermissionDenied

    def get_form_kwargs(self):
        kw = super().get_form_kwargs()
        kw["fpr"] = self.visitor.fpr
        return kw

    def get_blurb(self):
        """
        Get the blurb used for auto-verification, or None if none is available
        """
        if self.requirement.type == "sc_dmup":
            return [
                "I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.",
                "I have read the Debian Machine Usage Policy and I accept them."
            ]
        #elif self.requirement.type == "intent":
        #    return [
        #        "I would like to apply to change my status in Debian to {}".format(const.ALL_STATUS_DESCS[self.process.applying_for]),
        #    ]
        return None

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["blurb"] = [shlex_quote(x) for x in self.blurb] if self.blurb else None
        ctx["wikihelp"] = "https://wiki.debian.org/nm.debian.org/Statements"
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        statement, plaintext = form.cleaned_data["statement"]
        op = pops.ProcessStatementAdd(
                audit_author=self.visitor,
                requirement=self.requirement,
                statement=statement)
        op.execute(self.request)
        return redirect(self.requirement.get_absolute_url())


class StatementDelete(StatementMixin, TemplateView):
    require_visit_perms = "edit_statements"
    template_name = "process/statement_delete.html"

    def post(self, request, *args, **kw):
        op = pops.ProcessStatementRemove(audit_author=self.visitor, statement=self.statement)
        op.execute(self.request)
        return redirect(self.requirement.get_absolute_url())


class StatementRaw(StatementMixin, View):
    def get(self, request, *args, **kw):
        return http.HttpResponse(self.statement.statement, content_type="text/plain")


class MailArchive(VisitProcessMixin, View):
    require_visit_perms = "view_mbox"

    def get(self, request, *args, **kw):
        fname = self.process.mailbox_file
        if fname is None: raise http.Http404

        user_fname = "{}-{}-{}.mbox".format(
            self.process.person.uid or self.process.person.email,
            self.process.applying_for,
            self.process.pk)

        res = http.HttpResponse(content_type="application/octet-stream")
        res["Content-Disposition"] = "attachment; filename=%s.gz" % user_fname

        # Compress the mailbox and pass it to the request
        from gzip import GzipFile
        import os.path
        import shutil
        # The last mtime argument seems to only be supported in python 2.7
        outfd = GzipFile(user_fname, "wb", 9, res) #, os.path.getmtime(fname))
        try:
            with open(fname, "rb") as infd:
                shutil.copyfileobj(infd, outfd)
            outfd.write(b"\n")
            outfd.write(self.process.get_statements_as_mbox())
        finally:
            outfd.close()
        return res


class DisplayMailArchive(VisitProcessMixin, TemplateView):
    require_visit_perms = "view_mbox"
    template_name = "restricted/display-mail-archive.html"

    def get_context_data(self, **kw):
        import backend.email
        ctx = super(DisplayMailArchive, self).get_context_data(**kw)
        fname = self.process.mailbox_file
        if fname is None: raise http.Http404
        ctx["mails"] = backend.email.get_mbox_as_dicts(fname)
        ctx["process"] = self.process
        ctx["class"] = "clickable"
        return ctx


class UpdateKeycheck(RequirementMixin, View):
    type = "keycheck"
    require_visit_perms = "update_keycheck"

    def post(self, request, *args, **kw):
        from keyring.models import Key
        try:
            key = Key.objects.get_or_download(self.person.fpr)
        except RuntimeError as e:
            key = None
        if key is not None:
            key.update_key()
            key.update_check_sigs()
        return redirect(self.requirement.get_absolute_url())


class DownloadStatements(VisitProcessMixin, View):
    def get(self, request, *args, **kw):
        data = self.process.get_statements_as_mbox()
        res = http.HttpResponse(data, content_type="text/plain")
        res["Content-Disposition"] = "attachment; filename={}.mbox".format(self.person.lookup_key)
        return res


def only_needs_guest_account(process):
    if process.person.status == const.STATUS_DC:
        if process.applying_for == const.STATUS_DC_GA:
            return True
    elif process.person.status == const.STATUS_DM:
        if process.applying_for == const.STATUS_DM_GA:
            return True
    return False


def make_rt_ticket_text(request, visitor, process):
    retiring = process.applying_for in (const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD)
    ctx = {
        "visitor": visitor,
        "person": process.person,
        "process": process,
        "retiring": retiring,
    }

    ## Build request text

    req = []
    if process.person.status == const.STATUS_DC:
        if process.applying_for == const.STATUS_DC_GA:
            req.append("Please create a porter account for {person.fullname} (sponsored by {sponsors}).")
    elif process.person.status == const.STATUS_DC_GA:
        pass
    elif process.person.status == const.STATUS_DM:
        if process.applying_for == const.STATUS_DM_GA:
            req.append("Please create a porter account for {person.fullname} (currently a DM).")
    elif process.person.status == const.STATUS_DM_GA:
        pass
    elif process.person.status == const.STATUS_DD_NU:
        pass
    elif process.person.status == const.STATUS_EMERITUS_DD:
        pass
    elif process.person.status == const.STATUS_REMOVED_DD:
        pass

    only_guest_account = only_needs_guest_account(process)

    if retiring:
        req.append("Please make {person.fullname} (currently '{status}') a '{applying_for}'.")
    elif not only_guest_account:
        req.append("Please make {person.fullname} (currently '{status}') a '{applying_for}' (advocated by {sponsors}).")

    if not only_guest_account:
        if process.person.status == const.STATUS_DC:
            req.append("Key {person.fpr} should be added to the '{applying_for}' keyring.")
        else:
            req.append("Key {person.fpr} should be moved from the '{status}' to the '{applying_for}' keyring.")

    if retiring:
        req.append("Please also disable the {person.uid} LDAP account.")
    elif process.person.status not in (const.STATUS_DC, const.STATUS_DM):
        req.append("Note that {person.fullname} already has an account in LDAP.")

    sponsors = set()
    try:
        adv_req = process.requirements.get(type="advocate")
    except pmodels.Requirement.DoesNotExist:
        adv_req = None
    if adv_req is not None:
        for st in adv_req.statements.all():
            sponsors.add(st.uploaded_by.lookup_key)
    sponsors = ", ".join(sorted(sponsors))

    format_args = {
        "person": process.person,
        "process": process,
        "status": const.ALL_STATUS_DESCS[process.person.status],
        "applying_for": const.ALL_STATUS_DESCS[process.applying_for],
        "sponsors": sponsors,
    }

    import textwrap
    wrapper = textwrap.TextWrapper(width=75)
    wrapped = []
    for paragraph in req:
        for line in wrapper.wrap(paragraph.format(**format_args)):
            wrapped.append(line)
        wrapped.append("")
    ctx["request"] = "\n".join(wrapped)


    # Format the declarations of intent

    wrapper = textwrap.TextWrapper(width=75, initial_indent="  ", subsequent_indent="  ")
    wrapped = []
    intents_from = set()
    for intent in pmodels.Statement.objects.filter(requirement__process=process, requirement__type="intent"):
        intents_from.add(intent.uploaded_by)
        for paragraph in intent.statement_clean.splitlines():
            for line in wrapper.wrap(paragraph):
                wrapped.append(line)
        wrapped.append("")
    ctx["intents"] = "\n".join(wrapped)
    ctx["intents_from"] = ", ".join(x.uid for x in sorted(intents_from))

    ctx["process_url"] = build_absolute_uri(process.get_absolute_url(), request)

    from django.template.loader import render_to_string
    return render_to_string("process/rt_ticket.txt", ctx).strip()


class MakeRTTicket(VisitProcessMixin, TemplateView):
    template_name = "process/make_rt_ticket.html"

    def get_context_data(self, **kw):
        ctx = super(MakeRTTicket, self).get_context_data(**kw)

        only_guest_account = only_needs_guest_account(self.process)

        if only_guest_account:
            ctx["mail_to"] = "Debian Sysadmin requests <admin@rt.debian.org>"
            ctx["subject"] = "[Debian RT] Guest account on porter machines for {}".format(self.person.fullname)
        else:
            ctx["mail_to"] = "Debian Keyring requests <keyring@rt.debian.org>"
            ctx["subject"] = "[Debian RT] {} to become {}".format(self.person.fullname, const.ALL_STATUS_DESCS[self.process.applying_for])

        ctx["only_guest_account"] = only_guest_account

        ctx["text"] = make_rt_ticket_text(self.request, self.visitor, self.process)

        return ctx


class ApproveForm(forms.Form):
    signed = forms.CharField(label="Signed RT text", widget=forms.Textarea(attrs={"rows": 25, "cols": 80}))


class Approve(VisitProcessMixin, FormView):
    require_visitor = "admin"
    template_name = "process/approve.html"
    form_class = ApproveForm

    def load_objects(self):
        super().load_objects()
        self.op = pops.ProcessApproveRT(audit_author=self.visitor, process=self.process)

    def check_permissions(self):
        super().check_permissions()
        if not self.process.frozen:
            raise PermissionDenied
        if self.process.approved:
            raise PermissionDenied

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        rt_content = OrderedDict()
        rt_content["id"] = self.op.rt_id
        rt_content["Queue"] = self.op.rt_queue
        rt_content["Requestor"] = self.op.rt_requestor
        rt_content["Subject"] = self.op.rt_subject
        rt_content["Cc"] = self.op.rt_cc
        ctx["rt_content"] = rt_content
        ctx["text"] = make_rt_ticket_text(self.request, self.visitor, self.process)
        return ctx

    def form_valid(self, form):
        self.op.rt_text = form.cleaned_data["signed"]

        try:
            self.op.execute(self.request)
        except self.op.RTError as e:
            out = http.HttpResponse(content_type="text/plain")
            out.status_code = 500
            print("Error:", e.msg, file=out)
            print("RT response:", file=out)
            for line in e.rt_lines:
                print(line, file=out)
            return out

        return redirect(self.process.get_absolute_url())


class EmeritusForm(forms.Form):
    statement = forms.CharField(
        required=True,
        label=_("Statement"),
        widget=forms.Textarea(attrs=dict(rows=10, cols=80)),
    )


class Emeritus(TokenAuthMixin, VisitPersonMixin, FormView):
    token_domain = "emeritus"
    require_visitor = "dd"
    template_name = "process/emeritus.html"
    form_class = EmeritusForm
    # Make the token last 3 months, so that one has plenty of time to use it
    # even if MIA lags triggering removal
    token_max_age = 90 * 3600 * 24
    initial = {
        "statement": """
Dear fellow developers,

As I am not currently active in Debian, I request to move to the Emeritus
status.

So long, and thanks for all the fish.
""".strip()
    }

    def load_objects(self):
        super().load_objects()
        try:
            self.process = pmodels.Process.objects.get(person=self.person, applying_for__in=(const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD))
        except pmodels.Process.DoesNotExist:
            self.process = None

        self.expired = self.process is not None and (
                self.process.applying_for == const.STATUS_REMOVED_DD
                or self.process.closed is not None
        )

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["expired"] = self.expired
        return ctx

    @classmethod
    def get_nonauth_url(cls, person, request=None):
        from django.utils.http import urlencode
        if person.uid is None:
            raise RuntimeError("cannot generate an Emeritus url for a user without uid")
        url = reverse("process_emeritus") + "?" + cls.make_token(person.uid)
        if not request: return url
        return build_absolute_uri(url, request)

    def form_valid(self, form):
        if self.expired:
            raise PermissionDenied

        op = pops.RequestEmeritus(audit_author=self.visitor, person=self.person, statement=form.cleaned_data["statement"])
        op.execute(self.request)

        return redirect(op._statement.requirement.process.get_absolute_url())


class CancelForm(forms.Form):
    statement = forms.CharField(
        required=True,
        label=_("Statement"),
        widget=forms.Textarea(attrs=dict(rows=25, cols=80, placeholder="Enter here details of your activity in Debian"))
    )
    is_public = forms.BooleanField(
        required=False,
        label=_("Make the message public"),
    )


class Cancel(VisitProcessMixin, FormView):
    template_name = "process/cancel.html"
    form_class = CancelForm

    def check_permissions(self):
        super().check_permissions()
        # Visible by anonymous or by who can close the procses
        if self.request.user.is_anonymous:
            if self.request.method == "GET":
                return
            else:
                raise PermissionDenied
        if "proc_close" not in self.visit_perms:
            raise PermissionDenied

    def form_valid(self, form):
        if self.process.applying_for in (const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD):
            cls = pops.ProcessCancelEmeritus
        else:
            cls = pops.ProcessCancel

        op = cls(
                audit_author=self.visitor,
                process=self.process,
                is_public=form.cleaned_data["is_public"],
                statement=form.cleaned_data["statement"])
        op.execute(self.request)
        return redirect(self.process.get_absolute_url())
