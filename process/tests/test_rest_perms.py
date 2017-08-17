from django.test import TestCase
from django.urls import reverse
from backend import const
from backend.unittest import PersonFixtureMixin
from backend.tests.test_rest_perms import PersonFieldsMixin
import datetime
import json

class ProcessFieldsMixin(PersonFieldsMixin):
    PROCESS_ANON_FIELDS = (
        'id', 'person', 'applying_for', 'started',
        'frozen_by', 'frozen_time',
        'approved_by', 'approved_time',
        'closed', 'rt_ticket',
    )
    PROCESS_ADMIN_FIELDS = ('fd_comment', 'rt_request')

    def assertAllProcessFieldsAccountedFor(self, record):
        all_fields = frozenset(self.PROCESS_ANON_FIELDS + self.PROCESS_ADMIN_FIELDS)
        self.assertFalse(record.keys() - all_fields)

    def assertProcessAnonFields(self, record):
        for field in self.PROCESS_ANON_FIELDS:
            self.assertIn(field, record)
        for field in self.PROCESS_ADMIN_FIELDS:
            self.assertNotIn(field, record)
        self.assertPersonAnonFields(record["person"])
        self.assertAllProcessFieldsAccountedFor(record)

    def assertProcessDDFields(self, record):
        for field in self.PROCESS_ANON_FIELDS:
            self.assertIn(field, record)
        for field in self.PROCESS_ADMIN_FIELDS:
            self.assertNotIn(field, record)
        self.assertPersonDDFields(record["person"])
        self.assertAllProcessFieldsAccountedFor(record)

    def assertProcessAdminFields(self, record):
        for field in self.PROCESS_ANON_FIELDS + self.PROCESS_ADMIN_FIELDS:
            self.assertIn(field, record)
        self.assertPersonAdminFields(record["person"])
        self.assertAllProcessFieldsAccountedFor(record)


class RestPersonTestCase(PersonFixtureMixin, ProcessFieldsMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.create("proc", person=cls.persons["dc"], applying_for=const.STATUS_DD_U, fd_comment="test")

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
        response = client.get(reverse('processes-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertProcessAnonFields(response.data[0])

        response = client.get(reverse('processes-detail', args=[self.processes.proc.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertProcessAnonFields(response.data)

    def _test_dd(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('processes-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertProcessDDFields(response.data[0])

        response = client.get(reverse('processes-detail', args=[self.processes.proc.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertProcessDDFields(response.data)

    def _test_admin(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('processes-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertProcessAdminFields(response.data[0])

        response = client.get(reverse('processes-detail', args=[self.processes.proc.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertProcessAdminFields(response.data)

