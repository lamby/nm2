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


class EndorsementForm(forms.Form):
    agreement = forms.CharField(label="Agreement", widget=forms.Textarea(attrs={"rows": 25, "cols": 80}))

    def __init__(self, *args, **kw):
        self.fpr = kw.pop("fpr")
        super(EndorsementForm, self).__init__(*args, **kw)

    def clean_agreement(self):
        from keyring.models import Key
        text = self.cleaned_data["agreement"]
        key = Key.objects.get_or_download(self.fpr.fpr)
        try:
            plaintext = key.verify(text)
        except RuntimeError as e:
            raise forms.ValidationError("Cannot verify the signature: " + str(e))

        #data = bmodels.FingerprintField.clean_fingerprint(self.cleaned_data['fpr'])
        #try:
        #    fpr = bmodels.Fingerprint.objects.get(fpr=self.cleaned_data["fpr"])
        #except bmodels.Fingerprint.DoesNotExist:
        #    raise forms.ValidationError("The GPG fingerprint is not known to this system. "
        #                                "If you are a Debian Maintainer, and you entered the fingerprint that is in the DM keyring, "
        #                                "please contact Front Desk to get this fixed.")

        #if not fpr.is_active:
        #    raise forms.ValidationError("The GPG fingerprint corresponds to a key that is not currently the active key of the user.")

        #if is_valid_username(fpr.person.username):
        #    raise forms.ValidationError("The GPG fingerprint corresponds to a person that has a valid Single Sign-On username.")

        return text

class Endorsement(FingerprintMixin, FormView):
    # TODO: work in progress
    template_name = "fprs/endorsement.html"
    require_vperms = "edit_ldap"
    form_class = EndorsementForm

    def get_form_kwargs(self):
        kw = super(Endorsement, self).get_form_kwargs()
        kw["fpr"] = self.fpr
        return kw

    @transaction.atomic
    def form_valid(self, form):
        #fpr = form.save(commit=False)
        #fpr.person = self.person
        #fpr.is_active = True
        #fpr.save(audit_author=self.visitor, audit_notes="added new fingerprint")
        ## Ensure that only the new fingerprint is the active one
        #self.person.fprs.exclude(pk=fpr.pk).update(is_active=False)
        return redirect("fprs_person_list", key=self.person.lookup_key)
