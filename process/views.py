# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.translation import ugettext as _
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.utils.timezone import now
from django.db import transaction
from django import forms, http
from django.core.exceptions import PermissionDenied
from backend.mixins import VisitorMixin, VisitPersonMixin
from backend import const
import backend.models as bmodels
from .mixins import VisitProcessMixin
import datetime
import re
from six.moves import shlex_quote
from . import models as pmodels
from .forms import StatementForm


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


class Create(VisitPersonMixin, FormView):
    """
    Create a new process
    """
    require_visit_perms = "request_new_status"
    template_name = "process/create.html"

    def get_context_data(self, **kw):
        ctx = super(Create, self).get_context_data(**kw)
        current = []
        current.extend(bmodels.Process.objects.filter(person=self.person, is_active=True))
        current.extend(pmodels.Process.objects.filter(person=self.person, closed__isnull=True))
        ctx["current"] = current
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
        # TODO: ensure visitor can create processes for person
        # TODO: ensure that applying_for is a valid new process for person
        with transaction.atomic():
            p = pmodels.Process.objects.create(self.person, applying_for)
            p.add_log(self.visitor, "Process created", is_public=True)
        return redirect(p.get_absolute_url())


class Show(VisitProcessMixin, TemplateView):
    """
    Show a process
    """
    template_name = "process/show.html"


class AddProcessLog(VisitProcessMixin, View):
    """
    Add an entry to the process or requirement log
    """
    @transaction.atomic
    def post(self, request, *args, **kw):
        logtext = request.POST.get("logtext", "")
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

        if action == "log_private":
            if "add_log" not in visit_perms: raise PermissionDenied
            is_public = False
            action = ""
        elif action == "log_public":
            if "add_log" not in visit_perms: raise PermissionDenied
            action = ""
        elif action == "req_unapprove":
            if action not in visit_perms: raise PermissionDenied
            if not logtext: logtext = "Unapproved"
            requirement.approved_by = None
            requirement.approved_time = None
            requirement.save()
        elif action == "req_approve":
            if action not in visit_perms: raise PermissionDenied
            if not logtext: logtext = "Approved"
            requirement.approved_by = self.visitor
            requirement.approved_time = now()
            requirement.save()
        elif action == "proc_freeze":
            if action not in visit_perms: raise PermissionDenied
            if not logtext: logtext = "Frozen for review"
            self.process.frozen_by = self.visitor
            self.process.frozen_time = now()
            self.process.save()
        elif action == "proc_unfreeze":
            if action not in visit_perms: raise PermissionDenied
            if not logtext: logtext = "Unfrozen for further work"
            self.process.frozen_by = None
            self.process.frozen_time = None
            self.process.save()
        elif action == "proc_approve":
            if action not in visit_perms: raise PermissionDenied
            if not logtext: logtext = "Process approved"
            self.process.approved_by = self.visitor
            self.process.approved_time = now()
            self.process.save()
        elif action == "proc_unapprove":
            if action not in visit_perms: raise PermissionDenied
            if not logtext: logtext = "Process unapproved"
            self.process.approved_by = None
            self.process.approved_time = None
            self.process.save()

        if logtext:
            target.add_log(self.visitor, logtext, action=action if action else "", is_public=is_public)
        return redirect(target.get_absolute_url())


