# coding: utf8
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
from django.shortcuts import redirect, render, get_object_or_404
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext as _
from django.utils.timezone import now
from django.views.generic import TemplateView
import backend.models as bmodels
import backend.email as bemail
from backend import const
from backend.mixins import VisitorMixin, VisitorTemplateView, VisitPersonTemplateView
import markdown
import datetime
import json

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

class Process(VisitorTemplateView):
    template_name = "public/process.html"

    def get_context_data(self, **kw):
        ctx = super(Process, self).get_context_data(**kw)
        key = self.kwargs["key"]
        process = bmodels.Process.lookup_or_404(key)
        perms = process.permissions_of(self.visitor)

        ctx.update(
            process=process,
            person=process.person,
            perms=perms,
        )

        # Process form ASAP, so we compute the rest with updated values
        am = self.visitor.am_or_none if self.visitor else None
        if am and (process.manager == am or am.is_admin) and (
            "edit_bio" in perms.perms or "edit_ldap" in perms.perms):
            StatusUpdateForm = make_statusupdateform(am)
            form = StatusUpdateForm(initial=dict(progress=process.progress))
        else:
            form = None

        ctx["form"] = form

        log = list(process.log.order_by("logdate", "progress"))
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
        curstep = unusual_step_map.get(process.progress, process.progress)

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

        return ctx

    def post(self, request, key, *args, **kw):
        process = bmodels.Process.lookup_or_404(key)
        if not self.visitor: raise PermissionDenied()
        am = self.visitor.am_or_none
        if not am: raise PermissionDenied

        StatusUpdateForm = make_statusupdateform(am)
        form = StatusUpdateForm(request.POST)
        if form.is_valid():
            if form.cleaned_data["progress"] == const.PROGRESS_APP_OK \
                and process.progress in [const.PROGRESS_AM_HOLD, const.PROGRESS_AM, const.PROGRESS_AM_RCVD]:
                # Unassign from AM
                process.manager = None
            process.progress = form.cleaned_data["progress"]
            process.save()
            text = form.cleaned_data["logtext"]
            if self.impersonator:
                text = "[%s as %s] %s" % (self.impersonator,
                                            self.visitor.lookup_key,
                                            text)
            log = bmodels.Log(
                changed_by=self.visitor,
                process=process,
                progress=process.progress,
                logtext=text,
                is_public=form.cleaned_data["log_is_public"]
            )
            log.save()
            form = StatusUpdateForm(initial=dict(progress=process.progress))

        context = self.get_context_data(**kw)
        return self.render_to_response(context)


