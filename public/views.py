# coding: utf-8
# nm.debian.org website reports
#
# Copyright (C) 2012--2014  Enrico Zini <enrico@debian.org>
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
from django import http, forms
from django.conf import settings
from django.shortcuts import redirect, render, get_object_or_404
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext as _
from django.utils.timezone import now
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
import backend.models as bmodels
import backend.email as bemail
from backend import const
from backend.mixins import VisitorMixin, VisitorTemplateView, VisitPersonTemplateView, VisitProcessMixin, VisitProcessTemplateView
from .email_stats import mailbox_get_gaps
import markdown
import datetime
import os
import json

def lookup_or_404(dict, key):
    """
    Lookup a key in a dictionary, raising 404 if not found
    """
    try:
        return dict[key]
    except KeyError:
        raise http.Http404

class Managers(VisitorTemplateView):
    template_name = "public/managers.html"

    def get_context_data(self, **kw):
        ctx = super(Managers, self).get_context_data(**kw)
        from django.db import connection

        # Compute statistics indexed by AM id
        cursor = connection.cursor()
        cursor.execute("""
        SELECT am.id,
            count(*) as total,
            sum(case when process.is_active then 1 else 0 end) as active,
            sum(case when process.progress=%s then 1 else 0 end) as held
        FROM am
        JOIN process ON process.manager_id=am.id
        GROUP BY am.id
        """, (const.PROGRESS_AM_HOLD,))
        stats = {}
        for amid, total, active, held in cursor:
            stats[amid] = (total, active, held)

        # Read the list of AMs, with default sorting, and annotate with the
        # statistics
        ams = []
        for a in bmodels.AM.objects.all().order_by("-is_am", "person__uid"):
            total, active, held = stats.get(a.id, (0, 0, 0))
            a.stats_total = total
            a.stats_active = active
            a.stats_done = total-active
            a.stats_held = held
            ams.append(a)

        ctx["ams"] = ams
        return ctx

class Processes(VisitorTemplateView):
    template_name = "public/processes.html"

    def get_context_data(self, **kw):
        from django.db.models import Min, Max
        ctx = super(Processes, self).get_context_data(**kw)

        cutoff = now() - datetime.timedelta(days=180)

        ctx["open"] = bmodels.Process.objects.filter(is_active=True) \
                                             .annotate(
                                                 started=Min("log__logdate"),
                                                 last_change=Max("log__logdate")) \
                                             .order_by("-last_change")

        ctx["done"] = bmodels.Process.objects.filter(progress=const.PROGRESS_DONE) \
                                             .annotate(
                                                 started=Min("log__logdate"),
                                                 last_change=Max("log__logdate")) \
                                             .order_by("-last_change") \
                                             .filter(last_change__gt=cutoff)

        return ctx

def make_statusupdateform(editor):
    if editor.is_fd:
        choices = [(x.tag, "%s - %s" % (x.tag, x.ldesc)) for x in const.ALL_PROGRESS]
    else:
        choices = [(x.tag, x.ldesc) for x in const.ALL_PROGRESS if x[0] in ("PROGRESS_APP_OK", "PROGRESS_AM", "PROGRESS_AM_HOLD", "PROGRESS_AM_OK")]

    class StatusUpdateForm(forms.Form):
        progress = forms.ChoiceField(
            required=True,
            label=_("Progress"),
            choices=choices
        )
        logtext = forms.CharField(
            required=False,
            label=_("Log text"),
            widget=forms.Textarea(attrs=dict(rows=5, cols=80))
        )
        log_is_public = forms.BooleanField(
            required=False,
            label=_("Log is public")
        )
    return StatusUpdateForm


