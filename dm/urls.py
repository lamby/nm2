# coding: utf-8




from django.conf.urls import url
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^$', RedirectView.as_view(url="/", permanent=True), name="dm_index"),
    url(r'^claim$', views.Claim.as_view(), name="dm_claim"),
    url(r'^claim/confirm/(?P<token>[^/]+)$', views.ClaimConfirm.as_view(), name="dm_claim_confirm"),
]

