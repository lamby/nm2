from django.test import TestCase
from backend import ops
from backend import const
from backend.unittest import PersonFixtureMixin
import datetime

class TestOps(PersonFixtureMixin, TestCase):
    def test_change_status(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.person, self.persons.dc)
            self.assertEqual(o.status, const.STATUS_DD_NU)

        o = ops.ChangeStatus(audit_author=self.persons.fd, audit_notes="test message", person=self.persons.dc, status=const.STATUS_DD_NU)
        self.check_op(o, check_contents)

    def test_change_fingerprint(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.person, self.persons.dc)
            self.assertEqual(o.fpr, "123456789ABCDEF0")

        o = ops.ChangeFingerprint(audit_author=self.persons.fd, audit_notes="test message", person=self.persons.dc, fpr="123456789ABCDEF0")
        self.check_op(o, check_contents)

    def test_create_person(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.username, "test_username")
            self.assertEqual(o.cn, "test cn")
            self.assertEqual(o.mn, "")
            self.assertEqual(o.sn, "")
            self.assertEqual(o.email, "test@email")
            self.assertEqual(o.status, const.STATUS_DC)
            self.assertIsNone(o.fpr)
            self.assertIsNone(o.last_login)
            self.assertIsNone(o.date_joined)
            self.assertIsNone(o.created)
            self.assertIsNone(o.expires)

        o = ops.CreatePerson(audit_author=self.persons.fd, audit_notes="test message", username="test_username", cn="test cn", email="test@email", status=const.STATUS_DC)
        self.check_op(o, check_contents)
