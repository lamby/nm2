# coding: utf8
# nm.debian.org AM interaction
#
# Copyright (C) 2013--2014  Enrico Zini <enrico@debian.org>
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
from django.shortcuts import render, render_to_response, redirect
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.views.generic import View
from django.utils.timezone import now
import backend.models as bmodels
import minechangelogs.models as mmodels
from backend import const
from backend.mixins import VisitorMixin, VisitorTemplateView, VisitPersonTemplateView
import backend.email
import json
import datetime

class AMMain(VisitorTemplateView):
    require_visitor = "am"
    template_name = "restricted/ammain.html"

    def get_context_data(self, **kw):
        from django.db.models import Min, Max
        ctx = super(AMMain, self).get_context_data(**kw)

        ctx["am_available"] = bmodels.AM.list_free()

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

def make_am_form(editor):
    excludes = ["person", "is_am_ctte", "created"]

    if editor.is_dam:
        pass
    elif editor.is_fd:
        excludes.append("is_dam")
    else:
        excludes.append("is_fd")
        excludes.append("is_dam")

    class AMForm(forms.ModelForm):
        class Meta:
            model = bmodels.AM
            exclude = excludes
    return AMForm

class AMProfile(VisitorTemplateView):
    require_visitor = "am"
    template_name = "restricted/amprofile.html"

    def get_context_data(self, **kw):
        ctx = super(AMProfile, self).get_context_data(**kw)
        uid = self.kwargs.get("uid", None)

        from django.db.models import Min

        if uid is None:
            person = self.visitor
        else:
            person = bmodels.Person.lookup_or_404(uid)
        am = person.am

        AMForm = make_am_form(am)

        form = AMForm(instance=am)

        processes = bmodels.Process.objects.filter(manager=am).annotate(started=Min("log__logdate")).order_by("-started")

        ctx.update(
            person=person,
            am=am,
            processes=processes,
            form=form,
        )

    def post(self, request, uid=None, *args, **kw):
        if uid is None:
            person = self.visitor
        else:
            person = bmodels.Person.lookup_or_404(uid)
            if person.pk != self.visitor.pk and not self.visitor.is_admin:
                raise PermissionDenied

        am = person.am
        AMForm = make_am_form(am)
        form = AMForm(request.POST, instance=am)
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
        perms = self.vperms.perms

        # Check permissions
        if "edit_bio" not in perms and "edit_ldap" not in perms:
            raise PermissionDenied

        # Build the form to edit the person
        excludes = ["user", "created", "status_changed"]
        if "edit_bio" not in perms:
            excludes.append("bio")
        if "edit_ldap" not in perms:
            excludes.extend(("cn", "mn", "sn", "email", "uid", "fpr"))
        if not self.visitor.is_admin:
            excludes.extend(("status", "fd_comment", "expires", "pending"))

        class PersonForm(forms.ModelForm):
            class Meta:
                model = bmodels.Person
                exclude = excludes
        return PersonForm

    def get_context_data(self, **kw):
        ctx = super(Person, self).get_context_data(**kw)
        if "form" not in ctx:
            ctx["form"] = self.get_person_form()(instance=self.person)
        return ctx

    def post(self, request, *args, **kw):
        form = self.get_person_form()(request.POST, instance=self.person)
        if form.is_valid():
            form.save()

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
        if applying_for not in self.vperms.advocate_targets:
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
                                            .order_by("last_change")[0]:
                    became_dm = p.last_change
                if not became_dm:
                    became_dm = self.person.status_changed

                ts_now = now()
                if became_dm + datetime.timedelta(days=6*30) > ts_now:
                    # Warn about not having been DM for 6 months
                    ctx["warn_early_dm"] = became_dm

        ctx["existing_process"] = self.get_existing_process(applying_for)
        ctx["applying_for"] = applying_for