class Process(VisitProcessTemplateView):
    template_name = "public/process.html"

    def get_context_data(self, **kw):
        ctx = super(Process, self).get_context_data(**kw)

        # Process form ASAP, so we compute the rest with updated values
        am = self.visitor.am_or_none if self.visitor else None
        if am and (self.process.manager == am or am.is_admin) and (
            "edit_bio" in self.visit_perms or "edit_ldap" in self.visit_perms):
            StatusUpdateForm = make_statusupdateform(am)
            form = StatusUpdateForm(initial=dict(progress=self.process.progress))
        else:
            form = None

        ctx["form"] = form

        log = list(self.process.log.order_by("logdate", "progress"))
        if log:
            ctx["started"] = log[0].logdate
            ctx["last_change"] = log[-1].logdate
        else:
            ctx["started"] = datetime.datetime(1970, 1, 1, 0, 0, 0)
            ctx["last_change"] = datetime.datetime(1970, 1, 1, 0, 0, 0)

        if am:
            ctx["log"] = log
        else:
            # Summarise log for privacy
            distilled_log = []
            last_progress = None
            for l in log:
                if last_progress != l.progress:
                    distilled_log.append(dict(
                        progress=l.progress,
                        changed_by=l.changed_by,
                        logdate=l.logdate,
                    ))
                    last_progress = l.progress
            ctx["log"] = distilled_log

        # Map unusual steps to their previous usual ones
        unusual_step_map = {
            const.PROGRESS_APP_HOLD: const.PROGRESS_APP_RCVD,
            const.PROGRESS_AM_HOLD: const.PROGRESS_AM,
            const.PROGRESS_FD_HOLD: const.PROGRESS_AM_OK,
            const.PROGRESS_DAM_HOLD: const.PROGRESS_FD_OK,
            const.PROGRESS_CANCELLED: const.PROGRESS_DONE,
        }

        # Get the 'simplified' current step
        curstep = unusual_step_map.get(self.process.progress, self.process.progress)

        # List of usual steps in order
        steps = (
            const.PROGRESS_APP_NEW,
            const.PROGRESS_APP_RCVD,
            const.PROGRESS_ADV_RCVD,
            const.PROGRESS_POLL_SENT,
            const.PROGRESS_APP_OK,
            const.PROGRESS_AM_RCVD,
            const.PROGRESS_AM,
            const.PROGRESS_AM_OK,
            const.PROGRESS_FD_OK,
            const.PROGRESS_DAM_OK,
            const.PROGRESS_DONE,
        )

        # Add past/current/future timeline
        curstep_idx = steps.index(curstep)
        ctx["steps"] = steps
        ctx["curstep_idx"] = curstep_idx

        # Wizards for next actions
        if self.visitor:
            ctx["wizards"] = self.build_wizards(self.process)

        # Mailbox statistics
        # TODO: move saving per-process stats into a JSON field in Process
        try:
            with open(os.path.join(settings.DATA_DIR, 'mbox_stats.json'), "rt") as infd:
                stats = json.load(infd)
        except OSError:
            stats = {}

        stats = stats.get("process", {})
        stats = stats.get(self.process.lookup_key, {})
        if stats:
            stats["date_first_py"] = datetime.datetime.fromtimestamp(stats["date_first"])
            stats["date_last_py"] = datetime.datetime.fromtimestamp(stats["date_last"])
            if "median" not in stats or stats["median"] is None:
                stats["median_py"] = None
            else:
                stats["median_py"] = datetime.timedelta(seconds=stats["median"])
                stats["median_hours"] = stats["median_py"].seconds // 3600
        ctx["mbox_stats"] = stats

        # Key information for active processes
        if self.process.is_active and self.process.person.fpr:
            from keyring.models import Key
            try:
                key = Key.objects.get_or_download(self.process.person.fpr)
            except RuntimeError as e:
                key = None
                key_error = str(e)
            if key is not None:
                keycheck = key.keycheck()
                uids = []
                for ku in keycheck.uids:
                    uids.append({
                        "name": ku.uid.name.replace("@", ", "),
                        "remarks": " ".join(sorted(ku.errors)) if ku.errors else "ok",
                        "sigs_ok": len(ku.sigs_ok),
                        "sigs_no_key": len(ku.sigs_no_key),
                        "sigs_bad": len(ku.sigs_bad)
                    })

                ctx["keycheck"] = {
                    "main": {
                        "remarks": " ".join(sorted(keycheck.errors)) if keycheck.errors else "ok",
                    },
                    "uids": uids,
                    "updated": key.check_sigs_updated,
                }
            else:
                ctx["keycheck"] = {
                    "main": {
                        "remarks": key_error
                    }
                }

        return ctx

    def build_wizards(self, process):
        wizards = []
        # TODO: add a wizard for free-form action
        # TODO: for each wizard, generate a form, which may or may not have a
        # "next status" field (generally not), and can have a default text in
        # the text area. Also, (pre)generate the template emails.
        if process.applying_for == const.STATUS_DC_GA or process.applying_for == const.STATUS_DM_GA:
            if self.visitor.is_admin and process.progress == const.PROGRESS_APP_NEW:
                wizards.append({
                    "label": "Approve",
                    "prog_to": const.PROGRESS_DAM_OK,
                    "show_dam_mail": True,
                    "mail_template": "dam",
                })

        if process.applying_for == const.STATUS_DD_U or process.applying_for == const.STATUS_DD_NU:
            if process.progress == const.PROGRESS_AM_RCVD:
                wizards.append({
                    "label": "Confirm assignment",
                    "prog_to": const.PROGRESS_AM,
                })
            if process.progress == const.PROGRESS_AM:
                wizards.append({
                    "label": "ID check ok",
                    "prog_to": const.PROGRESS_AM,
                    "logtext": "ID check passed",
                })
                wizards.append({
                    "label": "P&P ok",
                    "prog_to": const.PROGRESS_AM,
                    "logtext": "P&P check passed",
                })
                wizards.append({
                    "label": "T&S ok",
                    "prog_to": const.PROGRESS_AM,
                    "logtext": "T&S check passed",
                })
                wizards.append({
                    "label": "Approve applicant",
                    "prog_to": const.PROGRESS_AM_OK,
                    "logtext": "Please enter personal comment about applicant for the process log.\nMake sure all your communication with the NM has been Cc'ed or forwarded to the archive mailbox.\nOn submitting, the system will announce the approval in a summary message including the applicant's bio to nm@debian.org.",
                    "mail_template": "am",
                })
                wizards.append({
                    "label": "On hold",
                    "prog_to": const.PROGRESS_AM_HOLD,
                    "logtext": "Please enter reason for hold",
                })
            if process.progress == const.PROGRESS_AM_HOLD:
                wizards.append({
                    "label": "Back from hold",
                    "prog_to": const.PROGRESS_AM,
                })
            if process.progress in [const.PROGRESS_AM_RCVD, const.PROGRESS_AM, const.PROGRESS_AM_HOLD]:
                w = {
                    "label": "Unassign",
                    "prog_to": const.PROGRESS_APP_OK,
                }
                if self.visitor.is_admin:
                    w["logtext"] = "Unassigned from {} [TODO: please enter a reason]".format(process.manager.person.uid)
                else:
                    w["logtext"] = "Handing applicant back to Front Desk. [TODO: please enter a reason] [TODO: please send the mailbox with all your conversation so far to nm@debian.org]"
                wizards.append(w)
            if self.visitor.is_admin:
                if process.progress == const.PROGRESS_ADV_RCVD:
                    wizards.append({
                        "label": "Hold",
                        "prog_to": const.PROGRESS_APP_HOLD,
                        "logtext": "Please enter reason for hold",
                    })
                    wizards.append({
                        "label": "Advocacies ok",
                        "prog_to": const.PROGRESS_POLL_SENT,
                    })
                if process.progress == const.PROGRESS_POLL_SENT:
                    wizards.append({
                        "label": "Activity poll answer received",
                        "prog_to": const.PROGRESS_APP_OK,
                    })
                if process.progress == const.PROGRESS_APP_HOLD:
                    wizards.append({
                        "label": "Unhold",
                        "prog_to": const.PROGRESS_ADV_RCVD,
                    })
                    #TODO: assign AM, field with uid and macros to fill it with a list of free ones
                    #    ("PROGRESS_APP_OK",    "app_ok",    "Advocacies have been approved"),
                if process.progress == const.PROGRESS_AM_OK:
                    wizards.append({
                        "label": "FD hold",
                        "prog_to": const.PROGRESS_FD_HOLD,
                        "logtext": "Please enter reason for hold",
                    })
                    wizards.append({
                        "label": "FD approve",
                        "prog_to": const.PROGRESS_FD_OK,
                    })
                if process.progress == const.PROGRESS_FD_OK:
                    wizards.append({
                        "label": "Unhold",
                        "prog_to": const.PROGRESS_AM_OK,
                    })
                if self.visitor.am.is_dam:
                    if process.progress == const.PROGRESS_FD_OK:
                        wizards.append({
                            "label": "DAM hold",
                            "prog_to": const.PROGRESS_DAM_HOLD,
                            "logtext": "Please enter reason for hold",
                        })
                        wizards.append({
                            "label": "DAM approve",
                            "prog_to": const.PROGRESS_DAM_OK,
                            "mail_template": "dam",
                        })
                    if process.progress == const.PROGRESS_DAM_HOLD:
                        wizards.append({
                            "label": "Unhold",
                            "prog_to": const.PROGRESS_FD_OK,
                        })
        return wizards

    def post(self, request, key, *args, **kw):
        if not self.visitor: raise PermissionDenied()
        am = self.visitor.am_or_none
        if not am: raise PermissionDenied

        StatusUpdateForm = make_statusupdateform(am)
        form = StatusUpdateForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["progress"] == const.PROGRESS_APP_OK \
                and self.process.progress in [const.PROGRESS_AM_HOLD, const.PROGRESS_AM, const.PROGRESS_AM_RCVD]:
                # Unassign from AM
                self.process.manager = None
            self.process.progress = form.cleaned_data["progress"]
            self.process.save()
            text = form.cleaned_data["logtext"]
            if self.impersonator:
                text = "[%s as %s] %s" % (self.impersonator,
                                            self.visitor.lookup_key,
                                            text)
            log = bmodels.Log(
                changed_by=self.visitor,
                process=self.process,
                progress=self.process.progress,
                logtext=text,
                is_public=form.cleaned_data["log_is_public"]
            )
            log.save()
            form = StatusUpdateForm(initial=dict(progress=self.process.progress))

        context = self.get_context_data(**kw)
        return self.render_to_response(context)


