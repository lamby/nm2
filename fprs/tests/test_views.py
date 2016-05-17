# coding: utf8
"""
Test DM claim interface
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
from backend.models import Person, Fingerprint
from backend import const
from backend.unittest import PersonFixtureMixin
from keyring.models import Key


class TestPersonFingerprints(PersonFixtureMixin, TestCase):
    # Use an old, not yet revoked key of mine
    test_fingerprint1 = "66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB"
    test_fingerprint2 = "1793D6AB75663E6BF104953A634F4BD1E7AD5568"

    @classmethod
    def setUpClass(cls):
        super(TestPersonFingerprints, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        cls.persons.create("adv", status=const.STATUS_DD_NU)
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am, advocates=[cls.persons.adv])

    @classmethod
    def __add_extra_tests__(cls):
        # Anonymous cannot see or edit anyone's keys
        for person in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "fd", "dam"):
            cls._add_method(cls._test_get_forbidden, None, person)
            cls._add_method(cls._test_post_forbidden, None, person)

        # Only confirmed people with no entries in LDAP can see and edit their own keys
        for person in ("dc", "dm"):
            cls._add_method(cls._test_get_success, person, person)
            cls._add_method(cls._test_post_success, person, person)
        for person in ("pending", "dc_ga", "dm_ga", "dd_nu", "dd_u", "fd", "dam"):
            cls._add_method(cls._test_get_forbidden, person, person)
            cls._add_method(cls._test_post_forbidden, person, person)

        # Only applicant, advocate, am, fd and dam can see and edit the keys of an applicant
        for person in ("app", "adv", "am", "fd", "dam"):
            cls._add_method(cls._test_get_success, person, "app")
            cls._add_method(cls._test_post_success, person, "app")
        for person in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u"):
            cls._add_method(cls._test_get_forbidden, person, "app")
            cls._add_method(cls._test_post_forbidden, person, "app")

    def _test_get_success(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.get(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        self.assertEquals(response.status_code, 200)

    def _test_post_success(self, visitor, visited):
        client = self.make_test_client(visitor)

        # Add one fingerprint
        response = client.post(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}), data={"fpr": self.test_fingerprint1})
        self.assertRedirectMatches(response, reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        fpr1 = Fingerprint.objects.get(fpr=self.test_fingerprint1)
        self.assertEquals(fpr1.is_active, True)
        self.assertEquals(fpr1.endorsement, "")
        self.assertEquals(fpr1.endorsement_valid, False)
        self.assertEquals(fpr1.person, self.persons[visited])

        # Add a second one, it becomes the active one
        response = client.post(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}), data={"fpr": self.test_fingerprint2})
        self.assertRedirectMatches(response, reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        fpr2 = Fingerprint.objects.get(fpr=self.test_fingerprint2)
        self.assertEquals(fpr2.is_active, True)
        self.assertEquals(fpr2.endorsement, "")
        self.assertEquals(fpr2.endorsement_valid, False)
        self.assertEquals(fpr2.person, self.persons[visited])

        fpr1 = Fingerprint.objects.get(fpr=self.test_fingerprint1)
        self.assertEquals(fpr1.is_active, False)

        # Activate the first one
        response = client.post(reverse("fprs_person_activate", kwargs={"key": self.persons[visited].lookup_key, "fpr": self.test_fingerprint1}))
        self.assertRedirectMatches(response, reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        fpr1 = Fingerprint.objects.get(fpr=self.test_fingerprint1)
        fpr2 = Fingerprint.objects.get(fpr=self.test_fingerprint2)
        self.assertEquals(fpr1.is_active, True)
        self.assertEquals(fpr2.is_active, False)

    def _test_get_forbidden(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.get(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        self.assertPermissionDenied(response)

    def _test_post_forbidden(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.post(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}), data={"fpr": self.test_fingerprint1})
        self.assertPermissionDenied(response)
