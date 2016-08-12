# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import backend.models as bmodels
from backend import const
from django.views.generic import TemplateView, View
from django.views.generic.edit import UpdateView
from backend.mixins import VisitorMixin, VisitPersonMixin
import markdown
import json


class Person(VisitPersonMixin, TemplateView):
    template_name = "person/person.html"

    def get_context_data(self, **kw):
        from django.db.models import Min, Max
        ctx = super(Person, self).get_context_data(**kw)

        processes = self.person.processes \
                .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                .order_by("is_active", "ended")

        import process.models as pmodels
        processes2 = pmodels.Process.objects.filter(person=self.person).order_by("-closed")

        adv_processes2 = []
        for req in pmodels.Requirement.objects.filter(type="advocate", statements__uploaded_by=self.person).distinct().select_related("process"):
            adv_processes2.append(req.process)

        if self.person.is_am:
            am = self.person.am
            am_processes = am.processed \
                    .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                    .order_by("is_active", "ended")

            am_processes2 = pmodels.Process.objects.filter(ams__am=am).distinct()
        else:
            am = None
            am_processes = []
            am_processes2 = []

        audit_log = []
        if "view_person_audit_log" in self.visit_perms:
            is_admin = self.visitor.is_admin
            for e in self.person.audit_log.order_by("-logdate"):
                if is_admin:
                    changes = sorted((k, v[0], v[1]) for k, v in json.loads(e.changes).items())
                else:
                    changes = sorted((k, v[0], v[1]) for k, v in json.loads(e.changes).items() if k not in ("fd_comment", "pending"))
                audit_log.append({
                    "logdate": e.logdate,
                    "author": e.author,
                    "notes": e.notes,
                    "changes": changes,
                })

        ctx.update(
            am=am,
            processes=processes,
            processes2=processes2,
            am_processes=am_processes,
            am_processes2=am_processes2,
            adv_processes=self.person.advocated \
                    .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                    .order_by("is_active", "ended"),
            adv_processes2=adv_processes2,
            audit_log=audit_log,
        )

        if self.person.bio:
            ctx["bio_html"] = markdown.markdown(self.person.bio, safe_mode="escape")
        else:
            ctx["bio_html"] = ""
        return ctx


class EditLDAP(VisitPersonMixin, UpdateView):
    """
    Edit a person's information
    """
    require_visit_perms = "edit_ldap"
    model = bmodels.Person
    fields = ("cn", "mn", "sn", "email_ldap", "uid")
    template_name = "person/edit_ldap.html"

    def get_object(self):
        return self.person

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save(commit=False)
        self.object.save(audit_author=self.visitor, audit_notes="edited LDAP information")
        return super(EditLDAP, self).form_valid(form)


class EditBio(VisitPersonMixin, UpdateView):
    """
    Edit a person's information
    """
    require_visit_perms = "edit_bio"
    model = bmodels.Person
    fields = ("bio",)
    template_name = "person/edit_bio.html"

    def get_object(self):
        return self.person

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save(commit=False)
        self.object.save(audit_author=self.visitor, audit_notes="edited bio information")
        return super(EditBio, self).form_valid(form)


class EditEmail(VisitPersonMixin, UpdateView):
    """
    Edit a person's information
    """
    require_visit_perms = "edit_email"
    model = bmodels.Person
    fields = ("email",)
    template_name = "person/edit_email.html"

    def get_object(self):
        return self.person

    def form_valid(self, form):
        """
        If the form is valid, save the associated model.
        """
        self.object = form.save(commit=False)
        self.object.save(audit_author=self.visitor, audit_notes="edited email")
        return super(EditEmail, self).form_valid(form)