class ProcessUpdateKeycheck(VisitProcessMixin, View):
    require_visit_perms = "update_keycheck"

    def post(self, request, key, *args, **kw):
        from keyring.models import Key
        try:
            key = Key.objects.get_or_download(self.person.fpr)
        except RuntimeError as e:
            key = None
        if key is not None:
            key.update_key()
            key.update_check_sigs()
        return redirect(self.process.get_absolute_url())


SIMPLIFY_STATUS = {
    const.STATUS_DC: "new",
    const.STATUS_DC_GA: "new",
    const.STATUS_DM: "dm",
    const.STATUS_DM_GA: "dm",
    const.STATUS_DD_U: "dd",
    const.STATUS_DD_NU: "dd",
    const.STATUS_EMERITUS_DD: "emeritus",
    const.STATUS_EMERITUS_DM: "emeritus",
    const.STATUS_REMOVED_DD: "removed",
    const.STATUS_REMOVED_DM: "removed",
}

class People(VisitorTemplateView):
    template_name = "public/people.html"
    def get_context_data(self, **kw):
        ctx = super(People, self).get_context_data(**kw)
        status = self.kwargs.get("status", None)

        #def people(request, status=None):
        objects = bmodels.Person.objects.all().order_by("uid", "sn", "cn")
        show_status = True
        status_sdesc = None
        status_ldesc = None
        if status:
            if status == "dm_all":
                objects = objects.filter(status__in=(const.STATUS_DM, const.STATUS_DM_GA))
                status_sdesc = _("Debian Maintainer")
                status_ldesc = _("Debian Maintainer (with or without guest account)")
            elif status == "dd_all":
                objects = objects.filter(status__in=(const.STATUS_DD_U, const.STATUS_DD_NU))
                status_sdesc = _("Debian Developer")
                status_ldesc = _("Debian Developer (uploading or not)")
            else:
                objects = objects.filter(status=status)
                show_status = False
                status_sdesc = lookup_or_404(const.ALL_STATUS_BYTAG, status).sdesc
                status_ldesc = lookup_or_404(const.ALL_STATUS_BYTAG, status).sdesc

        people = []
        for p in objects:
            p.simple_status = SIMPLIFY_STATUS.get(p.status, None)
            people.append(p)

        ctx.update(
            people=people,
            status=status,
            show_status=show_status,
            status_sdesc=status_sdesc,
            status_ldesc=status_ldesc,
        )
        return ctx

