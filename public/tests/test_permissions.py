# coding: utf8
"""
Test permissions
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from backend import const
from backend.test_common import *

class PermissionsTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def test_newnm(self):
        """
        newnm works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_newnm")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

    def test_processes(self):
        """
        processes works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("processes")
            def __unicode__(self): return "visiting {}".format(self.url)
        class ThenSeesFDComments(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenSeesFDComments, self).__call__(fixture, response, when, test_client)
                if b"FD_COMMENTS" not in response.content:
                    fixture.fail("FD comments not visible by {} when {}".format(when.user, when))
        class ThenDoesNotSeeFDComments(ThenSuccess):
            def __call__(self, fixture, response, when, test_client):
                super(ThenDoesNotSeeFDComments, self).__call__(fixture, response, when, test_client)
                if b"FD_COMMENTS" in response.content:
                    fixture.fail("FD comments are visible by {} when {}".format(when.user, when))

        self.assertVisit(WhenView(), ThenDoesNotSeeFDComments())
        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenView(user=self.users[u]), ThenDoesNotSeeFDComments())
        for u in ("fd", "dam"):
            self.assertVisit(WhenView(user=self.users[u]), ThenSeesFDComments())

    def test_managers(self):
        """
        managers works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("managers")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

    def test_stats(self):
        """
        stats works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_stats")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

    def test_stats_latest(self):
        """
        stats/latest works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_stats_latest")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

    def test_findperson(self):
        """
        findperson works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_findperson")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

        # TODO: test POST

    def test_people(self):
        """
        stats/latest works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("people")
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

    def test_person(self):
        """
        person works for all users
        """
        class WhenViewSelf(NMTestUtilsWhen):
            def setUp(self, fixture):
                super(WhenViewSelf, self).setUp(fixture)
                self.url = reverse("person", kwargs={ "key": self.user.lookup_key })
        self.assertVisit(WhenViewSelf(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenViewSelf(user=u), ThenSuccess())

        # TODO: test visiting other people's pages, and what is their content

    def test_process(self):
        """
        process works for all users
        """
        class WhenViewOther(NMTestUtilsWhen):
            def setUp(self, fixture):
                super(WhenViewOther, self).setUp(fixture)
                self.person = bmodels.Person.objects.create(cn="Other", email="other@example.org", status=const.STATUS_MM)
                self.process = bmodels.Process.objects.create(person=self.person,
                                               applying_as=const.STATUS_MM,
                                               applying_for=const.STATUS_DD_NU,
                                               progress=const.PROGRESS_APP_OK,
                                               is_active=True)
                self.url = reverse("public_process", kwargs={ "key": self.process.lookup_key })

            def tearDown(self, fixture):
                super(WhenViewOther, self).setUp(fixture)
                self.process.delete()
                self.person.delete()

        self.assertVisit(WhenViewOther(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenViewOther(user=u), ThenSuccess())

        # TODO: test visiting various combinations (applicant, dd, advocate and
        #       so on) and check what info are present in the page

    def test_progress(self):
        """
        progress works for all users
        """
        class WhenView(NMTestUtilsWhen):
            url = reverse("public_progress", kwargs={ "progress": "app_ok" })
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.itervalues():
            self.assertVisit(WhenView(user=u), ThenSuccess())

# TODO: url(r'^newnm/resend_challenge/(?P<key>[^/]+)$', 'newnm_resend_challenge', name="public_newnm_resend_challenge"),
# TODO: url(r'^newnm/confirm/(?P<nonce>[^/]+)$', 'newnm_confirm', name="public_newnm_confirm"),

# TODO: Compatibility
#    url(r'^whoisam$', 'managers', name="public_whoisam"),
#    url(r'^nmstatus/(?P<key>[^/]+)$', 'process', name="public_nmstatus"),
#    url(r'^nmlist$', 'processes', name="public_nmlist"),
