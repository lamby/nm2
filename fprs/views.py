# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, get_object_or_404
from django import forms
from django.core.exceptions import PermissionDenied
from backend.mixins import VisitPersonMixin
from django.db import transaction
import backend.models as bmodels


class NewFingerprintForm(forms.ModelForm):
    class Meta:
        model = bmodels.Fingerprint
        fields = ["fpr"]


class PersonFingerprints(VisitPersonMixin, FormView):
    template_name = "fprs/list.html"
    require_vperms = "edit_ldap"
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


class SetActiveFingerprint(VisitPersonMixin, View):
    require_vperms = "edit_ldap"

    @transaction.atomic
    def post(self, request, key, fpr, *args, **kw):
        fpr = get_object_or_404(bmodels.Fingerprint, fpr=fpr)
        if fpr.person.pk != self.person.pk:
            raise PermissionDenied

        # Set all other fingerprints as not active
        for f in self.person.fprs.filter(is_active=True).exclude(pk=fpr.pk):
            f.is_active = False
            f.save(audit_author=self.visitor, audit_notes="activated fingerprint {}".format(fpr.fpr))

        # Set this fingerprint as active
        if not fpr.is_active:
            fpr.is_active = True
            fpr.save(audit_author=self.visitor, audit_notes="activated fingerprint {}".format(fpr.fpr))

        return redirect("fprs_person_list", key=self.person.lookup_key)


class Endorsement(VisitPersonMixin, FormView):
    # TODO: work in progress
    template_name = "fprs/endorsement.html"
    require_vperms = "edit_ldap"
    form_class = NewFingerprintForm

    @transaction.atomic
    def form_valid(self, form):
        #fpr = form.save(commit=False)
        #fpr.person = self.person
        #fpr.is_active = True
        #fpr.save(audit_author=self.visitor, audit_notes="added new fingerprint")
        ## Ensure that only the new fingerprint is the active one
        #self.person.fprs.exclude(pk=fpr.pk).update(is_active=False)
        return redirect("fprs_person_list", key=self.person.lookup_key)
