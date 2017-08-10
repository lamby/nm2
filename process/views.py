from django.utils.translation import ugettext as _
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.utils.timezone import now
from django.db import transaction
from django import forms, http
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.urls import reverse, reverse_lazy
from backend.mixins import VisitorMixin, VisitPersonMixin
from backend import const
import backend.models as bmodels
from .mixins import VisitProcessMixin
import datetime
import re
import json
import os
import requests
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
        current.extend(bmodels.Process.objects.filter(person=self.person, is_active=True))
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
        with transaction.atomic():
            p = pmodels.Process.objects.create(self.person, applying_for)
            p.add_log(self.visitor, "Process created", is_public=True)

        from .email import notify_new_process
        notify_new_process(p, self.request)

        return redirect(p.get_absolute_url())


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
            entry = target.add_log(self.visitor, logtext, action=action if action else "", is_public=is_public)
            if not action:
                from .email import notify_new_log_entry
                notify_new_log_entry(entry, request)

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
        ctx["wikihelp"] = "https://wiki.debian.org/nm.debian.org/Requirement/" + self.requirement.type
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

        if not am.is_am:
            am.is_am = True
            am.save()

        self.requirement.add_log(self.visitor, "Assigned AM {}".format(am.person.lookup_key), is_public=True, action="assign_am")

        from .email import notify_am_assigned
        notify_am_assigned(current, request=self.request)

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
        super().load_objects()
        self.blurb = self.get_blurb()
        if self.blurb:
            self.blurb = ["For nm.debian.org, at {:%Y-%m-%d}:".format(now())] + self.blurb
        if self.requirement.process.applying_for == const.STATUS_EMERITUS_DD:
            self.notify_ml = "private"
        else:
            self.notify_ml = "newmaint"

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
        ctx["wikihelp"] = "https://wiki.debian.org/nm.debian.org/Statements"
        ctx["notify_ml"] = self.notify_ml
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        statement = self.statement
        if statement is None:
            statement = pmodels.Statement(requirement=self.requirement, fpr=self.visitor.fingerprint)
            repace = False
        else:
            replace = True
        statement.uploaded_by = self.visitor
        statement.uploaded_time = now()
        statement.statement, plaintext = form.cleaned_data["statement"]
        statement.save()

        file_statement(self.request, self.visitor, self.requirement, statement, replace=replace, notify_ml=self.notify_ml)

        return redirect(self.requirement.get_absolute_url())


