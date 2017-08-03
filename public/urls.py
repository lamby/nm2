# coding: utf-8




from django.conf.urls import *
from django.views.generic import RedirectView
from . import views
import person.views as pviews

urlpatterns = [
    url(r'^$', RedirectView.as_view(url="/", permanent=True), name="public_index"),
    url(r'^newnm$', views.Newnm.as_view(), name="public_newnm"),
    url(r'^newnm/resend_challenge/(?P<key>[^/]+)$', views.NewnmResendChallenge.as_view(), name="public_newnm_resend_challenge"),
    url(r'^newnm/confirm/(?P<nonce>[^/]+)$', views.NewnmConfirm.as_view(), name="public_newnm_confirm"),
    url(r'^processes$', views.Processes.as_view(), name="processes"),
    url(r'^managers$', views.Managers.as_view(), name="managers"),
    url(r'^people(?:/(?P<status>\w+))?$', views.People.as_view(), name="people"),
    url(r'^process/(?P<key>[^/]+)$', views.Process.as_view(), name="public_process"),
    url(r'^process/(?P<key>[^/]+)/update_keycheck$', views.ProcessUpdateKeycheck.as_view(), name="public_process_update_keycheck"),
    url(r'^progress/(?P<progress>\w+)$', views.Progress.as_view(), name="public_progress"),
    url(r'^stats$', views.Stats.as_view(), name="public_stats"),
    url(r'^stats/latest$', views.StatsLatest.as_view(), name="public_stats_latest"),
    url(r'^stats/graph$', views.StatsGraph.as_view(), name="public_stats_graph"),
    url(r'^findperson$', views.Findperson.as_view(), name="public_findperson"),
    url(r'^audit_log$', views.AuditLog.as_view(), name="public_audit_log"),

    # Compatibility
    url(r'^person/(?P<key>[^/]+)$', pviews.Person.as_view(), name="deprecated_person"),
    url(r'^whoisam$', views.Managers.as_view(), name="public_whoisam"),
    url(r'^nmstatus/(?P<key>[^/]+)$', views.Process.as_view(), name="public_nmstatus"),
    url(r'^nmlist$', views.Processes.as_view(), name="public_nmlist"),
]
