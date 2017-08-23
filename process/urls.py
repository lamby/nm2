from django.conf.urls import url
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^$', views.List.as_view(), name="process_list"),
    url(r'^create/(?P<key>[^/]+)$', views.Create.as_view(), name="process_create"),
    url(r'^(?P<pk>\d+)$', views.Show.as_view(), name="process_show"),
    url(r'^(?P<pk>\d+)/intent$', views.ReqIntent.as_view(), name="process_req_intent"),
    url(r'^(?P<pk>\d+)/sc_dmup$', views.ReqAgreements.as_view(), name="process_req_sc_dmup"),
    url(r'^(?P<pk>\d+)/advocate$', views.ReqAdvocate.as_view(), name="process_req_advocate"),
    url(r'^(?P<pk>\d+)/am_ok$', views.ReqAM.as_view(), name="process_req_am_ok"),
    url(r'^(?P<pk>\d+)/keycheck$', views.ReqKeycheck.as_view(), name="process_req_keycheck"),
    url(r'^(?P<pk>\d+)/add_log$', views.AddProcessLog.as_view(), name="process_add_log"),
    url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/create$', views.StatementCreate.as_view(), name="process_statement_create"),
    url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/(?P<st>\d+)/delete$', views.StatementDelete.as_view(), name="process_statement_delete"),
    url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/(?P<st>\d+)/raw$', views.StatementRaw.as_view(), name="process_statement_raw"),
    url(r'^(?P<pk>\d+)/assign_am$', views.AssignAM.as_view(), name="process_assign_am"),
    url(r'^(?P<pk>\d+)/unassign_am$', views.UnassignAM.as_view(), name="process_unassign_am"),
    url(r'^(?P<pk>\d+)/mailbox/download$', views.MailArchive.as_view(), name="process_mailbox_download"), # TODO: test
    url(r'^(?P<pk>\d+)/mailbox$', views.DisplayMailArchive.as_view(), name="process_mailbox_show"), # TODO: test
    url(r'^(?P<pk>\d+)/update_keycheck$', views.UpdateKeycheck.as_view(), name="process_update_keycheck"), # TODO: test
    url(r'^(?P<pk>\d+)/download_statements$', views.DownloadStatements.as_view(), name="process_download_statements"), # TODO: test
    url(r'^(?P<pk>\d+)/rt_ticket$', views.MakeRTTicket.as_view(), name="process_rt_ticket"),
    url(r'^(?P<pk>\d+)/approve$', views.Approve.as_view(), name="process_approve"),
    url(r'^emeritus(?:/(?P<key>[^/]+))?$', views.Emeritus.as_view(), name="process_emeritus"),
    url(r'^(?P<pk>\d+)/cancel$', views.Cancel.as_view(), name="process_cancel"),
]
