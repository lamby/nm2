from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from django.core import mail
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin
from unittest.mock import patch

class TestMinechangelogs(PersonFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.url = reverse("minechangelogs_search", kwargs={ "key": cls.persons.dc.lookup_key })

    @classmethod
    def __add_extra_tests__(cls):
        cls._add_method(cls._test_forbidden, None)
        for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r",  "dd_nu", "dd_u", "fd", "dam":
            cls._add_method(cls._test_success, visitor)

    def _test_success(self, visitor):
        client = self.make_test_client(self.persons[visitor])
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)

        response = client.post(self.url, data={"query": "test"})
        self.assertEqual(response.status_code, 200)

        response = client.post(self.url, data={"query": "test", "download": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/plain")

    def _test_forbidden(self, visitor):
        client = self.make_test_client(self.persons[visitor])
        response = client.get(self.url)
        self.assertPermissionDenied(response)
