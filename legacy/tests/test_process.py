from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import NamedObjects
import process.models as pmodels
from process.unittest import ProcessFixtureMixin


class TestAMDashboard(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.add_named_objects(legacy_processes=NamedObjects(bmodels.Process))
        cls.legacy_processes.create("dc", person=cls.persons.dc, applying_as=cls.persons.dc.status, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_DONE, is_active=False)
        cls.url = reverse("legacy_process", kwargs={ "key": cls.legacy_processes.dc.lookup_key })

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in None, "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "activeam", "fd", "dam":
            cls._add_method(cls._test_success, visitor)
        
    def _test_success(self, visitor):
        client = self.make_test_client(visitor)
        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
