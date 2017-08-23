from django.test import TestCase
from django.urls import reverse
from django.core import mail
from backend.unittest import PersonFixtureMixin
from backend.tests.test_ops import TestOpMixin
from backend import const
import process.models as pmodels
import process.views as pviews
from process.tests.common import ProcessFixtureMixin
from backend import ops as bops
from mia import ops as mops
import datetime


class TestWatPing(PersonFixtureMixin, TestOpMixin, TestCase):
    def test_base_op(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.person, self.persons.dd_u)
            self.assertEqual(o.text, "test ping")

        o = mops.WATPing(audit_author=self.persons.fd, audit_notes="test message", person=self.persons.dd_u, text="test ping")
        self.check_op(o, check_contents)

    def test_op(self):
        mail.outbox = []
        o = mops.WATPing(audit_author=self.persons.fd, audit_notes="test message", person=self.persons.dd_u, text="test ping")
        o.execute()

        self.assertIsNotNone(o._process)
        process = o._process
        self.assertIsNone(process.frozen_by)
        self.assertIsNone(process.approved_by)
        self.assertIsNone(process.closed)
        log = process.log.order_by("-logdate")[0]
        self.assertEqual(log.changed_by, self.persons.fd)
        self.assertEqual(log.process, process)
        self.assertIsNone(log.requirement)
        self.assertTrue(log.is_public)
        self.assertEqual(log.action, "")
        self.assertEquals(log.logtext, "test message")

        mia_addr = "mia-{}@qa.debian.org".format(self.persons.dd_u.uid)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, "Debian MIA team <wat@debian.org>")
        self.assertEqual(mail.outbox[0].to, [self.persons.dd_u.email])
        self.assertEqual(mail.outbox[0].cc, ["archive-{}@nm.debian.org".format(process.pk)])
        self.assertEqual(mail.outbox[0].bcc, [mia_addr, "wat@debian.org"])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "out, wat; WAT by nm.d.o")
        self.assertIn(reverse("process_emeritus") + "?t=", mail.outbox[0].body)
        self.assertIn(reverse("process_cancel", args=[process.pk]), mail.outbox[0].body)
        self.assertIn(process.get_absolute_url(), mail.outbox[0].body)
        self.assertIn("test ping", mail.outbox[0].body)

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
        with bops.Operation.test_collect() as ops:
            client = self.make_test_client(visitor)
            response = client.get(reverse("mia_wat_ping", args=[self.persons[visited].lookup_key]))
            self.assertEqual(response.status_code, 200)
            # get the mail from context form initial value
            email = response.context["form"].initial["email"]
            self.assertIsNotNone(email)
            self.assertEqual(len(ops), 0)

            response = client.post(reverse("mia_wat_ping", args=[self.persons[visited].lookup_key]), data={"email": email})
            self.assertRedirectMatches(response, r"/process/\d+$")
            self.assertEqual(len(ops), 1)
            op = ops[0]
            self.assertEqual(op.audit_author, self.persons[visitor])
            self.assertEqual(op.audit_notes, "Sent WAT ping email")
            self.assertEqual(op.person, self.persons[visited])
            self.assertEqual(op.text, email)

    def _test_forbidden(self, visitor, visited):
        mail.outbox = []
        client = self.make_test_client(visitor)
