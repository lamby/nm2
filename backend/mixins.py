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
from . import models as bmodels

class VisitorMixin(object):
    """
    Add a 'visitor' entry to the context with the Person object for the person
    visiting the site
    """
    def get_visitor(self, request):
        if not request.user.is_authenticated():
            return None

        visitor = request.user.get_profile()

        # Implement impersonation if requested in session
        if visitor.is_admin:
            key = request.session.get("impersonate", None)
            if key is not None:
                p = bmodels.Person.lookup(key)
                if p is not None:
                    visitor = p
        return visitor

    def get_context_data(self, **kw):
        ctx = super(VisitorMixin, self).get_context_data(**kw)
        ctx["visitor"] = self.get_visitor(self.request)
        return ctx

class VisitorTemplateView(VisitorMixin, TemplateView):
    pass

