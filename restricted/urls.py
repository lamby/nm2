from django.conf.urls import *
from django.views.generic import RedirectView
from . import views
from backend.mixins import VisitorTemplateView

urlpatterns = [
    # Impersonate a user
    url(r'^impersonate/(?P<key>[^/]+)?$', views.Impersonate.as_view(), name="impersonate"),
    # Export database
    url(r'^db-export$', views.DBExport.as_view(), name="restricted_db_export"),
    # Mailbox stats
    url(r'^mailbox-stats$', views.MailboxStats.as_view(), name="mailbox_stats"),

    # Compatibility
    url(r'^ammain$', RedirectView.as_view(url="/process/am-dashboard", permanent=True)),
    url(r'^amprofile(?:/(?P<key>[^/]+))?$', RedirectView.as_view(url="/person/%(key)s/amprofile", permanent=True)),
    url(r'^minechangelogs/(?P<key>[^/]+)?$', RedirectView.as_view(url="/minechangelogs/search/%(key)s", permanent=True)),
    url(r'^mail-archive/(?P<key>[^/]+)$', RedirectView.as_view(url="/legacy/mail-archive/%(key)s", permanent=True)),
    url(r'^display-mail-archive/(?P<key>[^/]+)$', RedirectView.as_view(url="/legacy/display-mail-archive/%(key)s", permanent=True)),
]
