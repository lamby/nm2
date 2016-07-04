# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django import http, template, forms
from django.conf import settings
from django.shortcuts import render, render_to_response, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.views.generic import View, TemplateView
from django.views.generic.edit import FormView
from django.utils.timezone import now
from django.db import transaction
import backend.models as bmodels
import minechangelogs.models as mmodels
from backend import const
from backend.mixins import VisitorMixin, VisitPersonMixin, VisitorTemplateView, VisitPersonTemplateView, VisitProcessMixin
import backend.email
import json
import datetime
import os

class AMMain(VisitorTemplateView):
    require_visitor = "am"
    template_name = "restricted/ammain.html"

    def _show_process(self, process):
        """
        Return True if the process should be shown in ammain, False if it
        should not.
        """
        if process.frozen_by_id is not None or process.approved_by_id is not None: return True
        for_ga = process.applying_for in (const.STATUS_DC_GA, const.STATUS_DM_GA)

        needs_am_report = False
        for req in process.requirements.all():
            if req.type == "intent":
                if not req.approved_by_id: return False
                # Hide all processes with a statement of intent approved less
                # than 4 days ago
                if not for_ga and req.approved_time + datetime.timedelta(days=4) > now(): return False
            elif req.type == "sc_dmup":
                if not req.approved_by_id: return False
            elif req.type == "advocate":
                if not req.approved_by_id: return False
            elif req.type == "am_ok":
                needs_am_report = req.approved_by_id is None

        if needs_am_report and process.current_am_assignment:
            return False

        return True

    def get_context_data(self, **kw):
        from django.db.models import Min, Max
        ctx = super(AMMain, self).get_context_data(**kw)

        import process.models as pmodels
        processes = []
        for p in pmodels.Process.objects.filter(closed__isnull=True).order_by("applying_for"):
            if not self._show_process(p): continue
            processes.append(p)
        ctx["current_processes"] = processes

        ctx["am_available"] = bmodels.AM.list_available(free_only=True)

        if self.visitor.am.is_fd or self.visitor.am.is_dam:
            DISPATCH = {
                const.PROGRESS_APP_NEW: "prog_app_new",
                const.PROGRESS_APP_RCVD: "prog_app_new",
                const.PROGRESS_ADV_RCVD: "prog_app_new",
                const.PROGRESS_POLL_SENT: "prog_poll_sent",
                const.PROGRESS_APP_OK: "prog_app_ok",
                const.PROGRESS_AM_RCVD: "prog_am_rcvd",
                const.PROGRESS_AM_OK: "prog_am_ok",
                const.PROGRESS_FD_OK: "prog_fd_ok",
                const.PROGRESS_DAM_OK: "prog_dam_ok",
            }
            for p in bmodels.Process.objects.filter(is_active=True, progress__in=DISPATCH.keys()) \
                            .annotate(
                                started=Min("log__logdate"),
                                last_change=Max("log__logdate")) \
                            .order_by("started"):
                tgt = DISPATCH.get(p.progress, None)
                if tgt is not None:
                    p.annotate_with_duration_stats()
                    ctx.setdefault(tgt, []).append(p)

            DISPATCH = {
                const.PROGRESS_APP_HOLD: "prog_app_hold",
                const.PROGRESS_FD_HOLD: "prog_app_hold",
                const.PROGRESS_DAM_HOLD: "prog_app_hold",
            }
            for p in bmodels.Process.objects.filter(is_active=True, manager=None, progress__in=DISPATCH.keys()) \
                            .annotate(
                                started=Min("log__logdate"),
                                last_change=Max("log__logdate")) \
                            .order_by("started"):
                tgt = DISPATCH.get(p.progress, None)
                if tgt is not None:
                    p.annotate_with_duration_stats()
                    ctx.setdefault(tgt, []).append(p)

            DISPATCH = {
                const.PROGRESS_FD_HOLD: "prog_fd_hold",
                const.PROGRESS_DAM_HOLD: "prog_dam_hold",
            }
            for p in bmodels.Process.objects.filter(is_active=True, progress__in=DISPATCH.keys()) \
                            .exclude(manager=None) \
                            .annotate(
                                started=Min("log__logdate"),
                                last_change=Max("log__logdate")) \
                            .order_by("started"):
                tgt = DISPATCH.get(p.progress, None)
                if tgt is not None:
                    p.annotate_with_duration_stats()
                    ctx.setdefault(tgt, []).append(p)


        DISPATCH = {
            const.PROGRESS_AM_RCVD: "am_prog_rcvd",
            const.PROGRESS_AM: "am_prog_am",
            const.PROGRESS_AM_HOLD: "am_prog_hold",
            const.PROGRESS_AM_OK: "am_prog_done",
            const.PROGRESS_FD_HOLD: "am_prog_done",
            const.PROGRESS_FD_OK: "am_prog_done",
            const.PROGRESS_DAM_HOLD: "am_prog_done",
            const.PROGRESS_DAM_OK: "am_prog_done",
            const.PROGRESS_DONE: "am_prog_done",
            const.PROGRESS_CANCELLED: "am_prog_done",
        }
        for p in bmodels.Process.objects.filter(manager=self.visitor.am, progress__in=DISPATCH.keys()) \
                        .annotate(
                            started=Min("log__logdate"),
                            last_change=Max("log__logdate")) \
                        .order_by("started"):
            tgt = DISPATCH.get(p.progress, None)
            if tgt is not None:
                p.annotate_with_duration_stats()
                ctx.setdefault(tgt, []).append(p)

        processes = []
        for a in pmodels.AMAssignment.objects.filter(am=self.visitor.am, unassigned_by__isnull=True, process__closed__isnull=True).select_related("process"):
            processes.append(a.process)
        ctx["am_processes"] = processes

        return ctx

