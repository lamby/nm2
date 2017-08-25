from django.conf.urls import *
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^process/(?P<key>[^/]+)$', views.Process.as_view(), name="legacy_process"),
    url(r'^mail-archive/(?P<key>[^/]+)$', views.MailArchive.as_view(), name="legacy_download_mail_archive"),
    url(r'^display-mail-archive/(?P<key>[^/]+)$', views.DisplayMailArchive.as_view(), name="legacy_display_mail_archive"),
]
