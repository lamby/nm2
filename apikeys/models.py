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
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Key(models.Model):
    """
    An API access token and its associated user
    """
    user = models.ForeignKey(User)
    name = models.CharField(max_length=16)
    value = models.CharField(max_length=16, unique=True)
    enabled = models.BooleanField(default=True)

class AuditLog(models.Model):
    """
    Audit log for token usage
    """
    key = models.ForeignKey(Key)
    ts = models.DateTimeField(auto_now_add=True)
    key_enabled = models.BooleanField()
    remote_addr = models.CharField(max_length=255)
    request_method = models.CharField(max_length=8)
    absolute_uri = models.TextField()
