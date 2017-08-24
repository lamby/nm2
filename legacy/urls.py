from django.conf.urls import *
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^process/(?P<key>[^/]+)$', views.Process.as_view(), name="legacy_process"),
]
