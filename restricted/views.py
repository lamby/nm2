from django import http, template, forms
from django.conf import settings
from django.shortcuts import render, render_to_response, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.translation import ugettext as _
from django.urls import reverse
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

class AMProfile(VisitPersonMixin, FormView):
    # Require DD instead of AM to give access to inactive AMs
    require_visitor = "dd"
    template_name = "restricted/amprofile.html"

    def load_objects(self):
        super(AMProfile, self).load_objects()
        try:
            self.am = bmodels.AM.objects.get(person=self.person)
        except bmodels.AM.DoesNotExist:
            self.am = None

        try:
            self.visitor_am = bmodels.AM.objects.get(person=self.visitor)
        except bmodels.AM.DoesNotExist:
            self.visitor_am = None

    def check_permissions(self):
        super(AMProfile, self).check_permissions()
        if self.am is None: raise PermissionDenied
        if self.visitor_am is None: raise PermissionDenied
        if self.person.pk != self.visitor.pk and not self.visitor.is_admin:
            raise PermissionDenied

    def get_form_class(self):
        includes = ["slots", "is_am"]

        if self.visitor_am.is_fd:
            includes.append("is_fd")
        if self.visitor_am.is_dam:
            includes.append("is_dam")
        if self.visitor_am.is_admin:
            includes.append("fd_comment")

        class AMForm(forms.ModelForm):
            class Meta:
                model = bmodels.AM
                fields = includes
        return AMForm

    def get_form_kwargs(self):
        res = super(AMProfile, self).get_form_kwargs()
        res["instance"] = self.am
        return res

    def get_context_data(self, **kw):
        from django.db.models import Min
        ctx = super(AMProfile, self).get_context_data(**kw)
        ctx["am"] = self.am
        ctx["processes"] = bmodels.Process.objects.filter(manager=self.am).annotate(started=Min("log__logdate")).order_by("-started")
        return ctx

    def form_valid(self, form):
        form.save()
        return self.render_to_response(self.get_context_data(form=form))


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


class MineChangelogs(VisitorMixin, FormView):
    template_name = "restricted/minechangelogs.html"
    form_class = MinechangelogsForm

    def check_permissions(self):
        super(MineChangelogs, self).check_permissions()
        if self.visitor is None:
            raise PermissionDenied

    def load_objects(self):
        super(MineChangelogs, self).load_objects()
        self.key = self.kwargs.get("key", None)
        if self.key:
            self.person = bmodels.Person.lookup_or_404(self.key)
        else:
            self.person = None

    def get_initial(self):
        res = super(MineChangelogs, self).get_initial()
        if not self.person:
            return res

        query = [
            self.person.fullname,
            self.person.email,
        ]
        if self.person.cn and self.person.mn and self.person.sn:
            # some people don't use their middle names in changelogs
            query.append("{} {}".format(self.person.cn, self.person.sn))
        if self.person.uid:
            query.append(self.person.uid)
        return {"query": "\n".join(query)}

    def get_context_data(self, **kw):
        ctx = super(MineChangelogs, self).get_context_data(**kw)
        info = mmodels.info()
        info["max_ts"] = datetime.datetime.fromtimestamp(info["max_ts"])
        info["last_indexed"] = datetime.datetime.fromtimestamp(info["last_indexed"])
        ctx.update(
            info=info,
            person=self.person,
        )
        return ctx

    def form_valid(self, form):
        query = form.cleaned_data["query"]
        keywords = [x.strip() for x in query.split("\n")]
        entries = mmodels.query(keywords)
        if form.cleaned_data["download"]:
            def send_entries():
                for e in entries:
                    yield e
                    yield "\n\n"
            res = http.HttpResponse(send_entries(), content_type="text/plain")
            if self.person:
                res["Content-Disposition"] = 'attachment; filename=changelogs-%s.txt' % self.person.lookup_key
            else:
                res["Content-Disposition"] = 'attachment; filename=changelogs.txt'
            return res

        entries = list(entries)
        return self.render_to_response(self.get_context_data(
            form=form,
            entries=entries,
            keywords=keywords))


class Impersonate(View):
    def get(self, request, key=None, *args, **kw):
        visitor = request.user
        if not visitor.is_authenticated or not visitor.is_admin: raise PermissionDenied
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

        for email, st in list(stats["emails"].items()):
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