class AuditLog(VisitorTemplateView):
    template_name = "public/audit_log.html"
    require_visitor = "dd"

    def get_context_data(self, **kw):
        ctx = super(AuditLog, self).get_context_data(**kw)

        audit_log = []
        is_admin = self.visitor.is_admin
        cutoff = now() - datetime.timedelta(days=30)
        for e in bmodels.PersonAuditLog.objects.filter(logdate__gte=cutoff).order_by("-logdate"):
            if is_admin:
                changes = sorted((k, v[0], v[1]) for k, v in json.loads(e.changes).items())
            else:
                changes = sorted((k, v[0], v[1]) for k, v in json.loads(e.changes).items() if k != "fd_comment")
            audit_log.append({
                "person": e.person,
                "logdate": e.logdate,
                "author": e.author,
                "notes": e.notes,
                "changes": changes,
            })

        ctx["audit_log"] = audit_log
        return ctx

class Progress(VisitorTemplateView):
    template_name = "public/progress.html"

    def get_context_data(self, **kw):
        ctx = super(Progress, self).get_context_data(**kw)
        progress = self.kwargs["progress"]

        from django.db.models import Min, Max

        processes = bmodels.Process.objects.filter(progress=progress, is_active=True) \
                .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                .order_by("started")

        ctx.update(
            progress=progress,
            processes=processes,
        )
        return ctx