#def advocate_as_dd(request, key):
#    if request.method == "POST":
#        form = AdvocateDDForm(request.POST)
#        if form.is_valid():
#            # Create process if missing
#            if proc is None:
#                proc = bmodels.Process(
#                    person=person,
#                    applying_as=person.status,
#                    applying_for=const.STATUS_DD_U if form.cleaned_data["uploading"] else const.STATUS_DD_NU,
#                    progress=const.PROGRESS_ADV_RCVD,
#                    is_active=True)
#                proc.save()
#                # Log the change
#                text = "Process created by %s advocating %s" % (request.person.lookup_key, person.fullname)
#                if 'impersonate' in request.session:
#                    text = "[%s as %s] %s" % (request.user, request.person.lookup_key, text)
#                lt = bmodels.Log(
#                    changed_by=request.person,
#                    process=proc,
#                    progress=const.PROGRESS_APP_NEW,
#                    logtext=text,
#                )
#                lt.save()
#            # Add advocate
#            proc.advocates.add(request.person)
#            # Log the change
#            text = form.cleaned_data["logtext"]
#            if 'impersonate' in request.session:
#                text = "[%s as %s] %s" % (request.user, request.person.lookup_key, text)
#            lt = bmodels.Log(
#                changed_by=request.person,
#                process=proc,
#                progress=proc.progress,
#                is_public=True,
#                logtext=text,
#            )
#            lt.save()
#            # Send mail
#            backend.email.send_notification("notification_mails/advocacy_as_dd.txt", lt)
#            return redirect('public_process', key=proc.lookup_key)
#    else:
#        initial = dict(uploading=is_dm)
#        if proc:
#            uploading=(proc.applying_for == const.STATUS_DD_U)
#        form = AdvocateDDForm(initial=initial)
#
#    return render_to_response("restricted/advocate-dd.html",
#                              dict(
#                                  form=form,
#                                  person=person,
#                                  process=proc,
#                                  is_dm=is_dm,
#                                  is_early=is_early,
#                              ),
#                              context_instance=template.RequestContext(request))
        return ctx

    def post(self, request, applying_for, key, *args, **kw):
        applying_for = self.kwargs["applying_for"]
        if applying_for not in self.vperms.advocate_targets:
            raise PermissionDenied

        process = self.get_existing_process(applying_for)
        if not process:
            process = bmodels.Process(
                person=self.person,
                progress=const.PROGRESS_ADV_RCVD,
                is_active=True,
                applying_as=self.person.status,
                applying_for=applying_for,
            )
            process.save()
        process.advocates.add(self.visitor)

        text=""
        if 'impersonate' in request.session:
            text = "[%s as %s]" % (request.user, self.visitor.lookup_key)
        log = bmodels.Log(
            changed_by=self.visitor,
            process=process,
            progress=process.progress,
            logtext=text,
        )
        log.save()

        return redirect('public_process', key=process.lookup_key)

class DBExport(VisitorMixin, View):
    def get(self, request, *args, **kw):
        if request.user.is_anonymous():
            raise PermissionDenied

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

        res = http.HttpResponse(mimetype="application/json")
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
        visitor = request.user.get_profile()
        if not visitor or not visitor.is_admin: raise PermissionDenied
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

class NMAMMatch(VisitorTemplateView):
    template_name = "restricted/nm-am-match.html"
    require_visitor = "admin"

    def get_context_data(self, **kw):
        from django.db.models import Min, Max
        ctx = super(AMProfile, self).get_context_data(**kw)
        procs = []
        for p in bmodels.Process.objects.filter(is_active=True, progress=const.PROGRESS_APP_OK) \
                        .annotate(
                            started=Min("log__logdate"),
                            last_change=Max("log__logdate")) \
                        .order_by("started"):
            p.annotate_with_duration_stats()
            procs.append(p)
        ams = bmodels.AM.list_free()

        json_ams = dict()
        for a in ams:
            json_ams[a.person.lookup_key] = dict(
                name=a.person.fullname,
                uid=a.person.uid,
                email=a.person.email,
                key=a.person.lookup_key,
            )
        json_nms = dict()
        for p in procs:
            json_nms[p.lookup_key] = dict(
                name=p.person.fullname,
                uid=p.person.uid,
                email=p.person.email,
                key=p.lookup_key,
            )

        ctx.update(
            procs=procs,
            ams=ams,
            json_ams=json.dumps(json_ams),
            json_nms=json.dumps(json_nms),
        )
        return ctx

    def post(self, request, *args, **kw):
        # Perform assignment if requested
        am_key = request.POST.get("am", None)
        am = bmodels.AM.lookup_or_404(am_key)
        nm_key = request.POST.get("nm", None)
        nm = bmodels.Process.lookup_or_404(nm_key)
        _assign_am(request, self.visitor, nm, am)
        context = self.get_context_data(**kw)
        return self.render_to_response(context)

class MailArchive(VisitorMixin, View):
    def get(self, request, key, *args, **kw):
        process = bmodels.Process.lookup_or_404(key)
        perms = process.permissions_of(self.visitor)

        if not perms.can_view_email:
            raise PermissionDenied

        fname = process.mailbox_file
        if fname is None:
            from django.http import Http404
            raise Http404

        user_fname = "%s.mbox" % (process.person.uid or process.person.email)

        res = http.HttpResponse(mimetype="application/octet-stream")
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
        perms = process.permissions_of(self.visitor)

        if not perms.can_view_email:
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
        ctx = super(AMProfile, self).get_context_data(**kw)
        key = self.kwargs["key"]
        process = bmodels.Process.lookup_or_404(key)
        if process.manager is not None:
            raise PermissionDenied

        # List free AMs
        ams = bmodels.AM.list_free()

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
