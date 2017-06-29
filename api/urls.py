# coding: utf-8




from django.conf.urls import *
from backend.mixins import VisitorTemplateView
from . import views

urlpatterns = [
    url(r'^$', VisitorTemplateView.as_view(template_name="api/doc.html"), name="api_doc"),
    url(r'^people$', views.People.as_view(), name="api_people"),
    url(r'^status$', views.Status.as_view(), name="api_status"),
    url(r'^whoami$', views.Whoami.as_view(), name="api_whoami"),
]
