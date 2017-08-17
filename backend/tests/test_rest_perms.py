from django.test import TestCase
from django.urls import reverse
from backend.unittest import PersonFixtureMixin
import datetime
import json

class PersonFieldsMixin:
    PERSON_ANON_FIELDS = (
        'id', 'cn', 'mn', 'sn', 'fullname',
        'bio', 'uid',
        'status', 'status_changed',
        'fpr'
    )
    PERSON_DD_FIELDS = ('username', 'is_staff', 'email')
    PERSON_ADMIN_FIELDS = ('email_ldap', 'fd_comment')

    def assertAllPersonFieldsAccountedFor(self, record):
        all_fields = frozenset(self.PERSON_ANON_FIELDS + self.PERSON_DD_FIELDS + self.PERSON_ADMIN_FIELDS)
        self.assertFalse(record.keys() - all_fields)

    def assertPersonAnonFields(self, record):
        for field in self.PERSON_ANON_FIELDS:
            self.assertIn(field, record)
        for field in self.PERSON_DD_FIELDS + self.PERSON_ADMIN_FIELDS:
            self.assertNotIn(field, record)
        self.assertAllPersonFieldsAccountedFor(record)

    def assertPersonDDFields(self, record):
        for field in self.PERSON_ANON_FIELDS + self.PERSON_DD_FIELDS:
            self.assertIn(field, record)
        for field in self.PERSON_ADMIN_FIELDS:
            self.assertNotIn(field, record)
        self.assertAllPersonFieldsAccountedFor(record)

    def assertPersonAdminFields(self, record):
        for field in self.PERSON_ANON_FIELDS + self.PERSON_DD_FIELDS + self.PERSON_ADMIN_FIELDS:
            self.assertIn(field, record)
        self.assertAllPersonFieldsAccountedFor(record)


class RestPersonTestCase(PersonFixtureMixin, PersonFieldsMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r":
            cls._add_method(cls._test_anon, visitor)

        for visitor in "dd_nu", "dd_u":
            cls._add_method(cls._test_dd, visitor)

        for visitor in "fd", "dam":
            cls._add_method(cls._test_admin, visitor)


    def _test_anon(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('persons-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 13)
        self.assertPersonAnonFields(response.data[0])

        response = client.get(reverse('persons-detail', args=[self.persons.fd.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertPersonAnonFields(response.data)

    def _test_dd(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('persons-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 13)
        self.assertPersonDDFields(response.data[0])

        response = client.get(reverse('persons-detail', args=[self.persons.fd.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertPersonDDFields(response.data)

    def _test_admin(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('persons-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 13)
        self.assertPersonAdminFields(response.data[0])

        response = client.get(reverse('persons-detail', args=[self.persons.fd.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertPersonAdminFields(response.data)
