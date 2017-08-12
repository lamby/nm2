from django.test import TestCase
from django.urls import reverse
from backend.models import Person
from backend import const
from backend.unittest import PersonFixtureMixin


class TestNewnm(PersonFixtureMixin, TestCase):
    # Use an old, not yet revoked key of mine
    new_person_fingerprint = "66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB"

    @classmethod
    def __add_extra_tests__(cls):
        for person in ("pending", "dc", "dc_ga", "dm", "dm_ga"):
            cls._add_method(cls._test_non_dd, person)

        for person in ("dd_nu", "dd_u", "fd", "dam"):
            cls._add_method(cls._test_dd, person)

    def make_test_client(self, person):
        """
        Override the default make_test_client to allow sso-logged-in people
        with no corresponding Person record in the database
        """
        if person and "@" in person:
            return super(TestNewnm, self).make_test_client(None, sso_username=person)
        else:
            return super(TestNewnm, self).make_test_client(person)

    def assertPostForbidden(self, person):
        person = self.persons[person]
        client = self.make_test_client(person)

        # Posting to newnm to create a new record is forbidden
        response = client.post(reverse("public_newnm"), data={"fpr": self.new_person_fingerprint, "sc_ok": "yes", "dmup_ok": "yes", "cn": "test", "email": "new_person@example.org"})
        self.assertPermissionDenied(response)

        # Trying to resend newnm challenge is forbidden
        if person:
            response = client.get(reverse("public_newnm_resend_challenge", kwargs={"key": person.lookup_key}))
        else:
            response = client.get(reverse("public_newnm_resend_challenge", kwargs={"key": self.persons["pending"].lookup_key}))
        self.assertPermissionDenied(response)

        # Trying to confirm the account is forbidden
        if person:
            response = client.get(reverse("public_newnm_confirm", kwargs={"nonce": person.pending}))
        else:
            response = client.get(reverse("public_newnm_confirm", kwargs={"nonce": self.persons["pending"].pending}))
        self.assertPermissionDenied(response)

    def test_require_login(self):
        client = self.make_test_client(None)
        response = client.get(reverse("public_newnm"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["person"], None)
        self.assertEqual(response.context["errors"], [])
        self.assertEqual(response.context["DAYS_VALID"], 3)
        self.assertContains(response, "Please login first")
        self.assertNotContains(response, "You already have an entry in the system")
        self.assertNotContains(response, "Not only you have an entry, but you are also")
        self.assertNotContains(response, "Apply for an entry in the system")
        self.assertNotContains(response, "Submit disabled because you already have an entry in the system")
        self.assertPostForbidden(None)

    def test_no_person(self):
        client = self.make_test_client("new_person-guest@users.alioth.debian.org")
        response = client.get(reverse("public_newnm"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["person"], None)
        self.assertEqual(response.context["errors"], [])
        self.assertEqual(response.context["DAYS_VALID"], 3)
        self.assertNotContains(response, "Please login first")
        self.assertNotContains(response, "You already have an entry in the system")
        self.assertNotContains(response, "Not only you have an entry, but you are also")
        self.assertContains(response, "Apply for an entry in the system")
        self.assertNotContains(response, "Submit disabled because you already have an entry in the system")

        # A new Person is created on POST
        response = client.post(reverse("public_newnm"), data={"fpr": self.new_person_fingerprint, "sc_ok": "yes", "dmup_ok": "yes", "cn": "test", "email": "new_person@example.org"})
        self.assertRedirectMatches(response, reverse("public_newnm_resend_challenge", kwargs={"key": "new_person@example.org"}))
        new_person = Person.lookup("new_person@example.org")
        self.assertEqual(new_person.status, const.STATUS_DC)
        self.assertIsNotNone(new_person.expires)
        self.assertIsNotNone(new_person.pending)

        # The new person can resend the challenge email
        response = client.get(reverse("public_newnm_resend_challenge", kwargs={"key": "new_person@example.org"}))
        self.assertRedirectMatches(response, new_person.get_absolute_url())

        # The new person has a page in the system
        response = client.get(new_person.get_absolute_url())
        self.assertEqual(response.status_code, 200)

        # The new person can confirm its record
        response = client.get(reverse("public_newnm_confirm", kwargs={"nonce": new_person.pending}))
        self.assertRedirectMatches(response, new_person.get_absolute_url())
        new_person = Person.objects.get(pk=new_person.pk)
        self.assertEqual(new_person.status, const.STATUS_DC)
        self.assertIsNotNone(new_person.expires)
        self.assertEqual(new_person.pending, "")

    def _test_non_dd(self, person):
        client = self.make_test_client(person)
        response = client.get(reverse("public_newnm"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["person"], self.persons[person])
        self.assertEqual(response.context["errors"], [])
        self.assertEqual(response.context["DAYS_VALID"], 3)
        self.assertNotContains(response, "Please login first")
        self.assertContains(response, "You already have an entry in the system")
        self.assertNotContains(response, "Not only you have an entry, but you are also")
        self.assertNotContains(response, "Apply for an entry in the system")
        self.assertNotContains(response, "Submit disabled because you already have an entry in the system")
        self.assertPostForbidden(None)

    def _test_dd(self, person):
        client = self.make_test_client(person)
        response = client.get(reverse("public_newnm"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["person"], self.persons[person])
        self.assertEqual(response.context["errors"], [])
        self.assertEqual(response.context["DAYS_VALID"], 3)
        self.assertNotContains(response, "Please login first")
        self.assertContains(response, "You already have an entry in the system")
        self.assertContains(response, "Not only you have an entry, but you are also")
        self.assertContains(response, "Apply for an entry in the system")
        self.assertContains(response, "Submit disabled because you already have an entry in the system")
        self.assertPostForbidden(None)
