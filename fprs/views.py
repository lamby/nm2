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
import re


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
    require_vperms = "edit_ldap"

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


class AgreementForm(forms.Form):
    agreement = forms.CharField(label="Agreement", widget=forms.Textarea(attrs={"rows": 25, "cols": 80}))

    def __init__(self, *args, **kw):
        self.fpr = kw.pop("fpr")
        super(AgreementForm, self).__init__(*args, **kw)

    def clean_agreement(self):
        from keyring.models import Key
        text = self.cleaned_data["agreement"]
        try:
            key = Key.objects.get_or_download(self.fpr.fpr)
        except RuntimeError as e:
            raise forms.ValidationError("Cannot download the key: " + str(e))

        try:
            plaintext = key.verify(text)
        except RuntimeError as e:
            raise forms.ValidationError("Cannot verify the signature: " + str(e))

        return (text, plaintext)


class ShowAgreement(FingerprintMixin, TemplateView):
    template_name = "fprs/show_agreement.html"
    require_vperms = "see_agreements"


class EditAgreement(FingerprintMixin, FormView):
    template_name = "fprs/edit_agreement.html"
    form_class = AgreementForm
    require_vperms = "edit_agreements"

    def get_form_kwargs(self):
        kw = super(EditAgreement, self).get_form_kwargs()
        kw["fpr"] = self.fpr
        return kw

    def normalise_text(self, text):
        return re.sub("\s+", " ", text).lower().strip()

    @transaction.atomic
    def form_valid(self, form):
        self.fpr.agreement, plaintext = form.cleaned_data["agreement"]
        expected = self.normalise_text(
            "I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.\n"
            "I have read the Debian Machine Usage Policy and I accept them.")
        submitted = self.normalise_text(plaintext)
        self.fpr.agreement_valid = submitted == expected
        self.fpr.save(audit_author=self.visitor, audit_notes="added SC/DFSG/DMUP agreement")
        return redirect("fprs_person_list", key=self.person.lookup_key)