class RequirementMixin(VisitProcessMixin):
    # Requirement type. If not found, check self.kwargs["type"]
    type = None

    def get_requirement_type(self):
        if self.type:
            return self.type
        else:
            return self.kwargs.get("type", None)

    def get_requirement(self):
        process = get_object_or_404(pmodels.Process, pk=self.kwargs["pk"])
        return get_object_or_404(pmodels.Requirement, process=process, type=self.get_requirement_type())

    def get_visit_perms(self):
        return self.requirement.permissions_of(self.visitor)

    def get_process(self):
        return self.requirement.process

    def load_objects(self):
        self.requirement = self.get_requirement()
        super(RequirementMixin, self).load_objects()

    def get_context_data(self, **kw):
        ctx = super(RequirementMixin, self).get_context_data(**kw)
        ctx["requirement"] = self.requirement
        ctx["type"] = self.requirement.type
        ctx["type_desc"] = pmodels.REQUIREMENT_TYPES_DICT[self.requirement.type].desc
        ctx["explain_template"] = "process/explain_statement_" + self.requirement.type + ".html"
        ctx["status"] = self.requirement.compute_status()
        return ctx


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

    def _assign_am(self, am):
        current = self.process.current_am_assignment
        if current is not None:
            current.unassigned_by = self.visitor
            current.unassigned_time = now()
            current.save()
            self.requirement.add_log(self.visitor, "Unassigned AM {}".format(current.am.person.lookup_key), is_public=True, action="unassign_am")

        current = pmodels.AMAssignment.objects.create(
            process=self.process,
            am=am,
            assigned_by=self.visitor,
            assigned_time=now())

        self.requirement.add_log(self.visitor, "Assigned AM {}".format(am.person.lookup_key), is_public=True, action="assign_am")

    def post(self, request, *args, **kw):
        am_key = request.POST.get("am", None)
        am = bmodels.AM.lookup_or_404(am_key)
        self._assign_am(am)
        return redirect(self.requirement.get_absolute_url())


class UnassignAM(RequirementMixin, View):
    require_visit_perms = "am_unassign"
    type = "am_ok"
    def post(self, request, *args, **kw):
        current = self.process.current_am_assignment
        if current is not None:
            current.unassigned_by = self.visitor
            current.unassigned_time = now()
            current.save()
            self.requirement.add_log(self.visitor, "Unassigned AM {}".format(current.am.person.lookup_key), is_public=True, action="unassign_am")
        return redirect(self.requirement.get_absolute_url())


class StatementMixin(RequirementMixin):
    def load_objects(self):
        super(StatementMixin, self).load_objects()
        if "st" in self.kwargs:
            self.statement = get_object_or_404(pmodels.Statement, pk=self.kwargs["st"])
            if self.statement.requirement != self.requirement:
                raise PermissionDenied
        else:
            self.statement = None

    def get_form_kwargs(self):
        kw = super(StatementMixin, self).get_form_kwargs()
        kw["fpr"] = self.visitor.fpr
        return kw

    def get_context_data(self, **kw):
        ctx = super(StatementMixin, self).get_context_data(**kw)
        ctx["fpr"] = self.visitor.fpr
        ctx["keyid"] = self.visitor.fpr[-16:]
        ctx["statement"] = self.statement
        ctx["now"] = now()
        return ctx


class StatementCreate(StatementMixin, FormView):
    form_class = StatementForm
    require_visit_perms = "edit_statements"
    template_name = "process/statement_create.html"

    def load_objects(self):
        super(StatementCreate, self).load_objects()
        self.blurb = self.get_blurb()
        if self.blurb:
            self.blurb = ["For nm.debian.org, at {:%Y-%m-%d}:".format(now())] + self.blurb

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

    def get_initial(self):
        if self.statement is None:
            return super(StatementCreate, self).get_initial()
        else:
            return { "statement": self.statement.statement }

    def normalise_text(self, text):
        return re.sub("\s+", " ", text).lower().strip()

    def get_context_data(self, **kw):
        ctx = super(StatementCreate, self).get_context_data(**kw)
        ctx["blurb"] = [shlex_quote(x) for x in self.blurb] if self.blurb else None
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        statement = self.statement
        if statement is None:
            statement = pmodels.Statement(requirement=self.requirement, fpr=self.visitor.fingerprint)
            action = "Added"
            log_action = "add_statement"
        else:
            action = "Updated"
            log_action = "update_statement"
        statement.uploaded_by = self.visitor
        statement.uploaded_time = now()
        statement.statement, plaintext = form.cleaned_data["statement"]

        if self.blurb is not None:
            expected = self.normalise_text("\n".join(self.blurb))
            submitted = self.normalise_text(plaintext)

        statement.save()

        self.requirement.approved_by = None
        self.requirement.approved_time = None
        self.requirement.save()
        self.requirement.add_log(self.visitor, "{} a signed statement".format(action), True, action=log_action)

        return redirect(self.requirement.get_absolute_url())