class Stats(VisitorTemplateView):
    template_name = "public/stats.html"

    def get_context_data(self, **kw):
        ctx = super(Stats, self).get_context_data(**kw)
        from django.db.models import Count

        dtnow = now()
        stats = {}

        # Count of people by status
        by_status = dict()
        for row in bmodels.Person.objects.values("status").annotate(Count("status")):
            by_status[row["status"]] = row["status__count"]
        stats["by_status"] = by_status

        # Count of applicants by progress
        by_progress = dict()
        for row in bmodels.Process.objects.filter(is_active=True).values("progress").annotate(Count("progress")):
            by_progress[row["progress"]] = row["progress__count"]
        stats["by_progress"] = by_progress

        # Cook up more useful bits for the templates

        ctx["stats"] = stats

        status_table = []
        for status in (s.tag for s in const.ALL_STATUS):
            status_table.append((status, by_status.get(status, 0)))
        ctx["status_table"] = status_table
        ctx["status_table_json"] = json.dumps([(s.sdesc, by_status.get(s.tag, 0)) for s in const.ALL_STATUS])

        progress_table = []
        for progress in (s.tag for s in const.ALL_PROGRESS):
            progress_table.append((progress, by_progress.get(progress, 0)))
        ctx["progress_table"] = progress_table
        ctx["progress_table_json"] = json.dumps([(p.sdesc, by_progress.get(p.tag, 0)) for p in const.ALL_PROGRESS])

        # List of active processes with statistics
        active_processes = []
        #for p in bmodels.Process.objects.filter(is_active=True):
        #    p.annotate_with_duration_stats()
        #    mbox_mtime = p.mailbox_mtime
        #    if mbox_mtime is None:
        #        p.mbox_age = None
        #    else:
        #        p.mbox_age = (dtnow - mbox_mtime).days
        #    active_processes.append(p)
        #    if self.visitor and self.visitor.is_admin:
        #        pathname = p.mailbox_file
        #        if pathname:
        #            p.mbox_stats = []
        #            for idx, (addr, length) in enumerate(mailbox_get_gaps(pathname)):
        #                neg = 1 if idx % 2 == 0 else -1
        #                p.mbox_stats.append(neg * min(round(length/86400), 30))
        #        else:
        #            p.mbox_stats = None

        import process.models as pmodels
        from process.mixins import compute_process_status
        for p in pmodels.Process.objects.filter(closed__isnull=True):
            active_processes.append((p, compute_process_status(p, self.visitor)))

        active_processes.sort(key=lambda x:(x[1]["log_first"].logdate if x[1]["log_first"] else None))
        ctx["active_processes"] = active_processes

        return ctx

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        # If JSON is requested, dump them right away
        if 'json' in request.GET:
            res = http.HttpResponse(content_type="application/json")
            res["Content-Disposition"] = "attachment; filename=stats.json"
            json.dump(context["stats"], res, indent=1)
            return res
        else:
            return self.render_to_response(context)


