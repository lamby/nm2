# coding: utf8
# nm.debian.org view mixins
#
# Copyright (C) 2014  Enrico Zini <enrico@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.views.generic import TemplateView
from django.core.exceptions import PermissionDenied
from . import models as bmodels

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

        if not self.request.user.is_authenticated():
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

    def pre_dispatch(self):
        self.set_visitor_info()

        if self.require_visitor and (self.visitor is None or self.require_visitor not in self.visitor.perms):
            raise PermissionDenied

    def dispatch(self, request, *args, **kwargs):
        self.pre_dispatch()
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
    Visit a person record. Adds self.person and self.vperms with the
    permissions the visitor has over the person
    """
    # Define to "edit_bio" "edit_ldap" or "view_person_audit_log" to raise
    # PermissionDenied if the given test on the person-visitor fails
    require_vperms = None

    def get_person(self):
        key = self.kwargs.get("key", None)
        if key is None:
            return self.visitor
        else:
            return bmodels.Person.lookup_or_404(key)

    def pre_dispatch(self):
        super(VisitPersonMixin, self).pre_dispatch()
        self.person = self.get_person()
        self.vperms = self.person.permissions_of(self.visitor)

        if self.require_vperms and self.require_vperms not in self.vperms.perms:
            raise PermissionDenied

    def get_context_data(self, **kw):
        ctx = super(VisitPersonMixin, self).get_context_data(**kw)
        ctx["person"] = self.person
        ctx["vperms"] = self.vperms
        return ctx


class VisitPersonTemplateView(VisitPersonMixin, TemplateView):
    pass


class VisitProcessMixin(VisitorMixin):
    """
    Visit a person process. Adds self.person, self.process and self.vperms with
    the permissions the visitor has over the person
    """
    # Define to "edit_bio" "edit_ldap" or "view_person_audit_log" to raise
    # PermissionDenied if the given test on the person-visitor fails
    require_vperms = None

    def pre_dispatch(self):
        super(VisitProcessMixin, self).pre_dispatch()
        key = self.kwargs.get("key", None)
        if key is None:
            raise PermissionDenied
        self.process = bmodels.Process.lookup_or_404(key)
        self.person = self.process.person
        self.vperms = self.process.permissions_of(self.visitor)

        if self.require_vperms and self.require_vperms not in self.vperms.perms:
            raise PermissionDenied

    def get_context_data(self, **kw):
        ctx = super(VisitProcessMixin, self).get_context_data(**kw)
        ctx["person"] = self.person
        ctx["process"] = self.process
        ctx["vperms"] = self.vperms
        return ctx


class VisitProcessTemplateView(VisitProcessMixin, TemplateView):
    pass

