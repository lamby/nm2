from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied
from django.core import signing
from . import models as bmodels

class OverrideView(Exception):
    """
    Allow to override the current view using a different view function in
    load_objects, check_permissions and pre_dispatch.

    This can be used to show nice error messages when special cases are
    detected.
    """
    def __init__(self, method):
        self.method = method


class VisitorMixin(object):
    """
    Add self.visitor and self.impersonator to the View for the person visiting
    the site
    """
    # Define to "dd" "am" or "admin" to raise PermissionDenied if the
    # given test on the visitor fails
    require_visitor = None

    def set_visitor_info(self):
        self.impersonator = None

        if not self.request.user.is_authenticated:
            self.visitor = None
        else:
            self.visitor = self.request.user

            # Implement impersonation if requested in session
            if self.visitor.is_admin:
                key = self.request.session.get("impersonate", None)
                if key is not None:
                    p = bmodels.Person.lookup(key)
                    if p is not None:
                        self.impersonator = self.visitor
                        self.visitor = p

    def load_objects(self):
        """
        Hook to set self.* members from request parameters, so that they are
        available to the rest of the view members.
        """
        self.set_visitor_info()

    def check_permissions(self):
        """
        Raise PermissionDenied if some of the permissions requested by the view
        configuration are not met.

        Subclasses can extend this to check their own permissions.
        """
        if self.require_visitor and (self.visitor is None or self.require_visitor not in self.visitor.perms):
            raise PermissionDenied

    def pre_dispatch(self):
        pass

    def dispatch(self, request, *args, **kwargs):
        try:
            self.load_objects()
            self.check_permissions()
            self.pre_dispatch()
        except OverrideView as e:
            return e.method(request, *args, **kw)

        return super(VisitorMixin, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kw):
        ctx = super(VisitorMixin, self).get_context_data(**kw)
        ctx["visitor"] = self.visitor
        ctx["impersonator"] = self.impersonator
        return ctx


class VisitorTemplateView(VisitorMixin, TemplateView):
    pass


class VisitPersonMixin(VisitorMixin):
    """
    Visit a person record. Adds self.person and self.visit_perms with the
    permissions the visitor has over the person
    """
    # Define to "edit_bio" "edit_ldap" or "view_person_audit_log" to raise
    # PermissionDenied if the given test on the person-visitor fails
    require_visit_perms = None

    def get_person(self):
        key = self.kwargs.get("key", None)
        if key is None:
            if self.visitor is None: raise PermissionDenied
            return self.visitor
        else:
            return bmodels.Person.lookup_or_404(key)

    def get_visit_perms(self):
        return self.person.permissions_of(self.visitor)

    def load_objects(self):
        super(VisitPersonMixin, self).load_objects()
        self.person = self.get_person()
        self.visit_perms = self.get_visit_perms()

    def check_permissions(self):
        super(VisitPersonMixin, self).check_permissions()
        if self.require_visit_perms and self.require_visit_perms not in self.visit_perms:
            raise PermissionDenied

    def get_context_data(self, **kw):
        ctx = super(VisitPersonMixin, self).get_context_data(**kw)
        ctx["person"] = self.person
        ctx["visit_perms"] = self.visit_perms
        return ctx


class VisitPersonTemplateView(VisitPersonMixin, TemplateView):
    pass


class VisitProcessMixin(VisitPersonMixin):
    """
    Visit a person process. Adds self.person, self.process and self.visit_perms with
    the permissions the visitor has over the person
    """
    def get_person(self):
        return self.process.person

    def get_process(self):
        return bmodels.Process.lookup_or_404(self.kwargs["key"])

    def get_visit_perms(self):
        return self.process.permissions_of(self.visitor)

    def load_objects(self):
        self.process = self.get_process()
        super(VisitProcessMixin, self).load_objects()

    def get_context_data(self, **kw):
        ctx = super(VisitProcessMixin, self).get_context_data(**kw)
        ctx["process"] = self.process
        return ctx


class VisitProcessTemplateView(VisitProcessMixin, TemplateView):
    template_name = "process/show.html"


class TokenAuthMixin:
    # Domain used for this token
    token_domain = None
    # Max age in seconds
    token_max_age = 15 * 3600 * 24

    @classmethod
    def make_token(cls, uid, **kw):
        from django.utils.http import urlencode
        kw.update(u=uid, d=cls.token_domain)
        return urlencode({"t": signing.dumps(kw)})

    def verify_token(self, decoded):
        # Extend to verify extra components of the token
        pass

    def load_objects(self):
        token = self.request.GET.get("t")
        if token is not None:
            try:
                decoded = signing.loads(token, max_age=self.token_max_age)
            except signing.BadSignature:
                raise PermissionDenied
            uid = decoded.get("u")
            if uid is None:
                raise PermissionDenied
            if decoded.get("d") != self.token_domain:
                raise PermissionDenied
            self.verify_token(decoded)
            try:
                u = bmodels.Person.objects.get(uid=uid)
            except bmodels.Person.DoesNotExist:
                u = None
            if u is not None:
                self.request.user = u
        super().load_objects()