class AMProfile(VisitPersonTemplateView):
    require_visitor = "am"
    template_name = "restricted/amprofile.html"

    def make_am_form(self):
        includes = ["slots"]
        visitor_am = self.visitor.am

        if visitor_am.is_fd:
            includes.append("is_fd")
        if visitor_am.is_dam:
            includes.append("is_dam")
        if visitor_am.is_admin:
            includes.append("fd_comment")

        class AMForm(forms.ModelForm):
            class Meta:
                model = bmodels.AM
                fields = includes
        return AMForm

    def get_context_data(self, **kw):
        ctx = super(AMProfile, self).get_context_data(**kw)
        from django.db.models import Min
        AMForm = self.make_am_form()
        am = self.person.am
        form = AMForm(instance=am)
        processes = bmodels.Process.objects.filter(manager=am).annotate(started=Min("log__logdate")).order_by("-started")
        ctx.update(
            am=am,
            processes=processes,
            form=form,
        )
        return ctx

    def post(self, request, *args, **kw):
        if self.person.pk != self.visitor.pk and not self.visitor.is_admin:
            raise PermissionDenied

        AMForm = self.make_am_form()
        form = AMForm(request.POST, instance=self.person.am)
        if form.is_valid():
            form.save()
            # TODO: message that it has been saved

        context = self.get_context_data(**kw)
        return self.render_to_response(context)


class DBExport(VisitorMixin, View):
    require_visitor = "dd"

    def get(self, request, *args, **kw):
        if "full" in request.GET:
            if not self.visitor.is_admin:
                raise PermissionDenied
            full = True
        else:
            full = False

        people = list(bmodels.export_db(full))

        class Serializer(json.JSONEncoder):
            def default(self, o):
                if hasattr(o, "strftime"):
                    return o.strftime("%Y-%m-%d %H:%M:%S")
                return json.JSONEncoder.default(self, o)

        res = http.HttpResponse(content_type="application/json")
        if full:
            res["Content-Disposition"] = "attachment; filename=nm-full.json"
        else:
            res["Content-Disposition"] = "attachment; filename=nm-mock.json"
        json.dump(people, res, cls=Serializer, indent=1)
        return res


class MinechangelogsForm(forms.Form):
    query = forms.CharField(
        required=True,
        label=_("Query"),
        help_text=_("Enter one keyword per line. Changelog entries to be shown must match at least one keyword. You often need to tweak the keywords to improve the quality of results. Note that keyword matching is case-sensitive."),
        widget=forms.Textarea(attrs=dict(rows=5, cols=40))
    )
    download = forms.BooleanField(
        required=False,
        label=_("Download"),
        help_text=_("Activate this field to download the changelog instead of displaying it"),
    )

def minechangelogs(request, key=None):
    if request.user.is_anonymous():
        raise PermissionDenied
    entries = None
    info = mmodels.info()
    info["max_ts"] = datetime.datetime.fromtimestamp(info["max_ts"])
    info["last_indexed"] = datetime.datetime.fromtimestamp(info["last_indexed"])

    if key:
        person = bmodels.Person.lookup_or_404(key)
    else:
        person = None

    keywords=None
    if request.method == 'POST':
        form = MinechangelogsForm(request.POST)
        if form.is_valid():
            query = form.cleaned_data["query"]
            keywords = [x.strip() for x in query.split("\n")]
            entries = mmodels.query(keywords)
            if form.cleaned_data["download"]:
                def send_entries():
                    for e in entries:
                        yield e
                        yield "\n\n"
                res = http.HttpResponse(send_entries(), content_type="text/plain")
                if person:
                    res["Content-Disposition"] = 'attachment; filename=changelogs-%s.txt' % person.lookup_key
                else:
                    res["Content-Disposition"] = 'attachment; filename=changelogs.txt'
                return res
            else:
                entries = list(entries)
    else:
        if person:
            query = [
                person.fullname,
                person.email,
            ]
            if person.cn and person.mn and person.sn:
                # some people don't use their middle names in changelogs
                query.append("{} {}".format(person.cn, person.sn))
            if person.uid:
                query.append(person.uid)
            form = MinechangelogsForm(initial=dict(query="\n".join(query)))
        else:
            form = MinechangelogsForm()

    return render_to_response("restricted/minechangelogs.html",
                              dict(
                                  keywords=keywords,
                                  form=form,
                                  info=info,
                                  entries=entries,
                                  person=person,
                              ),
                              context_instance=template.RequestContext(request))

