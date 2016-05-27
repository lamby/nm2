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
    url(r'^create/(?P<key>[^/]+)$', views.Create.as_view(), name="process_create"),
    url(r'^(?P<pk>\d+)$', views.Show.as_view(), name="process_show"),
    url(r'^(?P<pk>\d+)/intent$', views.ReqIntent.as_view(), name="process_req_intent"),
    url(r'^(?P<pk>\d+)/sc_dmup$', views.ReqAgreements.as_view(), name="process_req_sc_dmup"),
    url(r'^(?P<pk>\d+)/advocate$', views.ReqIntent.as_view(), name="process_req_advocate"),
    url(r'^(?P<pk>\d+)/keycheck$', views.ReqIntent.as_view(), name="process_req_keycheck"),
    url(r'^(?P<pk>\d+)/am_ok$', views.ReqIntent.as_view(), name="process_req_am_ok"),
    url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/create$', views.StatementCreate.as_view(), name="process_statement_create"),
    url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/(?P<st>\d+)/edit$', views.StatementEdit.as_view(), name="process_statement_edit"),
]
