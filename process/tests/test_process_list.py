# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
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
        self.assertEquals(response.status_code, 200)

#    def _test_forbidden(self, visitor):
#        client = self.make_test_client(visitor)
#        response = client.get(reverse("process_list"))
#        self.assertPermissionDenied(response)

