# coding: utf-8




from django.conf.urls import *
from . import views

urlpatterns = [
    url(r'^$', views.KeyList.as_view(), name="apikeys_list"),
    url(r'^(?P<pk>\d+)/enable$', views.KeyEnable.as_view(), name="apikeys_enable"),
    url(r'^(?P<pk>\d+)/delete$', views.KeyDelete.as_view(), name="apikeys_delete"),
]
