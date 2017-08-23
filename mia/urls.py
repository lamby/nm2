from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^uploaders$', views.Uploaders.as_view(), name="mia_uploaders"),
    url(r'^voters$', views.Voters.as_view(), name="mia_voters"),
    url(r'^wat/ping/(?P<key>[^/]+)?$', views.MIAPing.as_view(), name="mia_wat_ping"),
    url(r'^wat/remove/(?P<pk>\d+)$', views.MIARemove.as_view(), name="mia_wat_remove"),
]
