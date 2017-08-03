# coding: utf-8




from django.conf.urls import url
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^$', RedirectView.as_view(url="/", permanent=True), name="dm_index"),
    # Manage fingerprints
    url(r'^person/(?P<key>[^/]+)$', views.PersonFingerprints.as_view(), name="fprs_person_list"),
    # Activate fingerprints
    url(r'^person/(?P<key>[^/]+)/(?P<fpr>[0-9A-F]+)/activate$', views.SetActiveFingerprint.as_view(), name="fprs_person_activate"),
]
