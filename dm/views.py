# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.shortcuts import render
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.core import signing
from django.core.urlresolvers import reverse
from django import forms
from backend.mixins import VisitorMixin
import backend.models as bmodels

def is_valid_username(username):
    if username.endswith("@users.alioth.debian.org"): return True
    if username.endswith("@debian.org"): return True
    return False


class ClaimForm(forms.Form):
    fpr = forms.CharField(label="Fingerprint", min_length=40, widget=forms.TextInput(attrs={"size": 60}))

    def clean_fpr(self):
        data = bmodels.FingerprintField.clean_fingerprint(self.cleaned_data['fpr'])
        try:
            fpr = bmodels.Fingerprint.objects.get(fpr=self.cleaned_data["fpr"])
        except bmodels.Fingerprint.DoesNotExist:
            raise forms.ValidationError("The GPG fingerprint is not known to this system. "
                                        "If you are a Debian Maintainer, and you entered the fingerprint that is in the DM keyring, "
                                        "please contact Front Desk to get this fixed.")

        if not fpr.is_active:
            raise forms.ValidationError("The GPG fingerprint corresponds to a key that is not currently the active key of the user.")

        if is_valid_username(fpr.user.username):
            raise forms.ValidationError("The GPG fingerprint corresponds to a person that has a valid Single Sign-On username.")

        return data


class Claim(VisitorMixin, FormView):
    """
    Validate and send an encrypted HMAC url to associate an alioth account with
    a DM key
    """
    template_name = "dm/claim.html"
    form_class = ClaimForm

    def pre_dispatch(self):
        super(Claim, self).pre_dispatch()
        if self.visitor is not None: raise PermissionDenied
        if self.request.sso_username is None: raise PermissionDenied
        if not is_valid_username(self.request.sso_username): raise PermissionDenied
        self.username = self.request.sso_username

    def get_context_data(self, fpr=None, **kw):
        ctx = super(Claim, self).get_context_data(**kw)
        ctx["username"] = self.username
        if fpr:
            ctx["fpr"] = fpr
            ctx["person"] = fpr.user

            key = fpr.get_key()
            if not key.key_is_fresh(): key.update_key()
            plaintext = self.request.build_absolute_uri(reverse("dm_claim_confirm", kwargs={
                "token": signing.dumps({
                    "u": self.username,
                    "f": fpr.fpr,
                })
            }))
            plaintext += "\n"
            ctx["challenge"] = key.encrypt(plaintext.encode("utf8"))
        return ctx

    def form_valid(self, form):
        fpr = bmodels.Fingerprint.objects.get(fpr=form.cleaned_data["fpr"])
        return self.render_to_response(self.get_context_data(form=form, fpr=fpr))


class ClaimConfirm(VisitorMixin, TemplateView):
    """
    Validate the claim confirmation links
    """
    template_name = "dm/claim_confirm.html"

    def validate_token(self, token):
        parsed = signing.loads(token)
        self.errors = []

        if self.visitor is not None:
            self.errors.append("Your SSO username is already associated with a person in the system")
            return False

        # Validate fingerprint
        try:
            self.fpr = bmodels.Fingerprint.objects.get(fpr=parsed["f"])
        except bmodels.Fingerprint.DoesNotExist:
            self.fpr = None
            self.errors.append("The GPG fingerprint is not known to this system")
            return False

        if not self.fpr.is_active:
            self.errors.append("The GPG fingerprint corresponds to a key that is not currently the active key of the user.")

        if is_valid_username(self.fpr.user.username):
            self.errors.append("The GPG fingerprint corresponds to a person that has a valid Single Sign-On username.")

        # Validate username
        self.username = parsed["u"]
        if not is_valid_username(self.username):
            self.errors.append("The username does not look like a valid SSO username")

        try:
            existing_person = bmodels.Person.objects.get(username=self.username)
        except bmodels.Person.DoesNotExist:
            existing_person = None
        if existing_person is not None:
            self.errors.append("The SSO username is already associated with a different person in the system")

        return not self.errors

    def get_context_data(self, **kw):
        ctx = super(ClaimConfirm, self).get_context_data(**kw)

        if self.validate_token(self.kwargs["token"]):
            # Do the mapping
            self.fpr.person.username = self.username
            self.fpr.person.save()
            ctx["mapped"] = True
            ctx["person"] = self.fpr.person
            ctx["fpr"] = self.fpr
            ctx["username"] = self.username
        ctx["errors"] = self.errors

        return ctx
