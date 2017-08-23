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
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.person, self.persons.dm)
            self.assertEqual(o.applying_for, const.STATUS_DD_U)
            self.assertEqual(o.creator, self.persons.dm)

        o = pops.ProcessCreate(audit_author=self.persons.fd, audit_notes="test message", person=self.persons.dm, applying_for=const.STATUS_DD_U)
        self.check_op(o, check_contents)

    def test_log_statement_private(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test log")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.process, self.processes.app)
            self.assertIsNone(o.requirement)
            self.assertFalse(o.is_public)

        o = pops.ProcessAddLogEntry(audit_author=self.persons.fd, audit_notes="test log", process=self.processes.app, is_public=False)
        self.check_op(o, check_contents)

    def test_log_statement_public(self):
        req = self.processes.app.requirements.get(type="intent")

        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test log")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertIsNone(o.process)
            self.assertEqual(o.requirement, req)
            self.assertTrue(o.is_public)

        o = pops.ProcessAddLogEntry(audit_author=self.persons.fd, audit_notes="test log", requirement=req, is_public=True)
        self.check_op(o, check_contents)

    def test_requirement_approve(self):
        req = self.processes.app.requirements.get(type="intent")

        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test approved")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.requirement, req)

        o = pops.RequirementApprove(audit_author=self.persons.fd, audit_notes="test approved", requirement=req)
        self.check_op(o, check_contents)

    def test_requirement_unapprove(self):
        req = self.processes.app.requirements.get(type="intent")

        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test unapproved")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.requirement, req)

        o = pops.RequirementUnapprove(audit_author=self.persons.fd, audit_notes="test unapproved", requirement=req)
        self.check_op(o, check_contents)

    def test_process_freeze(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test frozen")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.process, self.processes.app)

        o = pops.ProcessFreeze(audit_author=self.persons.fd, audit_notes="test frozen", process=self.processes.app)
        self.check_op(o, check_contents)

    def test_process_unfreeze(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test unfrozen")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.process, self.processes.app)

        o = pops.ProcessUnfreeze(audit_author=self.persons.fd, audit_notes="test unfrozen", process=self.processes.app)
        self.check_op(o, check_contents)

    def test_process_approve(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test approved")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.process, self.processes.app)

        o = pops.ProcessApprove(audit_author=self.persons.fd, audit_notes="test approved", process=self.processes.app)
        self.check_op(o, check_contents)

    def test_process_unapprove(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test unapproved")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.process, self.processes.app)

        o = pops.ProcessUnapprove(audit_author=self.persons.fd, audit_notes="test unapproved", process=self.processes.app)
        self.check_op(o, check_contents)

    def test_process_close(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "test message")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.process, self.processes.app)

        o = pops.ProcessClose(audit_author=self.persons.fd, audit_notes="test message", process=self.processes.app)
        self.check_op(o, check_contents)

    def test_process_assign_am(self):
        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Assigned AM activeam")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.process, self.processes.app)
            self.assertEqual(o.am, self.ams.activeam)

        o = pops.ProcessAssignAM(audit_author=self.persons.fd, process=self.processes.app, am=self.ams.activeam)
        self.check_op(o, check_contents)

    def test_process_unassign_am(self):
        pops.ProcessAssignAM(audit_author=self.persons.fd, process=self.processes.app, am=self.ams.activeam).execute()
        assignment = self.processes.app.ams.get()

        def check_contents(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Unassigned AM activeam")
            self.assertIsInstance(o.audit_time, datetime.datetime)
            self.assertEqual(o.assignment, assignment)

        o = pops.ProcessUnassignAM(audit_author=self.persons.fd, assignment=assignment)
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
                               audit_time=self.now)
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
                               audit_time=self.now)
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
                               audit_time=self.now)
        op.execute()
        self.persons.app.refresh_from_db()
        self.processes.app.refresh_from_db()
        self.assertEqual(self.persons.app.status, const.STATUS_DD_U)
        self.assertEqual(self.persons.app.status_changed, self.now)
        self.assertEqual(self.processes.app.closed, self.now)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["leader@debian.org"])
