from django.conf.urls import *
from django.views.generic import RedirectView
from . import views
from backend.mixins import VisitorTemplateView

urlpatterns = [
    url(r'^$', VisitorTemplateView.as_view(template_name='restricted/index.html'), name="restricted_index"),
    # Show changelogs (minechangelogs)
    url(r'^minechangelogs/(?P<key>[^/]+)?$', views.MineChangelogs.as_view(), name="restricted_minechangelogs"),
    # Impersonate a user
    url(r'^impersonate/(?P<key>[^/]+)?$', views.Impersonate.as_view(), name="impersonate"),
    # Export database
    url(r'^db-export$', views.DBExport.as_view(), name="restricted_db_export"),
    # Download mail archive
    url(r'^mail-archive/(?P<key>[^/]+)$', views.MailArchive.as_view(), name="download_mail_archive"),
    # Display mail archive
    url(r'^display-mail-archive/(?P<key>[^/]+)$', views.DisplayMailArchive.as_view(), name="display_mail_archive"),
    # Mailbox stats
    url(r'^mailbox-stats$', views.MailboxStats.as_view(), name="mailbox_stats"),

    # Compatibility
    url(r'^ammain$', RedirectView.as_view(url="/process/am-dashboard", permanent=True)),
    url(r'^amprofile(?:/(?P<key>[^/]+))?$', RedirectView.as_view(url="/person/%(key)s/amprofile", permanent=True)),
]
