from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch
from backend.unittest import PersonFixtureMixin
from backend import const
import process.models as pmodels
import process.views as pviews
from .common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text,
                     test_fingerprint2, test_fpr2_signed_valid_text)


class TestCancel(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.create("proc", person=cls.persons.dc, applying_for=const.STATUS_DD_U)

    def test_anonymous(self):
        client = self.make_test_client(None)
        response = client.get(reverse("process_cancel", args=[self.processes.proc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<form id="cancel"')

        response = client.post(reverse("process_cancel", args=[self.processes.proc.pk]), data={
            "statement": "test statement",
            "is_public": True,
        })
        self.assertPermissionDenied(response)

    def test_no_proc_close(self):
        client = self.make_test_client(self.persons.dc)
        with patch.object(pmodels.Process, "permissions_of", return_value=set()):
            response = client.get(reverse("process_cancel", args=[self.processes.proc.pk]))
            self.assertPermissionDenied(response)

            response = client.post(reverse("process_cancel", args=[self.processes.proc.pk]), data={
                "statement": "test statement",
                "is_public": True,
            })
            self.assertPermissionDenied(response)

    def test_proc_close(self):
        client = self.make_test_client(self.persons.dc)
        with patch.object(pmodels.Process, "permissions_of", return_value=set(["proc_close"])):
            response = client.get(reverse("process_cancel", args=[self.processes.proc.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, '<form id="cancel"')

            response = client.post(reverse("process_cancel", args=[self.processes.proc.pk]), data={
                "statement": "test statement",
                "is_public": True,
            })
            self.assertRedirectMatches(response, self.processes.proc.get_absolute_url())

        proc = self.processes.proc
        proc.refresh_from_db()
        self.assertIsNotNone(proc.closed)
        log = proc.log.order_by("-logdate")[0]
        self.assertEqual(log.changed_by, self.persons.dc)
        self.assertIsNone(log.requirement)
        self.assertTrue(log.is_public)
        self.assertEqual(log.action, "proc_close")
        self.assertEqual(log.logtext, "test statement")
