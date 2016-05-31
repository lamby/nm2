# coding: utf8
# nm.debian.org AM interaction
#
# Copyright (C) 2013--2015  Enrico Zini <enrico@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
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
from django.views.generic import View
from django.views.generic.edit import FormView
from django.utils.timezone import now
from django.db import transaction
import backend.models as bmodels
import minechangelogs.models as mmodels
from backend import const
from backend.mixins import VisitorMixin, VisitPersonMixin, VisitorTemplateView, VisitPersonTemplateView
import backend.email
import json
import datetime
import os

class AMMain(VisitorTemplateView):
    require_visitor = "am"
    template_name = "restricted/ammain.html"

    def get_context_data(self, **kw):
        from django.db.models import Min, Max
        ctx = super(AMMain, self).get_context_data(**kw)

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

class Person(VisitPersonTemplateView):
    """
    Edit a person's information
    """
    template_name = "restricted/person.html"

    def get_person_form(self):
        perms = self.visit_perms.perms

        # Check permissions
        if "edit_bio" not in perms and "edit_ldap" not in perms:
            raise PermissionDenied

        # Build the form to edit the person
        includes = []
        if "edit_ldap" in perms:
            includes.extend(("cn", "mn", "sn", "email", "uid"))
        if self.visitor.is_admin:
            includes.extend(("status", "fd_comment", "expires", "pending"))
        if "edit_bio" in perms:
            includes.append("bio")

        class PersonForm(forms.ModelForm):
            class Meta:
                model = bmodels.Person
                fields = includes
        return PersonForm

    def get_context_data(self, **kw):
        ctx = super(Person, self).get_context_data(**kw)
        if "form" not in ctx:
            ctx["form"] = self.get_person_form()(instance=self.person)
        return ctx

    def post(self, request, *args, **kw):
        form = self.get_person_form()(request.POST, instance=self.person)
        if form.is_valid():
            p = form.save(commit=False)
            p.save(audit_author=self.visitor, audit_notes="edited Person information")

            # TODO: message that it has been saved

            # Redirect to the person view
            return redirect(self.person.get_absolute_url())

        context = self.get_context_data(form=form, **kw)
        return self.render_to_response(context)


class NewProcess(VisitPersonTemplateView):
    template_name = "restricted/advocate.html"
    """
    Create a new process
    """

    dd_statuses = frozenset((const.STATUS_DD_U, const.STATUS_DD_NU))
    dm_statuses = frozenset((const.STATUS_DM, const.STATUS_DM_GA))

    def get_existing_process(self, applying_for):
        "Get the existing process, if any"
        procs = list(self.person.processes.filter(is_active=True, applying_for=applying_for))
        if len(procs) > 1:
            return http.HttpResponseServerError(
                    "There is more than one active process applying for {}."
                    "Please ask Front Desk people to fix that before proceeding".format(applying_for))
        return procs[0] if procs else None

    def get_context_data(self, **kw):
        from django.db.models import Min, Max
        ctx = super(NewProcess, self).get_context_data(**kw)
        applying_for = self.kwargs["applying_for"]
        if applying_for not in self.visit_perms.advocate_targets:
            raise PermissionDenied

        # Checks and warnings

        # When applying for uploading DD
        if applying_for == const.STATUS_DD_U:
            if self.person.status not in self.dm_statuses:
                # Warn about the person not being a DM
                ctx["warn_no_dm"] = True
            else:
                # Check when the person first became DM
                became_dm = None
                for p in self.person.processes.filter(is_active=False, applying_for__in=self.dm_statuses) \
                                            .annotate(last_change=Max("log__logdate")) \
                                            .order_by("last_change"):
                    became_dm = p.last_change
                if not became_dm:
                    became_dm = self.person.status_changed

                ts_now = now()
                if became_dm + datetime.timedelta(days=6*30) > ts_now:
                    # Warn about not having been DM for 6 months
                    ctx["warn_early_dm"] = became_dm

        ctx["existing_process"] = self.get_existing_process(applying_for)
        ctx["applying_for"] = applying_for
        return ctx

    def post(self, request, applying_for, key, *args, **kw):
        applying_for = self.kwargs["applying_for"]
        if applying_for not in self.visit_perms.advocate_targets:
            raise PermissionDenied

        advtext = request.POST["text"].strip()
        if not advtext:
            context = self.get_context_data(**kw)
            return self.render_to_response(context)

        process = self.get_existing_process(applying_for)
        if not process:
            # Create the process if one does not exist yet
            process = bmodels.Process.objects.create(
                person=self.person,
                progress=const.PROGRESS_ADV_RCVD,
                is_active=True,
                applying_as=self.person.status,
                applying_for=applying_for,
            )

            # Log the creation
            text = "Process created by {} advocating {}".format(self.visitor.lookup_key, self.person.lookup_key)
            if self.impersonator:
                text = "[{} as {}] {}".format(self.impersonator.lookup_key, self.visitor.lookup_key, text)
            bmodels.Log.objects.create(
                changed_by=self.visitor,
                process=process,
                progress=process.progress,
                is_public=True,
                logtext=text,
            )

        # Add the advocate
        process.advocates.add(self.visitor)

        # Log the advocacy
        if self.impersonator:
            advtext = "[{} as {}] {}".format(self.impersonator.lookup_key, self.visitor.lookup_key, advtext)
        lt = bmodels.Log.objects.create(
            changed_by=self.visitor,
            process=process,
            progress=process.progress,
            is_public=True,
            logtext=advtext,
        )

        # Send mail
        backend.email.send_notification("notification_mails/advocacy.txt", lt)
        return redirect('public_process', key=process.lookup_key)

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

class MailArchive(VisitorMixin, View):
    def get(self, request, key, *args, **kw):
        process = bmodels.Process.lookup_or_404(key)
        vperms = process.permissions_of(self.visitor)

        if "view_mbox" not in vperms.perms:
            raise PermissionDenied

        fname = process.mailbox_file
        if fname is None:
            from django.http import Http404
            raise Http404

        user_fname = "%s.mbox" % (process.person.uid or process.person.email)

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

class DisplayMailArchive(VisitorTemplateView):
    template_name = "restricted/display-mail-archive.html"
    def get_context_data(self, **kw):
        ctx = super(DisplayMailArchive, self).get_context_data(**kw)
        key = self.kwargs["key"]
        process = bmodels.Process.lookup_or_404(key)
        vperms = process.permissions_of(self.visitor)

        if "view_mbox" not in vperms.perms:
            raise PermissionDenied

        fname = process.mailbox_file
        if fname is None:
            from django.http import Http404
            raise Http404

        ctx["mails"] = backend.email.get_mbox_as_dicts(fname)
        ctx["process"] = process
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
