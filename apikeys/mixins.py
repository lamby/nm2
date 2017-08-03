# coding: utf-8
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





from backend.mixins import VisitorMixin
from . import authenticate

class APIVisitorMixin(VisitorMixin):
    """
    Allow to use api keys to set visitor information
    """
    def set_visitor_info(self):
        # Try the default from VisitorMixin
        super(APIVisitorMixin, self).set_visitor_info()

        # If it failed, try again with API key
        if self.visitor is None:
            self.visitor = authenticate(self.request)
