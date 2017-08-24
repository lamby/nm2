from django.conf.urls import *
from django.views.generic import RedirectView
from . import views
import person.views as pviews

urlpatterns = [
    url(r'^$', RedirectView.as_view(url="/", permanent=True), name="public_index"),

    url(r'^newnm$', views.Newnm.as_view(), name="public_newnm"),
    url(r'^newnm/resend_challenge/(?P<key>[^/]+)$', views.NewnmResendChallenge.as_view(), name="public_newnm_resend_challenge"),
    url(r'^newnm/confirm/(?P<nonce>[^/]+)$', views.NewnmConfirm.as_view(), name="public_newnm_confirm"),
    url(r'^managers$', views.Managers.as_view(), name="managers"),
    url(r'^people(?:/(?P<status>\w+))?$', views.People.as_view(), name="people"),
    url(r'^stats$', views.Stats.as_view(), name="public_stats"),
    url(r'^stats/graph$', views.StatsGraph.as_view(), name="public_stats_graph"),
    url(r'^findperson$', views.Findperson.as_view(), name="public_findperson"),
    url(r'^audit_log$', views.AuditLog.as_view(), name="public_audit_log"),

    # Compatibility
    url(r'^person/(?P<key>[^/]+)$', RedirectView.as_view(url="/person/%(key)s", permanent=True)),
    url(r'^whoisam$', RedirectView.as_view(url="/public/manager", permanent=True)),
    url(r'^process/(?P<key>[^/]+)$', RedirectView.as_view(url="/legacy/process/%(key)s", permanent=True)),
    url(r'^nmstatus/(?P<key>[^/]+)$', RedirectView.as_view(url="/legacy/process/%(key)s", permanent=True)),
]
