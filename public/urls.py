# coding: utf-8
# nm.debian.org website reports
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
from django.views.generic import RedirectView
from . import views

urlpatterns = patterns('public.views',
    url(r'^$', RedirectView.as_view(url="/"), name="public_index"),
    url(r'^newnm$', views.Newnm.as_view(), name="public_newnm"),
    url(r'^newnm/resend_challenge/(?P<key>[^/]+)$', 'newnm_resend_challenge', name="public_newnm_resend_challenge"),
    url(r'^newnm/confirm/(?P<nonce>[^/]+)$', 'newnm_confirm', name="public_newnm_confirm"),
    url(r'^processes$', views.Processes.as_view(), name="processes"),
    url(r'^managers$', views.Managers.as_view(), name="managers"),
    url(r'^people(?:/(?P<status>\w+))?$', views.People.as_view(), name="people"),
    url(r'^person/(?P<key>[^/]+)$', views.Person.as_view(), name="person"),
    url(r'^process/(?P<key>[^/]+)$', views.Process.as_view(), name="public_process"),
    url(r'^progress/(?P<progress>\w+)$', views.Progress.as_view(), name="public_progress"),
    url(r'^stats/$', views.Stats.as_view(), name="public_stats"),
    url(r'^stats/latest$', views.StatsLatest.as_view(), name="public_stats_latest"),
    url(r'^stats/graph$', views.StatsGraph.as_view(), name="public_stats_graph"),
    url(r'^findperson/$', views.Findperson.as_view(), name="public_findperson"),

    # Compatibility
    url(r'^whoisam$', views.Managers.as_view(), name="public_whoisam"),
    url(r'^nmstatus/(?P<key>[^/]+)$', views.Process.as_view(), name="public_nmstatus"),
    url(r'^nmlist$', views.Processes.as_view(), name="public_nmlist"),
)
