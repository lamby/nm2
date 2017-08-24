from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
import process.models as pmodels
from process.unittest import ProcessFixtureMixin


class TestAMDashboard(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.create("dc", person=cls.persons.dc, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.amassignments.create("am", process=cls.processes.dc, am=cls.ams.am, assigned_by=cls.persons.fd, assigned_time=now())

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in None, "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r":
            cls._add_method(cls._test_forbidden, visitor)
        
        for visitor in "am", "activeam", "fd", "dam":
            cls._add_method(cls._test_success, visitor)

    def _test_success(self, visitor):
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_am_dashboard"))
        self.assertEqual(response.status_code, 200)

    def _test_forbidden(self, visitor):
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_am_dashboard"))
        self.assertPermissionDenied(response)