class Impersonate(View):
    def get(self, request, key=None, *args, **kw):
        visitor = request.user
        if not visitor.is_authenticated() or not visitor.is_admin: raise PermissionDenied
        if key is None:
            del request.session["impersonate"]
        else:
            person = bmodels.Person.lookup_or_404(key)
            request.session["impersonate"] = person.lookup_key

        url = request.GET.get("url", None)
        if url is None:
            return redirect('home')
        else:
            return redirect(url)

def _assign_am(request, visitor, nm, am):
    import textwrap
    nm.manager = am
    nm.progress = const.PROGRESS_AM_RCVD
    nm.save()

    if not am.is_am:
        am.is_am = True
        am.save()

    # Parameters for the following templates
    parms = dict(
        fduid=visitor.uid,
        fdname=visitor.fullname,
        amuid=am.person.uid,
        amname=am.person.fullname,
        nmname=nm.person.fullname,
        nmcurstatus=const.ALL_STATUS_DESCS[nm.person.status],
        nmnewstatus=const.ALL_STATUS_DESCS[nm.applying_for],
        procurl=request.build_absolute_uri(reverse("public_process", kwargs=dict(key=nm.lookup_key))),
    )
    l = bmodels.Log.for_process(nm, changed_by=visitor)
    l.logtext = "Assigned to %(amuid)s" % parms
    if 'impersonate' in request.session:
        l.logtext = "[%s as %s] %s" % (request.user, visitor.lookup_key, l.logtext)
    l.save()


class MailArchive(VisitProcessMixin, View):
    require_visit_perms = "view_mbox"

    def get(self, request, key, *args, **kw):
        fname = self.process.mailbox_file
        if fname is None:
            from django.http import Http404
            raise Http404

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
    template_name = "restricted/display-mail-archive.html"
    require_visit_perms = "view_mbox"

    def get_context_data(self, **kw):
        ctx = super(DisplayMailArchive, self).get_context_data(**kw)

        fname = self.process.mailbox_file
        if fname is None:
            from django.http import Http404
            raise Http404

        ctx["mails"] = backend.email.get_mbox_as_dicts(fname)
        ctx["class"] = "clickable"
        return ctx


class AssignAM(VisitorTemplateView):
    template_name = "restricted/assign-am.html"
    require_visitor = "admin"

    def get_context_data(self, **kw):
        ctx = super(AssignAM, self).get_context_data(**kw)
        key = self.kwargs["key"]
        process = bmodels.Process.lookup_or_404(key)
        if process.manager is not None:
            raise PermissionDenied

        # List free AMs
        ams = bmodels.AM.list_available(free_only=False)

        ctx.update(
            process=process,
            person=process.person,
            ams=ams,
        )
        return ctx

    def post(self, request, key, *args, **kw):
        process = bmodels.Process.lookup_or_404(key)
        am_key = request.POST.get("am", None)
        am = bmodels.AM.lookup_or_404(am_key)
        _assign_am(request, self.visitor, process, am)
        return redirect(process.get_absolute_url())


class MailboxStats(VisitorTemplateView):
    template_name = "restricted/mailbox-stats.html"
    require_visitor = "admin"

    def get_context_data(self, **kw):
        ctx = super(MailboxStats, self).get_context_data(**kw)

        try:
            with open(os.path.join(settings.DATA_DIR, 'mbox_stats.json'), "rt") as infd:
                stats = json.load(infd)
        except OSError:
            stats = {}

        for email, st in stats["emails"].items():
            st["person"] = bmodels.Person.lookup_by_email(email)
            st["date_first_py"] = datetime.datetime.fromtimestamp(st["date_first"])
            st["date_last_py"] = datetime.datetime.fromtimestamp(st["date_last"])
            if "median" not in st or st["median"] is None:
                st["median_py"] = None
            else:
                st["median_py"] = datetime.timedelta(seconds=st["median"])
                st["median_hours"] = st["median_py"].seconds // 3600

        ctx.update(
            emails=sorted(stats["emails"].items()),
        )
        return ctx
