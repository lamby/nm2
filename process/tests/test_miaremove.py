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


class TestMiaRemove(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.create("proc", person=cls.persons.dd_u, applying_for=const.STATUS_EMERITUS_DD)

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r":
            cls._add_method(cls._test_forbidden, visitor)

        for visitor in "fd", "dam":
            cls._add_method(cls._test_success, visitor)

    def _test_success(self, visitor):
        mail.outbox = []
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_mia_remove", args=[self.processes.proc.pk]))
        self.assertEqual(response.status_code, 200)

        # get the mail from context form initial value
        email = response.context["form"].fields["email"].initial

        response = client.post(reverse("process_mia_remove", args=[self.processes.proc.pk]), data={"email": email})
        self.assertRedirectMatches(response, r"/process/\d+$")

        process = self.processes.proc
        process.refresh_from_db()
        self.assertEquals(process.applying_for, const.STATUS_REMOVED_DD)
        self.assertIsNone(process.frozen_by)
        self.assertIsNone(process.approved_by)
        self.assertIsNone(process.closed)

        intent = process.requirements.get(type="intent")

        log = process.log.order_by("pk")[0]
        self.assertEqual(log.changed_by, self.persons[visitor])
        self.assertEqual(log.process, process)
        self.assertEqual(log.requirement, intent)
        self.assertTrue(log.is_public)
        self.assertEqual(log.action, "req_approve")
        self.assertEquals(log.logtext, "Notifying intention to remove the account")

        log = process.log.order_by("pk")[1]
        self.assertEqual(log.changed_by, self.persons[visitor])
        self.assertEqual(log.process, process)
        self.assertEqual(log.requirement, intent)
        self.assertTrue(log.is_public)
        self.assertEqual(log.action, "req_approve")
        self.assertEquals(log.logtext, "Requirement satisfied with intent to remove")

        self.assertEqual(intent.approved_by, self.persons[visitor])
        self.assertEqual(intent.statements.count(), 1)
        stm = intent.statements.get()
        self.assertIsNone(stm.fpr)
        self.assertIn(email, fpr.statement)
        self.assertEqual(stm.uploaded_by, self.persons[visitor])

        mia_addr = "mia-{}@qa.debian.org".format(self.persons[visited].uid)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "Debian MIA team <wat@debian.org>")
        self.assertEqual(mail.outbox[0].to, ["debian-private@lists.debian.org"])
        self.assertEqual(mail.outbox[0].cc, [self.persons[visited].email, "archive-{}@nm.debian.org".format(process.pk)])
        self.assertEqual(mail.outbox[0].bcc, [mia_addr, "wat@debian.org"])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "out, wat; WAT by nm.d.o TODO") # FIXME: ask mapreri
        self.assertIn(reverse("process_emeritus") + "\n", mail.outbox[0].body)
        self.assertIn(reverse("process_cancel", args=[process.pk]), mail.outbox[0].body)
        self.assertIn(process.get_absolute_url(), mail.outbox[0].body)

    def _test_forbidden(self, visitor):
        mail.outbox = []
        url = reverse("process_mia_remove", args=[self.processes.proc.pk])
        client = self.make_test_client(visitor)
        response = client.get(url)
        self.assertPermissionDenied(response)
        response = client.post(url, data={"statement": "test statement"})
        self.assertPermissionDenied(response)
        self.assertEqual(len(mail.outbox), 0)
