# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf.urls import *
from backend.mixins import VisitorTemplateView
from . import views

urlpatterns = [
    url(r'^$', VisitorTemplateView.as_view(template_name="wizard/home.html"), name="wizard_home"),
    url(r'^advocate$', views.Advocate.as_view(), name="wizard_advocate"),
    url(r'^process/(?P<applying_for>[^/]+)$', views.NewProcess.as_view(), name="wizard_newprocess"),
]