def file_statement(request, visitor, requirement, statement, replace=False, notify_ml="newmaint"):
    if replace:
        action = "Updated"
        log_action = "update_statement"
    else:
        action = "Added"
        log_action = "add_statement"

    requirement.add_log(visitor, "{} a signed statement".format(action), True, action=log_action)

    # Check if the requirement considers itself satisfied now, and
    # auto-mark approved accordingly
    status = requirement.compute_status()
    if status["satisfied"]:
        try:
            robot = bmodels.Person.objects.get(username="__housekeeping__")
        except bmodels.Person.DoesNotExist:
            robot = visitor
        requirement.approved_by = robot
        requirement.approved_time = now()
    else:
        requirement.approved_by = None
        requirement.approved_time = None
    requirement.save()

    if requirement.approved_by:
        requirement.add_log(requirement.approved_by, "New statement received, the requirement seems satisfied", True, action="req_approve")

    if requirement.type in ("intent", "advocate", "am_ok"):
        msg = statement.rfc3156
        if msg is None:
            from .email import notify_new_statement
            notify_new_statement(statement, request=request, cc_nm=(requirement.type=="am_ok"), notify_ml=notify_ml)


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
            with open(fname) as infd:
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
    ctx = {
        "visitor": visitor,
        "person": process.person,
        "process": process,
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

    if not only_guest_account:
        req.append("Please make {person.fullname} (currently '{status}') a '{applying_for}' (advocated by {sponsors}).")

    if not only_guest_account:
        if process.person.status == const.STATUS_DC:
            req.append("Key {person.fpr} should be added to the '{applying_for}' keyring.")
        else:
            req.append("Key {person.fpr} should be moved from the '{status}' to the '{applying_for}' keyring.")

    if process.person.status not in (const.STATUS_DC, const.STATUS_DM):
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
    for intent in pmodels.Statement.objects.filter(requirement__process=process, requirement__type="intent"):
        for paragraph in intent.statement_clean.splitlines():
            for line in wrapper.wrap(paragraph):
                wrapped.append(line)
        wrapped.append("")
    ctx["intents"] = "\n".join(wrapped)

    ctx["process_url"] = request.build_absolute_uri(process.get_absolute_url())

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


class EmailLookup(VisitProcessMixin, View):
    def _fetch_url(self, url):
        bundle="/etc/ssl/ca-debian/ca-certificates.crt"
        if os.path.exists(bundle):
            return requests.get(url, verify=bundle)
        else:
            return requests.get(url)

    def _scrape_msgid(self, content):
        from lxml.html import document_fromstring
        page = document_fromstring(content)
        for el in page.iter("li"):
            has_msgid = any(x.text == "Message-id" for x in el.iter("em"))
            if not has_msgid: continue
            for a in el.iter("a"):
                href = a.attrib.get("href", None)
                if href is None: continue
                if not href.startswith("msg"): continue
                return a.text
        return None

    def _fetch(self, url):
        mbox_pathname = self.process.mailbox_file
        if mbox_pathname is None:
            return { "error": "process has no archived emails yet" }

        if not url.startswith("https://lists.debian.org/debian-newmaint/"):
            return { "error": "url does not look like a debian-newmaint archive url" }

        res = self._fetch_url(url)
        if res.status_code != 200:
            return { "error": "fetching url had result code {} instead of 200".format(res.status_code) }

        msgid = self._scrape_msgid(res.content)
        if msgid is None:
            return { "error": "message ID not found at {}".format(url) }

        import mailbox
        mbox = mailbox.mbox(mbox_pathname)
        for key in mbox.keys():
            msg = mbox.get_message(key)
            if msg["Message-ID"].strip("<>") == msgid:
                fp = mbox.get_file(key)
                try:
                    return { "msg": fp.read().decode("utf8") }
                finally:
                    fp.close()

        return { "error": "Message-ID {} not found in archive mailbox".format(msgid) }

    def post(self, request, *args, **kw):
        url = request.POST["url"]
        res = http.HttpResponse(content_type="application/json")
        json.dump(self._fetch(url), res)
        return res


class ApproveForm(forms.Form):
    signed = forms.CharField(label="Signed RT text", widget=forms.Textarea(attrs={"rows": 25, "cols": 80}))


class Approve(VisitProcessMixin, FormView):
    require_visitor = "admin"
    template_name = "process/approve.html"
    form_class = ApproveForm

    def load_objects(self):
        super().load_objects()
        self.only_guest_account = only_needs_guest_account(self.process)

        if self.only_guest_account:
            subject = "Guest account on porter machines for {}".format(self.person.fullname)
        else:
            subject = "{} to become {}".format(self.person.fullname, const.ALL_STATUS_DESCS[self.process.applying_for])

        cc = [self.person.email, self.process.archive_email]
        if self.process.applying_for == "dm":
            cc.append("nm@debian.org")
            requestor = "nm@debian.org"
        else:
            requestor = "da-manager@debian.org"
            cc.append("da-manager@debian.org")

        self.rt_content = {
            "id": "ticket/new",
            "Queue": "DSA - Incoming" if self.only_guest_account else "Keyring",
            "Requestor": requestor,
            "Subject": subject,
            "Cc": ", ".join(cc)
        }

    def check_permissions(self):
        super().check_permissions()
        if not self.process.frozen:
            raise PermissionDenied
        if self.process.approved:
            raise PermissionDenied

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["rt_content"] = sorted(self.rt_content.items())
        ctx["text"] = make_rt_ticket_text(self.request, self.visitor, self.process)
        return ctx

    def form_valid(self, form):
        signed = form.cleaned_data["signed"]

        lines = []
        for key, val in self.rt_content.items():
            lines.append("{}: {}".format(key, val))

        lines.append("Text:")
        for line in signed.splitlines():
            lines.append(" " + line)

        args = {"data": { "content": "\n".join(lines) } }
        bundle="/etc/ssl/ca-debian/ca-certificates.crt"
        if os.path.exists(bundle):
            args["verify"] = bundle

        rt_user = getattr(settings, "RT_USER", None)
        rt_pass = getattr(settings, "RT_PASS", None)
        if rt_user is not None and rt_pass is not None:
            args["params"] = { "user": rt_user, "pass": rt_pass }

        # See https://rt-wiki.bestpractical.com/wiki/REST
        res = requests.post("https://rt.debian.org/REST/1.0/ticket/new", **args)
        res.raise_for_status()
        res_lines = res.text.splitlines()
        ver, status, text = res_lines[0].split(None, 2)

        def report_error(msg):
            out = http.HttpResponse(content_type="text/plain")
            out.status_code = 500
            print("Error:", msg, file=out)
            print("RT response:", file=out)
            for line in res_lines:
                print(line, file=out)
            return out

        if int(status) != 200:
            return report_error("RT status code is not 200")

        mo = re.match("# Ticket (\d+) created.", res_lines[2])
        if not mo:
            return report_error("Could not find ticket number is response")
        self.process.rt_ticket = int(mo.group(1))
        self.process.rt_request = signed
        self.process.approved_by = self.visitor
        self.process.approved_time = now()
        self.process.save()
        self.process.add_log(self.visitor, "Process approved", action="proc_approve", is_public=True)
        return redirect(self.process.get_absolute_url())


class TokenAuthMixin:
    # Domain used for this token
    token_domain = None
    # Max age in seconds
    token_max_age = 15 * 3600 * 24

    @classmethod
    def make_token(cls, uid, **kw):
        from django.utils.http import urlencode
        kw.update(u=uid, d=cls.token_domain)
        return urlencode({"t": signing.dumps(kw)})

    def verify_token(self, decoded):
        # Extend to verify extra components of the token
        pass

    def load_objects(self):
        token = self.request.GET.get("t")
        if token is not None:
            try:
                decoded = signing.loads(token, max_age=self.token_max_age)
            except signing.BadSignature:
                raise PermissionDenied
            uid = decoded.get("u")
            if uid is None:
                raise PermissionDenied
            if decoded.get("d") != self.token_domain:
                raise PermissionDenied
            self.verify_token(decoded)
            try:
                u = bmodels.Person.objects.get(uid=uid)
            except bmodels.Person.DoesNotExist:
                u = None
            if u is not None:
                self.request.user = u
        super().load_objects()


class EmeritusForm(forms.Form):
    statement = forms.CharField(
        required=True,
        label=_("Statement"),
        widget=forms.Textarea(attrs=dict(rows=25, cols=80, placeholder="Enter your leave message here"))
    )


class Emeritus(TokenAuthMixin, VisitorMixin, FormView):
    token_domain = "emeritus"
    require_visitor = "dd"
    template_name = "process/emeritus.html"
    form_class = EmeritusForm

    @classmethod
    def get_nonauth_url(cls, person, request=None):
        from django.utils.http import urlencode
        if person.uid is None:
            raise RuntimeError("cannot generate an Emeritus url for a user without uid")
        url = reverse("process_emeritus") + "?" + cls.make_token(person.uid)
        if not request: return url
        return request.build_absolute_uri(url)

    def form_valid(self, form):
        text = form.cleaned_data["statement"]

        try:
            process = pmodels.Process.objects.get(person=self.visitor, applying_for=const.STATUS_EMERITUS_DD)
        except pmodels.Process.DoesNotExist:
            process = None

        with transaction.atomic():
            if process is None:
                process = pmodels.Process.objects.create(self.visitor, const.STATUS_EMERITUS_DD)
                process.add_log(self.visitor, "Process created", is_public=True)

            requirement = process.requirements.get(type="intent")
            if requirement.statements.exists():
                return redirect(process.get_absolute_url())

            statement = pmodels.Statement(requirement=requirement)
            statement.uploaded_by = self.visitor
            statement.uploaded_time = now()
            statement.statement, plaintext = text, text
            statement.save()
            file_statement(self.request, self.visitor, requirement, statement, replace=False, notify_ml="private")

        return redirect(process.get_absolute_url())


class CancelForm(forms.Form):
    statement = forms.CharField(
        required=True,
        label=_("Statement"),
        widget=forms.Textarea(attrs=dict(rows=25, cols=80, placeholder="Enter your reason for canceling"))
    )
    is_public = forms.BooleanField(
        required=False,
        label=_("Message is public"),
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
        text = form.cleaned_data["statement"]
        with transaction.atomic():
            self.process.add_log(self.visitor, text, action="proc_close", is_public=form.cleaned_data["is_public"])
            self.process.closed = now()
            self.process.save()

        return redirect(self.process.get_absolute_url())
