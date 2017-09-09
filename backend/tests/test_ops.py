from django.test import TestCase
from django.utils.timezone import utc
from backend import ops
from backend import const
from backend.unittest import PersonFixtureMixin
import datetime

class TestChangeStatus(PersonFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.audit_time = datetime.datetime(2000, 1, 2, 3, 4, 5, tzinfo=utc)

    def test_op(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertEqual(o.audit_time, self.audit_time)
            self.assertEqual(o.person, self.persons.dc)
            self.assertEqual(o.status, const.STATUS_DD_NU)
            self.assertEqual(o.rt_ticket, 123)

        o = ops.ChangeStatus(
                audit_author=self.persons.fd, audit_notes="test message", audit_time=self.audit_time,
                person=self.persons.dc, status=const.STATUS_DD_NU, rt_ticket=123)
        self.check_op(o, check_contents)

    def test_emeritus(self):
        op = ops.ChangeStatus(
                audit_author=self.persons.fd, audit_notes="test emeritus", audit_time=self.audit_time,
                person=self.persons.dd_u, status=const.STATUS_EMERITUS_DD, rt_ticket=111)
        op.execute()

        person = self.persons.dd_u
        person.refresh_from_db()

        self.assertEqual(person.status, const.STATUS_EMERITUS_DD)
        self.assertEqual(person.status_changed, self.audit_time)

        from process.models import Process

        process = Process.objects.get(person=person)
        self.assertEqual(process.applying_for, const.STATUS_EMERITUS_DD)
        self.assertEqual(process.frozen_by, self.persons.fd)
        self.assertEqual(process.frozen_time, self.audit_time)
        self.assertEqual(process.approved_by, self.persons.fd)
        self.assertEqual(process.approved_time, self.audit_time)
        self.assertEqual(process.rt_ticket, 111)
        self.assertEqual(process.closed_by, self.persons.fd)
        self.assertEqual(process.closed_time, self.audit_time)
        self.assertFalse(process.requirements.exists())

        log = process.log.get()
        self.assertEqual(log.changed_by, self.persons.fd)
        self.assertEqual(log.logtext, "test emeritus")
        self.assertFalse(log.is_public)
        self.assertEqual(log.action, "proc_approve")
        self.assertEqual(log.logdate, self.audit_time)


class TestOps(PersonFixtureMixin, TestCase):
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
