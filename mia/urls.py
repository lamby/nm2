from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^uploaders$', views.Uploaders.as_view(), name="mia_uploaders"),
    url(r'^voters$', views.Voters.as_view(), name="mia_voters"),
]

