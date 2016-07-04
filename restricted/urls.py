# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf.urls import *
from . import views
from backend.mixins import VisitorTemplateView

urlpatterns = [
    url(r'^$', VisitorTemplateView.as_view(template_name='restricted/index.html'), name="restricted_index"),
    # AM Personal page
    url(r'^ammain$', views.AMMain.as_view(), name="restricted_ammain"),
    # AM preferences editor
    url(r'^amprofile(?:/(?P<key>[^/]+))?$', views.AMProfile.as_view(), name="restricted_amprofile"),
    # Show changelogs (minechangelogs)
    url(r'^minechangelogs/(?P<key>[^/]+)?$', views.minechangelogs, name="restricted_minechangelogs"),
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
    # Mailbox stats
    url(r'^mailbox-stats$', views.MailboxStats.as_view(), name="mailbox_stats"),
]
