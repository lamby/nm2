# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf.urls import url
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    # Signed agreements
    url(r'^show/(?P<pk>\d+)$', views.Show.as_view(), name="statement_show"),
    url(r'^edit/(?P<pk>\d+)$', views.Edit.as_view(), name="statement_edit"),
    url(r'^create/(?P<type>[^/]+)/(?P<fpr>[0-9A-F]+)$', views.Create.as_view(), name="statement_create"),
]

