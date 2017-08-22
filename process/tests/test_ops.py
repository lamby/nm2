from django.test import TestCase
from django.utils.timezone import now
from django.core import mail
from backend import const
from backend import models as bmodels
from process import models as pmodels
from process import ops as pops
from .common import ProcessFixtureMixin
from backend.tests.test_ops import TestOpMixin
import datetime


class TestOps(ProcessFixtureMixin, TestOpMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.create("app", person=cls.persons.dc, applying_for=const.STATUS_DD_U, fd_comment="test")

    def test_process_create(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertEqual(o.person, self.persons.dm)
            self.assertEqual(o.applying_for, const.STATUS_DD_U)
            self.assertEqual(o.creator, self.persons.dm)

        o = pops.ProcessCreate(audit_author=self.persons.fd, audit_notes="test message", person=self.persons.dm, applying_for=const.STATUS_DD_U)
        self.check_op(o, check_contents)

#    def test_process_approve(self):
#        def check_contents(o):
#            self.assertEqual(o.audit_author, self.persons.fd)
#            self.assertEqual(o.audit_notes, "test message")
#            self.assertEqual(o.person, self.persons.dm)
#            self.assertEqual(o.applying_for, const.STATUS_DD_U)
#            self.assertEqual(o.creator, self.persons.dm)
#
#        o = pops.ProcessCreate(audit_author=self.persons.fd, audit_notes="test message", person=self.persons.dc, status=const.STATUS_DD_NU)
#        self.check_op(o, check_contents)

    def test_process_close(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertEqual(o.process, self.processes.app)
            self.assertIsInstance(o.logdate, datetime.datetime)

        o = pops.ProcessClose(audit_author=self.persons.fd, audit_notes="test message", process=self.processes.app)
        self.check_op(o, check_contents)


class TestProcessClose(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.now = now()

    def test_close_process_dm(self):
        self.processes.app.applying_for = const.STATUS_DM
        self.processes.app.save()
        op = pops.ProcessClose(audit_author=self.persons.dam,
                               audit_notes="audit_closed",
                               process=self.processes.app,
                               logtext="closed",
                               logdate=self.now)
        op.execute()
        self.persons.app.refresh_from_db()
        self.processes.app.refresh_from_db()
        self.assertEqual(self.persons.app.status, const.STATUS_DM)
        self.assertEqual(self.persons.app.status_changed, self.now)
        self.assertEqual(self.processes.app.closed, self.now)
        self.assertEqual(len(mail.outbox), 0)

    def test_close_process_dd_nu(self):
        self.processes.app.applying_for = const.STATUS_DD_NU
        self.processes.app.save()
        op = pops.ProcessClose(audit_author=self.persons.dam,
                               audit_notes="audit_closed",
                               process=self.processes.app,
                               logtext="closed",
                               logdate=self.now)
        op.execute()
        self.persons.app.refresh_from_db()
        self.processes.app.refresh_from_db()
        self.assertEqual(self.persons.app.status, const.STATUS_DD_NU)
        self.assertEqual(self.persons.app.status_changed, self.now)
        self.assertEqual(self.processes.app.closed, self.now)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["leader@debian.org"])

    def test_close_process_dd_u(self):
        self.processes.app.applying_for = const.STATUS_DD_U
        self.processes.app.save()
        op = pops.ProcessClose(audit_author=self.persons.dam,
                               audit_notes="audit_closed",
                               process=self.processes.app,
                               logtext="closed",
                               logdate=self.now)
        op.execute()
        self.persons.app.refresh_from_db()
        self.processes.app.refresh_from_db()
        self.assertEqual(self.persons.app.status, const.STATUS_DD_U)
        self.assertEqual(self.persons.app.status_changed, self.now)
        self.assertEqual(self.processes.app.closed, self.now)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["leader@debian.org"])
