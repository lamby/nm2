from django.test import TestCase
from django.urls import reverse
from django.core import mail
from backend.unittest import PersonFixtureMixin
from backend import const
import process.models as pmodels
import process.views as pviews
from .common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text,
                     test_fingerprint2, test_fpr2_signed_valid_text)


class TestEmeritus(ProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "dd_nu", "dd_u", "fd", "dam":
            cls._add_method(cls._test_success, visitor)
            cls._add_method(cls._test_nonsso_success, visitor)
            cls._add_method(cls._test_existing_success, visitor)
            cls._add_method(cls._test_existing_nonsso_success, visitor)

        for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r":
            cls._add_method(cls._test_forbidden, visitor)
            cls._add_method(cls._test_nonsso_forbidden, visitor)

    def _test_success(self, visitor):
        mail.outbox = []
        client = self.make_test_client(visitor)
        self._test_success_common(visitor, client, reverse("process_emeritus"))

    def _test_existing_success(self, visitor):
        mail.outbox = []
        client = self.make_test_client(visitor)
        self.processes.create("dd_u", person=self.persons[visitor], applying_for=const.STATUS_EMERITUS_DD, fd_comment="test")
        self._test_success_common(visitor, client, reverse("process_emeritus"))

    def _test_nonsso_success(self, visitor):
        mail.outbox = []
        url = pviews.Emeritus.get_nonauth_url(self.persons[visitor])
        client = self.make_test_client(None)
        self._test_success_common(visitor, client, url)

    def _test_existing_nonsso_success(self, visitor):
        mail.outbox = []
        url = pviews.Emeritus.get_nonauth_url(self.persons[visitor])
        client = self.make_test_client(None)
        self.processes.create("dd_u", person=self.persons[visitor], applying_for=const.STATUS_EMERITUS_DD, fd_comment="test")
        self._test_success_common(visitor, client, url)

    def _test_success_common(self, visitor, client, url):
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, url)
        response = client.post(url, data={"statement": "test statement"})
        self.assertRedirectMatches(response, r"/process/\d+$")
        visitor = self.persons[visitor]
        process = pmodels.Process.objects.get(person=visitor, applying_for=const.STATUS_EMERITUS_DD, closed__isnull=True)
        req = process.requirements.get(type="intent")
        status = req.compute_status()
        self.assertTrue(status["satisfied"])
        self.assertEqual(req.statements.count(), 1)
        stm = req.statements.all()[0]
        self.assertEqual(stm.requirement, req)
        self.assertIsNone(stm.fpr)
        self.assertEqual(stm.statement, "test statement")
        self.assertEqual(stm.uploaded_by, visitor)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["debian-private@lists.debian.org"])
        self.assertCountEqual(mail.outbox[0].cc, ["{} <{}>".format(process.person.fullname, process.person.email), process.archive_email, "mia-{}@debian.org".format(process.person.uid)])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "in, retired; emeritus via nm.d.o")

        # Submit again, no statement is added/posted
        mail.outbox = []
        response = client.post(url, data={"statement": "test statement1"})
        self.assertRedirectMatches(response, r"/process/\d+$")
        req.refresh_from_db()
        self.assertEqual(req.statements.count(), 1)
        stm = req.statements.all()[0]
        self.assertEqual(stm.statement, "test statement")
        self.assertEqual(len(mail.outbox), 0)

    def _test_forbidden(self, visitor):
        mail.outbox = []
        client = self.make_test_client(visitor)
        self._test_forbidden_common(visitor, client, reverse("process_emeritus"))

    def _test_nonsso_forbidden(self, visitor):
        mail.outbox = []
        url = pviews.Emeritus.get_nonauth_url(self.persons[visitor])
        client = self.make_test_client(None)
        self._test_forbidden_common(visitor, client, url)

    def _test_forbidden_common(self, visitor, client, url):
        response = client.get(url)
        self.assertPermissionDenied(response)
        response = client.post(url, data={"statement": "test statement"})
        self.assertPermissionDenied(response)
        self.assertEqual(len(mail.outbox), 0)
