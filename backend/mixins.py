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

    def pre_dispatch(self):
        self.impersonator = None

        if not self.request.user.is_authenticated():
            self.visitor = None
        else:
            self.visitor = self.request.user.get_profile()

            # Implement impersonation if requested in session
            if self.visitor.is_admin:
                key = self.request.session.get("impersonate", None)
                if key is not None:
                    p = bmodels.Person.lookup(key)
                    if p is not None:
                        self.impersonator = self.visitor
                        self.visitor = p

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
    def pre_dispatch(self):
        super(VisitPersonMixin, self).pre_dispatch()
        key = self.kwargs.get("key", None)
        if key is None:
            self.person = self.visitor
        else:
            self.person = bmodels.Person.lookup_or_404(key)
        self.vperms = self.person.permissions_of(self.visitor)

    def get_context_data(self, **kw):
        ctx = super(VisitPersonMixin, self).get_context_data(**kw)
        ctx["person"] = self.person
        ctx["vperms"] = self.vperms
        return ctx

class VisitPersonTemplateView(VisitPersonMixin, TemplateView):
    pass