def make_findperson_form(request, visitor):
    includes = ["cn", "mn", "sn", "email", "uid", "status"]

    if visitor and visitor.is_admin:
        includes.append("username")
        includes.append("fd_comment")

    class FindpersonForm(forms.ModelForm):
        fpr = forms.CharField(label="Fingerprint", required=False, min_length=40, widget=forms.TextInput(attrs={"size": 60}))

        class Meta:
            model = bmodels.Person
            fields = includes

        def clean_fpr(self):
            return bmodels.FingerprintField.clean_fingerprint(self.cleaned_data['fpr'])

    return FindpersonForm

class Findperson(VisitorMixin, FormView):
    template_name = "public/findperson.html"

    def get_form_class(self):
        return make_findperson_form(self.request, self.visitor)

    def form_valid(self, form):
        if not self.visitor or not self.visitor.is_admin:
            raise PermissionDenied()

        person = form.save(commit=False)
        person.save(audit_author=self.visitor, audit_notes="user created manually")
        fpr = form.cleaned_data["fpr"]
        if fpr:
            bmodels.Fingerprint.objects.create(fpr=fpr, person=person, is_active=True, audit_author=self.visitor, audit_notes="user created manually")
        return redirect(person.get_absolute_url())


class StatsLatest(VisitorTemplateView):
    template_name = "public/stats_latest.html"

    def compute_stats(self):
        from django.db.models import Count, Min, Max

        days = int(self.request.GET.get("days", "7"))
        threshold = now().replace(hour=0, minute=0, second=0, microsecond=0) - datetime.timedelta(days=days)

        raw_counts = dict((x.tag, 0) for x in const.ALL_PROGRESS)
        for p in bmodels.Process.objects.values("progress").annotate(count=Count("id")).filter(is_active=True):
            raw_counts[p["progress"]] = p["count"]

        counts = dict(
            new=raw_counts[const.PROGRESS_APP_NEW] + raw_counts[const.PROGRESS_APP_RCVD] + raw_counts[const.PROGRESS_ADV_RCVD],
            new_hold=raw_counts[const.PROGRESS_APP_HOLD],
            new_ok=raw_counts[const.PROGRESS_APP_OK],
            am=raw_counts[const.PROGRESS_AM_RCVD] + raw_counts[const.PROGRESS_AM],
            am_hold=raw_counts[const.PROGRESS_AM_HOLD],
            fd=raw_counts[const.PROGRESS_AM_OK],
            fd_hold=raw_counts[const.PROGRESS_FD_HOLD],
            dam=raw_counts[const.PROGRESS_FD_OK],
            dam_hold=raw_counts[const.PROGRESS_DAM_HOLD],
            dam_ok=raw_counts[const.PROGRESS_DAM_OK],
        )

        irc_topic = "New %(new)d+%(new_hold)d ok %(new_ok)d | AM: %(am)d+%(am_hold)d | FD: %(fd)d+%(fd_hold)d | DAM: %(dam)d+%(dam_hold)d ok %(dam_ok)d" % counts

        events = []

        # Collect status change events
        for p in bmodels.Person.objects.filter(status_changed__gte=threshold).order_by("-status_changed"):
            events.append(dict(
                type="status",
                time=p.status_changed,
                person=p,
            ))

        # Collect progress change events
        for pr in bmodels.Process.objects.filter(is_active=True):
            old_progress = None
            for l in pr.log.order_by("logdate"):
                if l.progress != old_progress:
                    if l.logdate.date() >= threshold:
                        events.append(dict(
                            type="progress",
                            time=l.logdate,
                            person=pr.person,
                            log=l,
                        ))
                    old_progress = l.progress

        events.sort(key=lambda x:x["time"])
        return {
            "counts": counts,
            "raw_counts": raw_counts,
            "irc_topic": irc_topic,
            "events": events,
        }

    def get(self, request, *args, **kw):
        # If JSON is requested, dump them right away
        if 'json' in self.request.GET:
            ctx = self.compute_stats()
            json_evs = []
            for e in ctx["events"]:
                ne = dict(
                    status_changed_dt=e["time"].strftime("%Y-%m-%d %H:%M:%S"),
                    status_changed_ts=e["time"].strftime("%s"),
                    uid=e["person"].uid,
                    fn=e["person"].fullname,
                    key=e["person"].lookup_key,
                    type=e["type"],
                )
                if e["type"] == "status":
                    ne.update(
                        status=e["person"].status,
                    )
                elif e["type"] == "progress":
                    ne.update(
                        process_key=e["log"].process.lookup_key,
                        progress=e["log"].progress,
                    )
                json_evs.append(ne)
            ctx["events"] = json_evs
            res = http.HttpResponse(content_type="application/json")
            res["Content-Disposition"] = "attachment; filename=stats.json"
            json.dump(ctx, res, indent=1)
            return res
        else:
            return super(StatsLatest, self).get(request, *args, **kw)

    def get_context_data(self, **kw):
        ctx = super(StatsLatest, self).get_context_data(**kw)
        ctx.update(**self.compute_stats())
        return ctx