SIMPLIFY_STATUS = {
    const.STATUS_MM: "new",
    const.STATUS_MM_GA: "new",
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
                status_sdesc = const.ALL_STATUS_BYTAG[status].sdesc
                status_ldesc = const.ALL_STATUS_BYTAG[status].sdesc

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

class Person(VisitPersonTemplateView):
    template_name = "public/person.html"

    def get_context_data(self, **kw):
        from django.db.models import Min, Max
        ctx = super(Person, self).get_context_data(**kw)

        processes = self.person.processes \
                .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                .order_by("is_active", "ended")

        if self.person.is_am:
            am = self.person.am
            am_processes = am.processed \
                    .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                    .order_by("is_active", "ended")
        else:
            am = None
            am_processes = []

        ctx.update(
            person=self.person,
            am=am,
            processes=processes,
            am_processes=am_processes,
            vperms=self.vperms,
            adv_processes=self.person.advocated \
                    .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                    .order_by("is_active", "ended")
        )


        if self.person.bio is not None:
            ctx["bio_html"] = markdown.markdown(self.person.bio, safe_mode="escape")
        else:
            ctx["bio_html"] = ""
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

        # If JSON is requested, dump them right away
        if 'json' in self.request.GET:
            res = http.HttpResponse(content_type="application/json")
            res["Content-Disposition"] = "attachment; filename=stats.json"
            json.dump(stats, res, indent=1)
            return res

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
        for p in bmodels.Process.objects.filter(is_active=True):
            p.annotate_with_duration_stats()
            mbox_mtime = p.mailbox_mtime
            if mbox_mtime is None:
                p.mbox_age = None
            else:
                p.mbox_age = (dtnow - mbox_mtime).days
            active_processes.append(p)
        active_processes.sort(key=lambda x:(x.log_first.logdate if x.log_first else None))
        ctx["active_processes"] = active_processes

        return ctx

def make_findperson_form(request, visitor):
    includes = ["cn", "mn", "sn", "email", "uid", "fpr", "status"]

    if visitor and visitor.is_admin:
        includes.append("fd_comment")

    class FindpersonForm(forms.ModelForm):
        class Meta:
            model = bmodels.Person
            fields = includes
    return FindpersonForm

class Findperson(VisitorTemplateView):
    template_name = "public/findperson.html"

    def get_context_data(self, **kw):
        ctx = super(Findperson, self).get_context_data(**kw)
        FindpersonForm = make_findperson_form(self.request, self.visitor)
        form = FindpersonForm()
        ctx["form"] = form
        return ctx

    def post(self, request, *args, **kw):
        if not self.visitor or not self.visitor.is_admin:
            raise PermissionDenied()

        FindpersonForm = make_findperson_form(request, self.visitor)
        form = FindpersonForm(request.POST)
        if form.is_valid():
            person = form.save()
            return redirect(person.get_absolute_url())

        context = self.get_context_data(**kw)
        return self.render_to_response(context)


class StatsLatest(VisitorTemplateView):
    template_name = "public/stats_latest.html"

    def get_context_data(self, **kw):
        ctx = super(StatsLatest, self).get_context_data(**kw)
        from django.db.models import Count, Min, Max

        days = int(self.request.GET.get("days", "7"))
        threshold = datetime.date.today() - datetime.timedelta(days=days)

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

        ctx = dict(
            counts=counts,
            raw_counts=raw_counts,
            irc_topic=irc_topic,
            events=events,
        )

        # If JSON is requested, dump them right away
        if 'json' in self.request.GET:
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

        return ctx

YESNO = (
        ("yes", "Yes"),
        ("no", "No"),
)

class NewPersonForm(forms.ModelForm):
    sc_ok = forms.ChoiceField(choices=YESNO, widget=forms.RadioSelect(), label="SC and DFSG agreement")
    dmup_ok = forms.ChoiceField(choices=YESNO, widget=forms.RadioSelect(), label="DMUP agreement")

    def __init__(self, *args, **kwargs):
        super(NewPersonForm, self).__init__(*args, **kwargs)
        self.fields["fpr"].required = True

    def clean_fpr(self):
        fpr = self.cleaned_data['fpr']
        if fpr is not None:
            return fpr.replace(' ', '')
        return fpr

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
        fields = ["cn", "mn", "sn", "email", "bio", "uid", "fpr"]
        widgets = {
            "fpr": forms.TextInput(attrs={'size': 60}),
            "bio": forms.Textarea(attrs={'cols': 80, 'rows': 25}),
        }

def newnm(request):
    """
    Display the new Person form
    """
    DAYS_VALID = 3

    if request.method == 'POST':
        form = NewPersonForm(request.POST)
        if form.is_valid():
            person = form.save(commit=False)
            person.status = const.STATUS_MM
            person.status_changed = now()
            person.make_pending(days_valid=DAYS_VALID)
            person.save()
            # Redirect to the send challenge page
            return redirect("public_newnm_resend_challenge", key=person.lookup_key)
    else:
        form = NewPersonForm()
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
    return render(request, "public/newnm.html", {
        "form": form,
        "errors": errors,
        "DAYS_VALID": DAYS_VALID,
    })

def newnm_resend_challenge(request, key):
    """
    Send/resend the encrypted email nonce for people who just requested a new
    Person record
    """
    from keyring.models import UserKey
    person = bmodels.Person.lookup_or_404(key)

    # Deal gracefully with someone clicking the reconfirm link after they have
    # already confirmed
    if not person.pending: return redirect(person.get_absolute_url())

    confirm_url = request.build_absolute_uri(reverse("public_newnm_confirm", kwargs=dict(nonce=person.pending)))
    plaintext = "Please visit {} to confirm your application at {}\n".format(
            confirm_url,
            request.build_absolute_uri(person.get_absolute_url()))
    key = UserKey(person.fpr)
    encrypted = key.encrypt(plaintext.encode("utf8"))
    bemail.send_nonce("notification_mails/newperson.txt", person, encrypted_nonce=encrypted)
    return redirect(person.get_absolute_url())

def newnm_confirm(request, nonce):
    """
    Confirm a pending Person object, given its nonce
    """
    person = get_object_or_404(bmodels.Person, pending=nonce)
    person.pending = ""
    person.expires = now() + datetime.timedelta(days=30)
    person.save()
    return redirect(person.get_absolute_url())

