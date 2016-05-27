# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf.urls import url
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^$', views.List.as_view, name="process_list"),
    url(r'^create/(?P<key>[^/]+)/(?P<applying_for>[^/]+)$', views.Create.as_view(), name="process_create"),
    url(r'^(?P<pk>\d+)$', views.Show.as_view(), name="process_show"),
]

