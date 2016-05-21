# coding: utf-8
# nm.debian.org website authentication
#
# Copyright (C) 2012--2014  Enrico Zini <enrico@debian.org>
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
from django import http
from django.shortcuts import redirect
import backend.models as bmodels
from django_dacs.auth import DACSUserBackend

class NMUserBackend(DACSUserBackend):
    """
    RemoteUserBackend customised to create User objects from Person
    """

    # Copied from RemoteUserBackend and tweaked to validate against Person
    def authenticate(self, remote_user):
        """
        The username passed as ``remote_user`` is considered trusted.  This
        method simply returns the ``User`` object with the given username,
        creating a new ``User`` object if ``create_unknown_user`` is ``True``.

        Returns None if ``create_unknown_user`` is ``False`` and a ``User``
        object with the given username is not found in the database.
        """
        if not remote_user:
            return
        username = self.clean_username(remote_user)

        # Get the Person for this username: Person is authoritative over User
        # Allow user@alioth without -guest, for cases like retired DDs who are
        # DMs (Edward Betts <edward> is an example)
        if username.endswith("@debian.org") or username.endswith("@users.alioth.debian.org"):
            try:
                return bmodels.Person.objects.get(username=username)
            except bmodels.Person.DoesNotExist:
                return None
        else:
            return None
