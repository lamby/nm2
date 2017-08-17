from django.test import TestCase
from django.urls import reverse
from backend.unittest import PersonFixtureMixin
import datetime
import json

class RestPersonTestCase(PersonFixtureMixin, TestCase):
    ANON_FIELDS = (
        'cn', 'mn', 'sn', 'fullname',
        'bio', 'uid',
        'status', 'status_changed',
        'fpr'
    )
    DD_FIELDS = ('username', 'is_staff', 'email')
    ADMIN_FIELDS = ('email_ldap', 'fd_comment')

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
        for field in self.ANON_FIELDS:
            self.assertIn(field, response.data[0])
        for field in self.DD_FIELDS + self.ADMIN_FIELDS:
            self.assertNotIn(field, response.data[0])

        response = client.get(reverse('persons-detail', args=[self.persons.fd.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        for field in self.ANON_FIELDS:
            self.assertIn(field, response.data)
        for field in self.DD_FIELDS + self.ADMIN_FIELDS:
            self.assertNotIn(field, response.data)

    def _test_dd(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('persons-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 13)
        for field in self.ANON_FIELDS + self.DD_FIELDS:
            self.assertIn(field, response.data[0])
        for field in self.ADMIN_FIELDS:
            self.assertNotIn(field, response.data[0])

        response = client.get(reverse('persons-detail', args=[self.persons.fd.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        for field in self.ANON_FIELDS + self.DD_FIELDS:
            self.assertIn(field, response.data)
        for field in self.ADMIN_FIELDS:
            self.assertNotIn(field, response.data)

    def _test_admin(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('persons-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 13)
        for field in self.ANON_FIELDS + self.DD_FIELDS + self.ADMIN_FIELDS:
            self.assertIn(field, response.data[0])

        response = client.get(reverse('persons-detail', args=[self.persons.fd.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        for field in self.ANON_FIELDS + self.DD_FIELDS + self.ADMIN_FIELDS:
            self.assertIn(field, response.data)
