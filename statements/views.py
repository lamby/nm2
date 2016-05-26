# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.utils.timezone import now
from django.core.urlresolvers import reverse
from django.shortcuts import redirect, get_object_or_404
from django import forms
from django.core.exceptions import PermissionDenied
from backend.mixins import VisitPersonMixin
from django.db import transaction
import backend.models as bmodels
from six.moves import shlex_quote
from . import models as smodels
import re

# Blurb used for auto-verification
AUTO_VERIFY_BLURBS = {
    "sc_dmup": [
        "I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.",
        "I have read the Debian Machine Usage Policy and I accept them."
    ]
}

STATEMENT_TYPES = dict(smodels.STATEMENT_TYPES)


class VisitStatementMixin(VisitPersonMixin):
    def get_person(self):
        return self.fpr.person

    def pre_dispatch(self):
        self.statement = get_object_or_404(smodels.Statement, pk=self.kwargs["pk"])
        self.fpr = self.statement.fpr
        super(VisitStatementMixin, self).pre_dispatch()
        self.type = self.statement.type


class StatementMixin(object):
    def get_context_data(self, **kw):
        ctx = super(StatementMixin, self).get_context_data(**kw)
        ctx["type"] = self.type
        ctx["type_desc"] = STATEMENT_TYPES[self.type]
        ctx["fpr"] = self.fpr
        ctx["keyid"] = self.fpr.fpr[-16:]
        ctx["statement"] = self.statement
        ctx["explain_template"] = "statements/explain_" + self.type + ".html"
        ctx["blurb"] = [shlex_quote(x) for x in self.blurb] if self.blurb else None
        ctx["now"] = now()
        return ctx


class StatementForm(forms.Form):
    statement = forms.CharField(label="Signed statement", widget=forms.Textarea(attrs={"rows": 25, "cols": 80}))

    def __init__(self, *args, **kw):
        self.fpr = kw.pop("fpr")
        super(StatementForm, self).__init__(*args, **kw)

    def clean_statement(self):
        from keyring.models import Key
        text = self.cleaned_data["statement"]
        try:
            key = Key.objects.get_or_download(self.fpr.fpr)
        except RuntimeError as e:
            raise forms.ValidationError("Cannot download the key: " + str(e))

        try:
            plaintext = key.verify(text)
        except RuntimeError as e:
            raise forms.ValidationError("Cannot verify the signature: " + str(e))

        return (text, plaintext)


class EditStatementMixin(StatementMixin):
    def pre_dispatch(self):
        super(EditStatementMixin, self).pre_dispatch()
        self.blurb = AUTO_VERIFY_BLURBS.get(self.type, None)
        if self.blurb:
            self.blurb = ["For nm.debian.org, at {:%Y-%m-%d}:".format(now())] + self.blurb

    def get_initial(self):
        if self.statement is None:
            return super(EditStatementMixin, self).get_initial()
        else:
            return { "statement": self.statement.statement }

    def get_form_kwargs(self):
        kw = super(EditStatementMixin, self).get_form_kwargs()
        kw["fpr"] = self.fpr
        return kw

    def normalise_text(self, text):
        return re.sub("\s+", " ", text).lower().strip()

    @transaction.atomic
    def form_valid(self, form):
        statement = self.statement
        if statement is None:
            statement = smodels.Statement(fpr=self.fpr, type=self.type)

        statement.uploaded_by = self.visitor

        statement.statement, plaintext = form.cleaned_data["statement"]

        if self.blurb is not None:
            expected = self.normalise_text("\n".join(self.blurb))
            submitted = self.normalise_text(plaintext)
            if submitted == expected:
                statement.statement_verified = now()
            else:
                statement.statement_verified = None
        else:
            statement.statement_verified = None

        statement.save()
        return redirect(self.person.get_absolute_url())


class Create(EditStatementMixin, VisitPersonMixin, FormView):
    template_name = "statements/edit.html"
    form_class = StatementForm
    require_vperms = "edit_statements"

    def get_person(self):
        return self.fpr.person

    def pre_dispatch(self):
        self.fpr = get_object_or_404(bmodels.Fingerprint, fpr=self.kwargs["fpr"])
        self.type = self.kwargs["type"]
        if self.type not in STATEMENT_TYPES:
            raise PermissionDenied
        self.statement = None
        super(Create, self).pre_dispatch()


class Show(StatementMixin, VisitStatementMixin, TemplateView):
    template_name = "statements/show.html"
    require_vperms = "see_statements"


class Edit(EditStatementMixin, VisitStatementMixin, FormView):
    template_name = "statements/edit.html"
    form_class = StatementForm
    require_vperms = "edit_statements"
