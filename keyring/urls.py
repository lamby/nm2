# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf.urls import *
from . import views

urlpatterns = [
    url(r'^keycheck/(?P<fpr>[0-9A-Fa-f]{32,40})$', views.keycheck, name="keyring_keycheck"),
]
