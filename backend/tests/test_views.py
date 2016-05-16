# coding: utf8
"""
Test permissions
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
from backend import const
from backend.unittest import PersonFixtureMixin

class TestNewnm(PersonFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        for person in ("dc", "dc_ga", "dm", "dm_ga"):
            cls._add_method(cls._test_non_dd, person)

        for person in ("dd_nu", "dd_u", "fd", "dam"):
            cls._add_method(cls._test_dd, person)

        ## pending account
        #cls.person.create("pending", status=const.STATUS_DC, expires=now() + datetime.timedelta(days=1), pending="12345", alioth=True)

#    def _test_get_allowed(self, person):
#        client = self.make_test_client(person)
#        response = client.get(reverse("plant_obtouch_list"))
#        self.assertEquals(response.status_code, 200)
#
#    def _test_get_forbidden(self, person):
#        client = self.make_test_client(person)
#        response = client.get(reverse("plant_obtouch_list"))
#        self.assertPermissionDenied(response)

    def make_test_client(self, person):
        """
        Override the default make_test_client to allow sso-logged-in people
        with no corresponding Person record in the database
        """
        if person and "@" in person:
            return super(TestNewnm, self).make_test_client(None, sso_username=person)
        else:
            return super(TestNewnm, self).make_test_client(person)

    def test_require_login(self):
        client = self.make_test_client(None)
        response = client.get(reverse("public_newnm"))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.context["person"], None)
        self.assertEquals(response.context["errors"], [])
        self.assertEquals(response.context["DAYS_VALID"], 3)
        self.assertContains(response, "Please login first")
        self.assertNotContains(response, "You already have an entry in the system")
        self.assertNotContains(response, "Not only you have an entry, but you are also")
        self.assertNotContains(response, "Apply for an entry in the system")
        self.assertNotContains(response, "Submit disabled because you already have an entry in the system")

    def test_no_person(self):
        client = self.make_test_client("new_person@example.org")
        response = client.get(reverse("public_newnm"))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.context["person"], None)
        self.assertEquals(response.context["errors"], [])
        self.assertEquals(response.context["DAYS_VALID"], 3)
        self.assertNotContains(response, "Please login first")
        self.assertNotContains(response, "You already have an entry in the system")
        self.assertNotContains(response, "Not only you have an entry, but you are also")
        self.assertContains(response, "Apply for an entry in the system")
        self.assertNotContains(response, "Submit disabled because you already have an entry in the system")

    def _test_non_dd(self, person):
        client = self.make_test_client(person)
        response = client.get(reverse("public_newnm"))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.context["person"], self.persons[person])
        self.assertEquals(response.context["errors"], [])
        self.assertEquals(response.context["DAYS_VALID"], 3)
        self.assertNotContains(response, "Please login first")
        self.assertContains(response, "You already have an entry in the system")
        self.assertNotContains(response, "Not only you have an entry, but you are also")
        self.assertNotContains(response, "Apply for an entry in the system")
        self.assertNotContains(response, "Submit disabled because you already have an entry in the system")

    def _test_dd(self, person):
        client = self.make_test_client(person)
        response = client.get(reverse("public_newnm"))
        self.assertEquals(response.status_code, 200)
        self.assertEquals(response.context["person"], self.persons[person])
        self.assertEquals(response.context["errors"], [])
        self.assertEquals(response.context["DAYS_VALID"], 3)
        self.assertNotContains(response, "Please login first")
        self.assertContains(response, "You already have an entry in the system")
        self.assertContains(response, "Not only you have an entry, but you are also")
        self.assertContains(response, "Apply for an entry in the system")
        self.assertContains(response, "Submit disabled because you already have an entry in the system")
