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
from backend import const
from backend.mixins import VisitorMixin, VisitPersonMixin, VisitorTemplateView, VisitPersonTemplateView, VisitProcessMixin
import backend.email
import json
import datetime
import os

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