class StatsGraph(VisitorTemplateView):
    template_name = "public/stats_graph.html"

    def get_context_data(self, **kw):
        ctx = super(StatsGraph, self).get_context_data(**kw)
        from django.db import connection

        cursor = connection.cursor()
        cursor.execute("""
        SELECT am_person.uid AS am_uid, nm_person.uid AS nm_uid
        FROM person am_person
        JOIN am ON (am_person.id = am.person_id)
        JOIN process p ON (am.id = p.manager_id)
        JOIN person nm_person ON (p.person_id = nm_person.id);
        """)
        am_nm = []
        for am_uid, nm_uid in cursor:
            am_nm.append((am_uid, nm_uid))

        cursor = connection.cursor()
        cursor.execute("""
        SELECT adv_person.uid AS adv_uid, nm_person.uid AS nm_uid
        FROM person adv_person
        JOIN process_advocates adv ON (adv_person.id = adv.person_id)
        JOIN process p ON (adv.process_id = p.id)
        JOIN person nm_person ON (p.person_id = nm_person.id);
        """)
        adv_nm = []
        for adv_uid, nm_uid in cursor:
            adv_nm.append((adv_uid, nm_uid))

        ctx = dict(
            am_nm=am_nm,
            adv_nm=adv_nm,
        )

        return ctx

YESNO = (
        ("yes", "Yes"),
        ("no", "No"),
)

class NewPersonForm(forms.ModelForm):
    fpr = forms.CharField(label="Fingerprint", min_length=40, widget=forms.TextInput(attrs={"size": 60}))
    sc_ok = forms.ChoiceField(choices=YESNO, widget=forms.RadioSelect(), label="SC and DFSG agreement")
    dmup_ok = forms.ChoiceField(choices=YESNO, widget=forms.RadioSelect(), label="DMUP agreement")

    def clean_fpr(self):
        data = bmodels.FingerprintField.clean_fingerprint(self.cleaned_data['fpr'])
        if bmodels.Fingerprint.objects.filter(fpr=data).exists():
            raise forms.ValidationError("The GPG fingerprint is already known to this system. Please contact Front Desk to link your Alioth account to it.")
        return data

    def clean_sc_ok(self):
        data = self.cleaned_data['sc_ok']
        if data != "yes":
            raise forms.ValidationError("You need to agree with the Debian Social Contract and DFSG to continue")
        return data

    def clean_dmup_ok(self):
        data = self.cleaned_data['dmup_ok']
        if data != "yes":
            raise forms.ValidationError("You need to agree with the DMUP to continue")
        return data

    class Meta:
        model = bmodels.Person
        fields = ["cn", "mn", "sn", "email", "bio", "uid"]
        widgets = {
            "bio": forms.Textarea(attrs={'cols': 80, 'rows': 25}),
        }