class StatementDelete(StatementMixin, TemplateView):
    require_visit_perms = "edit_statements"
    template_name = "process/statement_delete.html"

    def post(self, request, *args, **kw):
        self.statement.delete()
        return redirect(self.requirement.get_absolute_url())


class StatementRaw(StatementMixin, View):
    def get(self, request, *args, **kw):
        return http.HttpResponse(self.statement.statement, content_type="text/plain")


class MailArchive(VisitProcessMixin, View):
    require_visit_perms = "view_mbox"

    def get(self, request, key, *args, **kw):
        fname = self.process.mailbox_file
        if fname is None: raise http.Http404

        user_fname = "%s.mbox" % (self.process.person.uid or self.process.person.email)

        res = http.HttpResponse(content_type="application/octet-stream")
        res["Content-Disposition"] = "attachment; filename=%s.gz" % user_fname

        # Compress the mailbox and pass it to the request
        from gzip import GzipFile
        import os.path
        import shutil
        # The last mtime argument seems to only be supported in python 2.7
        outfd = GzipFile(user_fname, "wb", 9, res) #, os.path.getmtime(fname))
        try:
            with open(fname) as infd:
                shutil.copyfileobj(infd, outfd)
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


class MakeRTTicket(VisitProcessMixin, TemplateView):
    template_name = "process/make_rt_ticket.html"

    def get_context_data(self, **kw):
        ctx = super(MakeRTTicket, self).get_context_data(**kw)

        only_guest_account = False

        request = []
        if self.person.status == const.STATUS_DC:
            if self.process.applying_for == const.STATUS_DC_GA:
                only_guest_account = True
                request.append("please create a porter account for {person.fullname} (sponsored by {sponsors}).")
            elif self.process.applying_for == const.STATUS_DM:
                request.append("TODO DM") # TODO
        elif self.person.status == const.STATUS_DC_GA:
            pass
        elif self.person.status == const.STATUS_DM:
            if self.process.applying_for == const.STATUS_DM_GA:
                only_guest_account = True
                request = "please create a porter account for {person.fullname} (currently a DM)."
        elif self.person.status == const.STATUS_DM_GA:
            pass
        elif self.person.status == const.STATUS_DD_NU:
            pass
        elif self.person.status == const.STATUS_DD_E:
            pass
        elif self.person.status == const.STATUS_DD_R:
            pass


        # Build the request text
        request.append("Please make {person.fullname} (currently '{status}') a '{applying_for}'.")

        if not only_guest_account:
            request.append("")
            if self.person.status == const.STATUS_DC:
                request.append("Key {person.fpr} should be added to the '{applying_for}' keyring.")
            else:
                request.append("Key {person.fpr} should be moved from the '{status}' to the '{applying_for}' keyring.")

        if self.visit_perms.person_has_ldap_record:
            request.append("")
            request.append("Note that {{person.fullname}} already has an account in LDAP.")

        sponsors = set()
        try:
            adv_req = self.process.requirements.get(type="advocate")
        except pmodels.Requirement.DoesNotExist:
            adv_req = None
        if adv_req is not None:
            for st in adv_req.statements.all():
                sponsors.add(st.uploaded_by.lookup_key)
        sponsors = ", ".join(sorted(sponsors))

        request = "\n".join(request)
        ctx["request"] = request.format(
            person=self.person,
            process=self.process,
            status=const.ALL_STATUS_DESCS[self.person.status],
            applying_for=const.ALL_STATUS_DESCS[self.process.applying_for],
            sponsors=sponsors,
        )


        if only_guest_account:
            ctx["mail_to"] = "DSA <admin@rt.debian.org>"
            ctx["subject"] = "[Debian RT] Guest account to porter machines for {}".format(self.person.fullname)
        else:
            ctx["mail_to"] = "Debian Keyring Maintainers <keyring@rt.debian.org>"
            ctx["subject"] = "[Debian RT] Account for {}".format(self.person.fullname)

        ctx["only_guest_account"] = only_guest_account

        ctx["intents"] = pmodels.Statement.objects.filter(requirement__process=self.process, requirement__type="intent")

        ctx["process_url"] = self.request.build_absolute_uri(self.process.get_absolute_url())

        return ctx
