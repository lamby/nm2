# coding: utf-8




from django.conf.urls import *
from . import views

urlpatterns = [
    url(r'^keycheck/(?P<fpr>[0-9A-Fa-f]{32,40})$', views.keycheck, name="keyring_keycheck"),
]
