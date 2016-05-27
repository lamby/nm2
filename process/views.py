# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.translation import ugettext as _
from django.shortcuts import redirect, get_object_or_404
from django.views.generic import TemplateView, View
from django.views.generic.edit import FormView
from django.utils.timezone import now
from django.db import transaction
from django import forms
from backend.mixins import VisitorMixin, VisitPersonMixin
from backend import const
import backend.models as bmodels
from .mixins import VisitProcessMixin
import datetime
import re
from six.moves import shlex_quote
from . import models as pmodels
from .forms import StatementForm


class List(VisitorMixin, TemplateView):
    """
    List active and recently closed processes
    """
    template_name = "process/list.html"

    def get_context_data(self, **kw):
        ctx = super(List, self).get_context_data(**kw)
        ctx["current"] = pmodels.Process.objects.filter(closed__isnull=True).order_by("applying_for")
        cutoff = now() - datetime.timedelta(days=30)
        ctx["last"] = pmodels.Process.objects.filter(closed__gte=cutoff).order_by("-closed")
        return ctx


class Create(VisitPersonMixin, FormView):
    """
    Create a new process
    """
    require_vperms = "request_new_status"
    template_name = "process/create.html"

    def get_context_data(self, **kw):
        ctx = super(Create, self).get_context_data(**kw)
        current = []
        current.extend(bmodels.Process.objects.filter(person=self.person, is_active=True))
        current.extend(pmodels.Process.objects.filter(person=self.person, closed__isnull=True))
        ctx["current"] = current
        return ctx

    def get_form_class(self):
        whitelist = self.person.possible_new_statuses
        choices = [(x.tag, x.sdesc) for x in const.ALL_STATUS if x.tag in whitelist]
        if not choices: raise PermissionDenied
        class Form(forms.Form):
            applying_for = forms.ChoiceField(label=_("Apply for status"), choices=choices, required=True)
        return Form

    def form_valid(self, form):
        applying_for = form.cleaned_data["applying_for"]
        # TODO: ensure visitor can create processes for person
        # TODO: ensure that applying_for is a valid new process for person
        with transaction.atomic():
            p = pmodels.Process.objects.create(self.person, applying_for)
            p.add_log(self.visitor, "Process create", is_public=True)
        return redirect(p.get_absolute_url())


class Show(VisitProcessMixin, TemplateView):
    """
    Show a process
    """
    template_name = "process/show.html"


class RequirementMixin(VisitProcessMixin):
    # Requirement type
    type = None

    def get_requirement_type(self):
        return self.type

    def get_requirement(self):
        return get_object_or_404(pmodels.Requirement, process=self.process, type=self.get_requirement_type())

    def pre_dispatch(self):
        super(RequirementMixin, self).pre_dispatch()
        self.requirement = self.get_requirement()

    def get_context_data(self, **kw):
        ctx = super(RequirementMixin, self).get_context_data(**kw)
        ctx["requirement"] = self.requirement
        ctx["type"] = self.requirement.type
        ctx["type_desc"] = pmodels.REQUIREMENT_TYPES_DICT[self.requirement.type]
        ctx["explain_template"] = "process/explain_statement_" + self.requirement.type + ".html"
        return ctx


class ReqIntent(RequirementMixin, TemplateView):
    type = "intent"
    template_name = "process/req_intent.html"

    # TODO: show existing status
    # TODO: link to add/edit statements
    #  - add shown if none exists, or if more can be added (advocacies)
    #  - edit is shown for existing ones
    #  - delete also offered as possibility

class ReqAgreements(RequirementMixin, TemplateView):
    type = "sc_dmup"
    template_name = "process/req_sc_dmup.html"

    # TODO: show existing status
    # TODO: link to add/edit statements
    #  - add shown if none exists, or if more can be added (advocacies)
    #  - edit is shown for existing ones
    #  - delete also offered as possibility



class EditStatementMixin(RequirementMixin):
    form_class = StatementForm
    require_vperms = "edit_statements"

    def get_requirement_type(self):
        return self.kwargs["type"]

    def get_blurb(self):
        """
        Get the blurb used for auto-verification, or None if none is available
        """
        if self.requirement.type == "sc_dmup":
            return [
                "I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.",
                "I have read the Debian Machine Usage Policy and I accept them."
            ]
        #elif self.requirement.type == "intent":
        #    return [
        #        "I would like to apply to change my status in Debian to {}".format(const.ALL_STATUS_DESCS[self.process.applying_for]),
        #    ]
        return None

    def pre_dispatch(self):
        super(EditStatementMixin, self).pre_dispatch()
        self.blurb = self.get_blurb()
        if self.blurb:
            self.blurb = ["For nm.debian.org, at {:%Y-%m-%d}:".format(now())] + self.blurb
        if "st" in self.kwargs:
            self.statement = get_object_or_404(pmodels.Statement, pk=self.kwargs["st"])
            if self.statement.requirement != self.requirement:
                raise PermissionDenied
        else:
            self.statement = None

    def get_initial(self):
        if self.statement is None:
            return super(EditStatementMixin, self).get_initial()
        else:
            return { "statement": self.statement.statement }

    def get_form_kwargs(self):
        kw = super(EditStatementMixin, self).get_form_kwargs()
        kw["fpr"] = self.visitor.fpr
        return kw

    def get_context_data(self, **kw):
        ctx = super(EditStatementMixin, self).get_context_data(**kw)
        ctx["fpr"] = self.visitor.fpr
        ctx["keyid"] = self.visitor.fpr[-16:]
        ctx["statement"] = self.statement
        ctx["blurb"] = [shlex_quote(x) for x in self.blurb] if self.blurb else None
        ctx["now"] = now()
        return ctx

    def normalise_text(self, text):
        return re.sub("\s+", " ", text).lower().strip()

    @transaction.atomic
    def form_valid(self, form):
        statement = self.statement
        if statement is None:
            statement = pmodels.Statement(requirement=self.requirement, fpr=self.visitor.fingerprint)
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
        return redirect(self.requirement.get_absolute_url())


