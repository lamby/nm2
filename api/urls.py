# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf.urls import *
from backend.mixins import VisitorTemplateView
from . import views

urlpatterns = [
    url(r'^$', VisitorTemplateView.as_view(template_name="api/doc.html"), name="api_doc"),
    url(r'^people$', views.People.as_view(), name="api_people"),
    url(r'^status$', views.Status.as_view(), name="api_status"),
]