class Newnm(VisitorMixin, FormView):
    """
    Display the new Person form
    """
    template_name = "public/newnm.html"
    form_class = NewPersonForm
    DAYS_VALID = 3

    def get_success_url(self):
        return redirect("public_newnm_resend_challenge", key=self.request.user.lookup_key)

    def form_valid(self, form):
        if self.visitor is not None: raise PermissionDenied
        if self.request.sso_username is None: raise PermissionDenied

        person = form.save(commit=False)
        person.username = self.request.sso_username
        person.status = const.STATUS_DC
        person.status_changed = now()
        person.make_pending(days_valid=self.DAYS_VALID)
        person.save(audit_author=person, audit_notes="new subscription to the site")
        fpr = form.cleaned_data["fpr"]
        bmodels.Fingerprint.objects.create(person=person, fpr=fpr, is_active=True, audit_author=person, audit_notes="new subscription to the site")

        # Redirect to the send challenge page
        return redirect("public_newnm_resend_challenge", key=person.lookup_key)

    def get_context_data(self, **kw):
        ctx = super(Newnm, self).get_context_data(**kw)
        form = ctx["form"]
        errors = []
        for k, v in form.errors.iteritems():
            if k in ("cn", "mn", "sn"):
                section = "name"
            elif k in ("sc_ok", "dmup_ok"):
                section = "rules"
            else:
                section = k
            errors.append({
                "section": section,
                "label": form.fields[k].label,
                "id": k,
                "errors": v,
            })

        has_entry = self.visitor is not None
        is_dd = self.visitor and "dd" in self.visitor.perms
        require_login = self.request.sso_username is None
        show_apply_form = not require_login and (not has_entry or is_dd)

        ctx.update(
            person=self.visitor,
            form=form,
            errors=errors,
            has_entry=has_entry,
            is_dd=is_dd,
            show_apply_form=show_apply_form,
            require_login=require_login,
            DAYS_VALID=self.DAYS_VALID,
            wikihelp="https://wiki.debian.org/nm.debian.org/Newnm",
        )
        return ctx


class NewnmResendChallenge(VisitorMixin, View):
    """
    Send/resend the encrypted email nonce for people who just requested a new
    Person record
    """
    def get(self, request, key=None, *args, **kw):
        from keyring.models import Key

        if self.visitor is None: raise PermissionDenied()

        # Deal gracefully with someone clicking the reconfirm link after they have
        # already confirmed
        if not self.visitor.pending: return redirect(self.visitor.get_absolute_url())

        confirm_url = request.build_absolute_uri(reverse("public_newnm_confirm", kwargs=dict(nonce=self.visitor.pending)))
        plaintext = "Please visit {} to confirm your application at {}\n".format(
                confirm_url,
                request.build_absolute_uri(self.visitor.get_absolute_url()))
        key = Key.objects.get_or_download(self.visitor.fpr)
        if not key.key_is_fresh(): key.update_key()
        encrypted = key.encrypt(plaintext.encode("utf8"))
        bemail.send_nonce("notification_mails/newperson.txt", self.visitor, encrypted_nonce=encrypted)
        return redirect(self.visitor.get_absolute_url())


class NewnmConfirm(VisitorMixin, View):
    """
    Confirm a pending Person object, given its nonce
    """
    def get(self, request, nonce, *args, **kw):
        if self.visitor is None: raise PermissionDenied
        if self.visitor.pending != nonce: raise PermissionDenied
        self.visitor.pending = ""
        self.visitor.expires = now() + datetime.timedelta(days=30)
        self.visitor.save(audit_author=self.visitor, audit_notes="confirmed pending subscription")
        return redirect(self.visitor.get_absolute_url())
