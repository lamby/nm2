# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf.urls import patterns, include, url
from django.views.generic import TemplateView
from django_dacs import views as django_dacs_views
from backend.mixins import VisitorTemplateView

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

urlpatterns = [
    url(r'^robots.txt$', TemplateView.as_view(template_name='robots.txt', content_type="text/plain"), name="root_robots_txt"),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^$', VisitorTemplateView.as_view(template_name='index.html'), name="home"),
    url(r'^license/$', VisitorTemplateView.as_view(template_name='license.html'), name="root_license"),
    url(r'^faq/$', VisitorTemplateView.as_view(template_name='faq.html'), name="root_faq"),
    # DACS login
    url(r'^public/', include("public.urls")),
    url(r'^am/', include("restricted.urls")),
    url(r'^fprs/', include("fprs.urls")),
    url(r'^statements/', include("statements.urls")),
    url(r'^process/', include("process.urls")),
    url(r'^dm/', include("dm.urls")),
    url(r'^api/', include("api.urls")),
    url(r'^apikeys/', include("apikeys.urls")),
    url(r'^keyring/', include("keyring.urls")),

    # Uncomment the admin/doc line below to enable admin documentation:
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),

    url(r'^logout/', django_dacs_views.logout),
]
