from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.urls import reverse
from django.shortcuts import redirect, get_object_or_404
from django import forms
from django.core.exceptions import PermissionDenied
from backend.mixins import VisitPersonMixin
from django.db import transaction
import backend.models as bmodels
import re


class NewFingerprintForm(forms.ModelForm):
    class Meta:
        model = bmodels.Fingerprint
        fields = ["fpr"]


class PersonFingerprints(VisitPersonMixin, FormView):
    template_name = "fprs/list.html"
    require_visit_perms = "edit_ldap"
    form_class = NewFingerprintForm

    @transaction.atomic
    def form_valid(self, form):
        fpr = form.save(commit=False)
        fpr.person = self.person
        fpr.is_active = True
        fpr.save(audit_author=self.visitor, audit_notes="added new fingerprint")
        # Ensure that only the new fingerprint is the active one
        self.person.fprs.exclude(pk=fpr.pk).update(is_active=False)
        return redirect("fprs_person_list", key=self.person.lookup_key)


class FingerprintMixin(VisitPersonMixin):
    def pre_dispatch(self):
        super(FingerprintMixin, self).pre_dispatch()
        self.fpr = get_object_or_404(bmodels.Fingerprint, fpr=self.kwargs["fpr"])
        if self.fpr.person.pk != self.person.pk:
            raise PermissionDenied

    def get_context_data(self, **kw):
        ctx = super(FingerprintMixin, self).get_context_data(**kw)
        ctx["fpr"] = self.fpr
        ctx["keyid"] = self.fpr.fpr[-16:]
        return ctx


class SetActiveFingerprint(FingerprintMixin, View):
    require_visit_perms = "edit_ldap"

    @transaction.atomic
    def post(self, request, *args, **kw):
        # Set all other fingerprints as not active
        for f in self.person.fprs.filter(is_active=True).exclude(pk=self.fpr.pk):
            f.is_active = False
            f.save(audit_author=self.visitor, audit_notes="activated fingerprint {}".format(self.fpr.fpr))

        # Set this fingerprint as active
        if not self.fpr.is_active:
            self.fpr.is_active = True
            self.fpr.save(audit_author=self.visitor, audit_notes="activated fingerprint {}".format(self.fpr.fpr))

        return redirect("fprs_person_list", key=self.person.lookup_key)
