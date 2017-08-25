from django.conf.urls import *
from . import views

urlpatterns = [
    # Show changelogs (minechangelogs)
    url(r'^search/(?P<key>[^/]+)?$', views.MineChangelogs.as_view(), name="minechangelogs_search"),
]
