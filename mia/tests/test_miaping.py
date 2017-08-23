from django.test import TestCase
from django.urls import reverse
from django.core import mail
from backend.unittest import PersonFixtureMixin
from backend import const
import process.models as pmodels
import process.views as pviews
from process.tests.common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text,
                     test_fingerprint2, test_fpr2_signed_valid_text)


class TestMiaPing(PersonFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        for visited in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r":
            for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r", "dd_nu", "dd_u", "fd", "dam":
                cls._add_method(cls._test_forbidden, visitor, visited)

        for visited in "dd_nu", "dd_u", "fd", "dam":
            for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r", "dd_nu", "dd_u":
                cls._add_method(cls._test_forbidden, visitor, visited)
            for visitor in "fd", "dam":
                cls._add_method(cls._test_success, visitor, visited)

    def _test_success(self, visitor, visited):
        mail.outbox = []
        client = self.make_test_client(visitor)
        response = client.get(reverse("mia_wat_ping", args=[self.persons[visited].lookup_key]))
        self.assertEqual(response.status_code, 200)

        # get the mail from context form initial value
        email = response.context["form"].initial["email"]
        self.assertIsNotNone(email)

        response = client.post(reverse("mia_wat_ping", args=[self.persons[visited].lookup_key]), data={"email": email})
        self.assertRedirectMatches(response, r"/process/\d+$")

        process = pmodels.Process.objects.get(person=self.persons[visited], applying_for=const.STATUS_EMERITUS_DD, closed__isnull=True)
        self.assertIsNone(process.frozen_by)
        self.assertIsNone(process.approved_by)
        self.assertIsNone(process.closed)
        log = process.log.order_by("-logdate")[0]
        self.assertEqual(log.changed_by, self.persons[visitor])
        self.assertEqual(log.process, process)
        self.assertIsNone(log.requirement)
        self.assertTrue(log.is_public)
        self.assertEqual(log.action, "")
        self.assertEquals(log.logtext, "Sent WAT ping email")

        mia_addr = "mia-{}@qa.debian.org".format(self.persons[visited].uid)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "Debian MIA team <wat@debian.org>")
        self.assertEqual(mail.outbox[0].to, [self.persons[visited].email])
        self.assertEqual(mail.outbox[0].cc, ["archive-{}@nm.debian.org".format(process.pk)])
        self.assertEqual(mail.outbox[0].bcc, [mia_addr, "wat@debian.org"])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "out, wat; WAT by nm.d.o")
        self.assertIn(reverse("process_emeritus") + "?t=", mail.outbox[0].body)
        self.assertIn(reverse("process_cancel", args=[process.pk]), mail.outbox[0].body)
        self.assertIn(process.get_absolute_url(), mail.outbox[0].body)

    def _test_forbidden(self, visitor, visited):
        mail.outbox = []
        client = self.make_test_client(visitor)