class StatementCreate(EditStatementMixin, FormView):
    template_name = "process/statement_edit.html"


class StatementEdit(EditStatementMixin, FormView):
    template_name = "process/statement_edit.html"


## coding: utf8
#from __future__ import print_function
#from __future__ import absolute_import
#from __future__ import division
#from __future__ import unicode_literals
#from django.views.generic import TemplateView, View
#from django.views.generic.edit import FormView
#from django.utils.timezone import now
#from django.core.urlresolvers import reverse
#from django.shortcuts import redirect, get_object_or_404
#from django import forms
#from django.core.exceptions import PermissionDenied
#from backend.mixins import VisitPersonMixin
#from django.db import transaction
#import backend.models as bmodels
#from six.moves import shlex_quote
#from . import models as smodels
#import re
#
#STATEMENT_TYPES = dict(smodels.STATEMENT_TYPES)
#
#
#class VisitStatementMixin(VisitPersonMixin):
#    def get_person(self):
#        return self.fpr.person
#
#    def pre_dispatch(self):
#        self.statement = get_object_or_404(smodels.Statement, pk=self.kwargs["pk"])
#        self.fpr = self.statement.fpr
#        super(VisitStatementMixin, self).pre_dispatch()
#        self.type = self.statement.type
#
#
#class StatementMixin(object):
#    def get_context_data(self, **kw):
#        ctx = super(StatementMixin, self).get_context_data(**kw)
#        ctx["type"] = self.type
#        ctx["type_desc"] = STATEMENT_TYPES[self.type]
#        ctx["fpr"] = self.fpr
#        ctx["keyid"] = self.fpr.fpr[-16:]
#        ctx["statement"] = self.statement
#        ctx["explain_template"] = "statements/explain_" + self.type + ".html"
#        ctx["blurb"] = [shlex_quote(x) for x in self.blurb] if self.blurb else None
#        ctx["now"] = now()
#        return ctx
#
#
#class StatementForm(forms.Form):
#    statement = forms.CharField(label="Signed statement", widget=forms.Textarea(attrs={"rows": 25, "cols": 80}))
#
#    def __init__(self, *args, **kw):
#        self.fpr = kw.pop("fpr")
#        super(StatementForm, self).__init__(*args, **kw)
#
#    def clean_statement(self):
#        from keyring.models import Key
#        text = self.cleaned_data["statement"]
#        try:
#            key = Key.objects.get_or_download(self.fpr.fpr)
#        except RuntimeError as e:
#            raise forms.ValidationError("Cannot download the key: " + str(e))
#
#        try:
#            plaintext = key.verify(text)
#        except RuntimeError as e:
#            raise forms.ValidationError("Cannot verify the signature: " + str(e))
#
#        return (text, plaintext)
#
#
#class EditStatementMixin(StatementMixin):
#    def pre_dispatch(self):
#        super(EditStatementMixin, self).pre_dispatch()
#        self.blurb = AUTO_VERIFY_BLURBS.get(self.type, None)
#        if self.blurb:
#            self.blurb = ["For nm.debian.org, at {:%Y-%m-%d}:".format(now())] + self.blurb
#
#    def get_initial(self):
#        if self.statement is None:
#            return super(EditStatementMixin, self).get_initial()
#        else:
#            return { "statement": self.statement.statement }
#
#    def get_form_kwargs(self):
#        kw = super(EditStatementMixin, self).get_form_kwargs()
#        kw["fpr"] = self.fpr
#        return kw
#
#    def normalise_text(self, text):
#        return re.sub("\s+", " ", text).lower().strip()
#
#    @transaction.atomic
#    def form_valid(self, form):
#        statement = self.statement
#        if statement is None:
#            statement = smodels.Statement(fpr=self.fpr, type=self.type)
#
#        statement.uploaded_by = self.visitor
#
#        statement.statement, plaintext = form.cleaned_data["statement"]
#
#        if self.blurb is not None:
#            expected = self.normalise_text("\n".join(self.blurb))
#            submitted = self.normalise_text(plaintext)
#            if submitted == expected:
#                statement.statement_verified = now()
#            else:
#                statement.statement_verified = None
#        else:
#            statement.statement_verified = None
#
#        statement.save()
#        return redirect(self.person.get_absolute_url())
#
#
#class Show(StatementMixin, VisitStatementMixin, TemplateView):
#    template_name = "statements/show.html"
#    require_vperms = "see_statements"
#
#
#class Edit(EditStatementMixin, VisitStatementMixin, FormView):
#    template_name = "statements/edit.html"
#    form_class = StatementForm
#    require_vperms = "edit_statements"
