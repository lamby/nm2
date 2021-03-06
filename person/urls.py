from django.conf.urls import url
from django.views.generic import RedirectView
from . import views

urlpatterns = [
    url(r'^$', RedirectView.as_view(url="/", permanent=True), name="person_index"),
    url(r'^(?P<key>[^/]+)$', views.Person.as_view(), name="person"),
    url(r'^(?P<key>[^/]+)/edit_ldap$', views.EditLDAP.as_view(), name="person_edit_ldap"),
    url(r'^(?P<key>[^/]+)/edit_bio$', views.EditBio.as_view(), name="person_edit_bio"),
    url(r'^(?P<key>[^/]+)/edit_email$', views.EditEmail.as_view(), name="person_edit_email"),
    # AM preferences editor
    url(r'^(?P<key>[^/]+)/amprofile$', views.AMProfile.as_view(), name="person_amprofile"),
]

