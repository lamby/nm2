from django.conf.urls import include, url
from django.views.generic import TemplateView
from backend.mixins import VisitorTemplateView
from django.conf import settings
from rest_framework import routers

# Uncomment the next two lines to enable the admin:
from django.contrib import admin
admin.autodiscover()

import backend.views as bviews
import process.views as pviews
router = routers.DefaultRouter()
router.register(r'persons', bviews.PersonViewSet, "persons")
router.register(r'processes', pviews.ProcessViewSet, "processes")


urlpatterns = [
    url(r'^robots.txt$', TemplateView.as_view(template_name='robots.txt', content_type="text/plain"), name="root_robots_txt"),
    url(r'^i18n/', include('django.conf.urls.i18n')),
    url(r'^$', VisitorTemplateView.as_view(template_name='index.html'), name="home"),
    url(r'^license/$', VisitorTemplateView.as_view(template_name='license.html'), name="root_license"),
    url(r'^faq/$', VisitorTemplateView.as_view(template_name='faq.html'), name="root_faq"),
    url(r'^legacy/', include("legacy.urls")),
    url(r'^person/', include("person.urls")),
    url(r'^public/', include("public.urls")),
    url(r'^am/', include("restricted.urls")),
    url(r'^fprs/', include("fprs.urls")),
    url(r'^process/', include("process.urls")),
    url(r'^dm/', include("dm.urls")),
    url(r'^api/', include("api.urls")),
    url(r'^apikeys/', include("apikeys.urls")),
    url(r'^keyring/', include("keyring.urls")),
    url(r'^wizard/', include("wizard.urls")),
    url(r'^mia/', include("mia.urls")),
    url(r'^minechangelogs/', include("minechangelogs.urls")),

    url(r'^rest/api/', include(router.urls)),

    # Uncomment the admin/doc line below to enable admin documentation:
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    url(r'^admin/', include(admin.site.urls)),
]

if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns += [
            url(r'^__debug__/', include(debug_toolbar.urls)),
        ]
    except ImportError:
        pass
