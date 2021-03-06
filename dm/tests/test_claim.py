"""
Test DM claim interface
"""
from django.test import TestCase
from django.urls import reverse
from backend.models import Person, Fingerprint
from backend import const
from backend.unittest import PersonFixtureMixin
from keyring.models import Key


class TestClaim(PersonFixtureMixin, TestCase):
    # Use an old, not yet revoked key of mine
    test_fingerprint = "66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB"

    @classmethod
    def __add_extra_tests__(cls):
        for person in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r"):
            cls._add_method(cls._test_success, person)

        for person in ("dd_nu", "dd_u", "fd", "dam"):
            cls._add_method(cls._test_is_dd, person)

    def make_test_client(self, person):
        """
        Override the default make_test_client to allow sso-logged-in people
        with no corresponding Person record in the database
        """
        if person and "@" in person:
            return super(TestClaim, self).make_test_client(None, sso_username=person)
        else:
            return super(TestClaim, self).make_test_client(person)

    def get_confirm_url(self, person):
        """
        Set up a test case where person has an invalid username and
        self.test_fingerprint as fingerprint, and request a claim url.

        Returns the original username of the person, and the plaintext claim
        url.
        """
        person = self.persons[person]
        orig_username = person.username
        person.username = "invalid@example.org"
        person.save(audit_skip=True)
        fpr = Fingerprint.objects.create(fpr=self.test_fingerprint, person=person, is_active=True, audit_skip=True)

        client = self.make_test_client(orig_username)
        response = client.get(reverse("dm_claim"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["username"], orig_username)

        response = client.post(reverse("dm_claim"), data={"fpr": self.test_fingerprint})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["username"], orig_username)
        self.assertEqual(response.context["fpr"].fpr, self.test_fingerprint)
        self.assertIn("/dm/claim/confirm", response.context["plaintext"])
        self.assertIn(b"-----BEGIN PGP MESSAGE-----", response.context["challenge"])
        return orig_username, response.context["plaintext"].strip()

    def _test_success(self, person):
        orig_username, confirm_url = self.get_confirm_url(person)
        client = self.make_test_client(orig_username)
        response = client.get(confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["errors"], [])
        person = Person.objects.get(pk=self.persons[person].pk)
        # The username has now been set
        self.assertEqual(person.username, orig_username)

    def _test_is_dd(self, person):
        orig_username, confirm_url = self.get_confirm_url(person)
        client = self.make_test_client(orig_username)
        response = client.get(confirm_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["errors"], ["The GPG fingerprint corresponds to a Debian Developer."])
        person = Person.objects.get(pk=self.persons[person].pk)
        # The username has not been set
        self.assertEqual(person.username, "invalid@example.org")

    def test_anonymous(self):
        client = self.make_test_client(None)
        response = client.get(reverse("dm_claim"))
        self.assertPermissionDenied(response)
        response = client.get(reverse("dm_claim_confirm", kwargs={"token": "123456"}))
        self.assertPermissionDenied(response)
