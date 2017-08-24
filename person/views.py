from django import http, forms
from django.views.generic import TemplateView, View
from django.views.generic.edit import UpdateView, FormView
from django.core.exceptions import PermissionDenied
from backend.mixins import VisitorMixin, VisitPersonMixin
import backend.models as bmodels
from backend import const
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
        processes2 = pmodels.Process.objects.filter(person=self.person).order_by("-closed_time")

        adv_processes2 = []
        for req in pmodels.Requirement.objects.filter(type="advocate", statements__uploaded_by=self.person).distinct().select_related("process"):
            adv_processes2.append(req.process)

        try:
            am = bmodels.AM.objects.get(person=self.person)
        except bmodels.AM.DoesNotExist:
            am = None

        if am is not None:
            am_processes = am.processed \
                    .annotate(started=Min("log__logdate"), ended=Max("log__logdate")) \
                    .order_by("is_active", "ended")

            am_processes2 = pmodels.Process.objects.filter(ams__am=am).distinct()
        else:
            am_processes = []
            am_processes2 = []

        audit_log = []
        if "view_person_audit_log" in self.visit_perms:
            is_admin = self.visitor.is_admin
            for e in self.person.audit_log.order_by("-logdate"):
                if is_admin:
                    changes = sorted((k, v[0], v[1]) for k, v in list(json.loads(e.changes).items()))
                else:
                    changes = sorted((k, v[0], v[1]) for k, v in list(json.loads(e.changes).items()) if k not in ("fd_comment", "pending"))
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


class AMProfile(VisitPersonMixin, FormView):
    # Require DD instead of AM to give access to inactive AMs
    require_visitor = "dd"
    template_name = "person/amprofile.html"

    def load_objects(self):
        super(AMProfile, self).load_objects()
        try:
            self.am = bmodels.AM.objects.get(person=self.person)
        except bmodels.AM.DoesNotExist:
            self.am = None

        try:
            self.visitor_am = bmodels.AM.objects.get(person=self.visitor)
        except bmodels.AM.DoesNotExist:
            self.visitor_am = None

    def check_permissions(self):
        super(AMProfile, self).check_permissions()
        if self.am is None: raise PermissionDenied
        if self.visitor_am is None: raise PermissionDenied
        if self.person.pk != self.visitor.pk and not self.visitor.is_admin:
            raise PermissionDenied

    def get_form_class(self):
        includes = ["slots", "is_am"]

        if self.visitor_am.is_fd:
            includes.append("is_fd")
        if self.visitor_am.is_dam:
            includes.append("is_dam")
        if self.visitor_am.is_admin:
            includes.append("fd_comment")

        class AMForm(forms.ModelForm):
            class Meta:
                model = bmodels.AM
                fields = includes
        return AMForm

    def get_form_kwargs(self):
        res = super(AMProfile, self).get_form_kwargs()
        res["instance"] = self.am
        return res

    def get_context_data(self, **kw):
        from django.db.models import Min
        ctx = super(AMProfile, self).get_context_data(**kw)
        ctx["am"] = self.am
        ctx["processes"] = bmodels.Process.objects.filter(manager=self.am).annotate(started=Min("log__logdate")).order_by("-started")
        return ctx

    def form_valid(self, form):
        form.save()
        return self.render_to_response(self.get_context_data(form=form))
