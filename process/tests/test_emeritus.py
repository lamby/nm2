from django.test import TestCase
from django.urls import reverse
from django.core import mail
from backend.unittest import PersonFixtureMixin
from .common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text,
                     test_fingerprint2, test_fpr2_signed_valid_text)


class TestEmeritus(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "dd_nu", "dd_u", "fd", "dam":
            cls._add_method(cls._test_success, visitor)

        for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r":
            cls._add_method(cls._test_forbidden, visitor)

    def _test_success(self, visitor):
        mail.outbox = []
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_emeritus"))
        self.assertEqual(response.status_code, 200)
        response = client.post(reverse("process_emeritus"), data={"statement": "test statement"})
        self.assertRedirectMatches(response, r"/process/\d+$")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["debian-private@lists.debian.org"])

    def _test_forbidden(self, visitor):
        mail.outbox = []
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_emeritus"))
        self.assertPermissionDenied(response)
        response = client.post(reverse("process_emeritus"), data={"statement": "test statement"})
        self.assertPermissionDenied(response)
        self.assertEqual(len(mail.outbox), 0)
