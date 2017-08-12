from django.test import TestCase
from django.urls import reverse
from .common import ProcessFixtureMixin


class TestList(ProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        # Process list is visible by anyone
        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "fd", "dam", None):
            cls._add_method(cls._test_success, visitor)

    def _test_success(self, visitor):
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_list"))
        self.assertEqual(response.status_code, 200)

#    def _test_forbidden(self, visitor):
#        client = self.make_test_client(visitor)
#        response = client.get(reverse("process_list"))
#        self.assertPermissionDenied(response)

