# coding: utf8
# nm.debian.org website restricted pages
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
from django.conf.urls import *
from . import views
from backend.mixins import VisitorTemplateView

urlpatterns = patterns('restricted.views',
    url(r'^$', VisitorTemplateView.as_view(template_name='restricted/index.html'), name="restricted_index"),
    # AM Personal page
    url(r'^ammain$', views.AMMain.as_view(), name="restricted_ammain"),
    # AM preferences editor
    url(r'^amprofile(?:/(?P<key>[^/]+))?$', views.AMProfile.as_view(), name="restricted_amprofile"),
    # Edit personal info
    url(r'^person/(?P<key>[^/]+)$', views.Person.as_view(), name="restricted_person"),
    # Create new process for a person (advocate)
    url(r'^advocate/(?P<applying_for>[^/]+)/(?P<key>[^/]+)$', views.NewProcess.as_view(), name="restricted_advocate"),
    # Show changelogs (minechangelogs)
    url(r'^minechangelogs/(?P<key>[^/]+)?$', 'minechangelogs', name="restricted_minechangelogs"),
    # Impersonate a user
    url(r'^impersonate/(?P<key>[^/]+)?$', views.Impersonate.as_view(), name="impersonate"),
    # Export database
    url(r'^db-export$', views.DBExport.as_view(), name="restricted_db_export"),
    # Download mail archive
    url(r'^mail-archive/(?P<key>[^/]+)$', views.MailArchive.as_view(), name="download_mail_archive"),
    # Display mail archive
    url(r'^display-mail-archive/(?P<key>[^/]+)$', views.DisplayMailArchive.as_view(), name="display_mail_archive"),
    # Assign AMs to NMs
    url(r'^assign-am/(?P<key>[^/]+)$', views.AssignAM.as_view(), name="assign_am"),
)
