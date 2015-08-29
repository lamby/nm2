# coding: utf-8

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

def authenticate(request):
    """
    Get the user from the Api-Key: header set in the request

    Returns the User if one was found, else None
    """
    from . import models as amodels
    value = request.META.get("HTTP_API_KEY", None)
    if value is None: return None

    try:
        key = amodels.Key.objects.get(value=value)
    except amodels.Key.DoesNotExists:
        return None

    amodels.AuditLog.objects.create(
        key=key,
        key_enabled=key.enabled,
        remote_addr=request.META.get("REMOTE_ADDR", "(unknown)"),
        request_method=request.method,
        absolute_uri=request.build_absolute_uri(),
    )

    if not key.enabled:
        return None

    return key.user
