from django.test import TestCase
from django.utils.timezone import now
from django.core import mail
from backend import const
from backend import models as bmodels
from process import models as pmodels
from mia import ops as mops
from process.tests.common import ProcessFixtureMixin
from backend.tests.test_ops import TestOpMixin
import datetime


class TestOps(ProcessFixtureMixin, TestOpMixin, TestCase):
    def test_wat_remove(self):
        op_ping = mops.WATPing(audit_author=self.persons.fd, person=self.persons.dd_u, text="test ping")
        op_ping.execute()

        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.process, op_ping._process)
            self.assertEqual(o.text, "test remove")

        o = mops.WATRemove(audit_author=self.persons.fd, audit_notes="test message", process=op_ping._process, text="test remove")
        self.check_op(o, check_contents)
