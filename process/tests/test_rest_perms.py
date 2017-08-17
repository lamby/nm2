from django.test import TestCase
from django.urls import reverse
from backend import const
from backend.unittest import PersonFixtureMixin
import datetime
import json

class RestPersonTestCase(PersonFixtureMixin, TestCase):
    ANON_FIELDS = (
        'person', 'applying_for', 'started',
        'frozen_by', 'frozen_time',
        'approved_by', 'approved_time',
        'closed', 'rt_ticket',
    )
    ADMIN_FIELDS = ('fd_comment', 'rt_request')

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.create("proc", person=cls.persons["dc"], applying_for=const.STATUS_DD_U, fd_comment="test")

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r", "dd_nu", "dd_u":
            cls._add_method(cls._test_anon, visitor)

        for visitor in "fd", "dam":
            cls._add_method(cls._test_admin, visitor)

    def _test_anon(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('processes-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        for field in self.ANON_FIELDS:
            self.assertIn(field, response.data[0])
        for field in self.ADMIN_FIELDS:
            self.assertNotIn(field, response.data[0])

        response = client.get(reverse('processes-detail', args=[self.processes.proc.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        for field in self.ANON_FIELDS:
            self.assertIn(field, response.data)
        for field in self.ADMIN_FIELDS:
            self.assertNotIn(field, response.data)

    def _test_admin(self, visitor):
        client = self.make_test_apiclient(visitor)
        response = client.get(reverse('processes-list'), format="html")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        for field in self.ANON_FIELDS + self.ADMIN_FIELDS:
            self.assertIn(field, response.data[0])

        response = client.get(reverse('processes-detail', args=[self.processes.proc.pk]), format="html")
        self.assertEqual(response.status_code, 200)
        for field in self.ANON_FIELDS + self.ADMIN_FIELDS:
            self.assertIn(field, response.data)

