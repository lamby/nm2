# coding: utf-8
#
# Copyright (C) 2014  Enrico Zini <enrico@debian.org>
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





from django import http, forms
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, get_object_or_404
from django.utils.crypto import get_random_string
from django.utils.timezone import now
from backend.mixins import VisitorMixin
from django.views.generic.edit import FormView
from django.views.generic.base import View
from . import models as amodels
import datetime

class KeyCreateForm(forms.ModelForm):
    class Meta:
        model = amodels.Key
        fields = ("name",)

class KeyList(VisitorMixin, FormView):
    require_visitor = "dd"
    form_class = KeyCreateForm
    template_name = "apikeys/keylist.html"

    def get_context_data(self, **kw):
        ctx = super(KeyList, self).get_context_data(**kw)
        cutoff_days = 30
        cutoff = now() - datetime.timedelta(days=cutoff_days)
        ctx["keys"] = amodels.Key.objects.filter(user=self.visitor)
        ctx["audit_log"] = amodels.AuditLog.objects.filter(key__user=self.visitor, ts__gte=cutoff).order_by("-ts")
        ctx["audit_log_cutoff_days"] = cutoff_days
        ctx["key_create_form"] = KeyCreateForm()
        return ctx

    def form_valid(self, form):
        key = form.save(commit=False)
        key.user = self.visitor
        key.value = get_random_string(length=16)
        key.save()
        ctx = self.get_context_data(form=self.form_class())
        return self.render_to_response(ctx)

class KeyEnable(VisitorMixin, View):
    require_visitor = "dd"

    def post(self, request, pk, *args, **kw):
        # Get the key
        key = get_object_or_404(amodels.Key, pk=pk)

        # Ensure it's owned by the current visitor
        if key.user.pk != self.visitor.pk:
            raise PermissionDenied()

        # Set its value to what is requested
        value = request.POST["enabled"]
        if value == "1":
            if not key.enabled:
                key.enabled = True
                key.save()
        elif value == "0":
            if key.enabled:
                key.enabled = False
                key.save()
        else:
            return http.HttpResponseBadRequest("bad 'enabled' value")

        return redirect("apikeys_list")

class KeyDelete(VisitorMixin, View):
    require_visitor = "dd"

    def post(self, request, pk, *args, **kw):
        # Get the key
        key = get_object_or_404(amodels.Key, pk=pk)

        # Ensure it's owned by the current visitor
        if key.user.pk != self.visitor.pk:
            raise PermissionDenied()

        key.delete()

        return redirect("apikeys_list")
