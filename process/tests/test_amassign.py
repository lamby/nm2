from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from django.core import mail
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin
import process.models as pmodels
from unittest.mock import patch
from process.unittest import ProcessFixtureMixin
from process import ops as pops


class TestProcessAMAssign(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessAMAssign, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)

        cls.visitor = cls.persons.dc

    def test_basic_op(self):
        o = pops.ProcessAssignAM(audit_author=self.persons.fd, process=self.processes.app, am=self.ams.activeam)
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Assigned AM activeam")
            self.assertEqual(o.process, self.processes.app)
            self.assertEqual(o.am, self.ams.activeam)

    def test_op(self):
        mail.outbox = []
        o = pops.ProcessAssignAM(audit_author=self.visitor, process=self.processes.app, am=self.ams.am)
        o.execute()

        self.processes.app.refresh_from_db()
        assignment = self.processes.app.current_am_assignment
        self.assertIsNotNone(assignment)
        self.assertEqual(assignment.process, self.processes.app)
        self.assertEqual(assignment.am, self.ams.am)
        self.assertEqual(assignment.paused, False)
        self.assertEqual(assignment.assigned_by, self.visitor)
        self.assertIsNotNone(assignment.assigned_time)
        self.assertIsNone(assignment.unassigned_by)
        self.assertIsNone(assignment.unassigned_time)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].cc, [self.processes.app.archive_email])
        self.assertEqual(mail.outbox[0].subject, "New Member process, Debian Developer, uploading")

    def test_success(self):
        client = self.make_test_client(self.visitor)
        with patch.object(pmodels.Requirement, "permissions_of", return_value={"am_assign"}):
            with self.collect_operations() as ops:
                response = client.get(reverse("process_assign_am", args=[self.processes.app.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(ops), 0)

            with self.collect_operations() as ops:
                response = client.post(reverse("process_assign_am", args=[self.processes.app.pk]), data={"am": self.persons.am.lookup_key})
                self.assertRedirectMatches(response, reverse("process_req_am_ok", args=[self.processes.app.pk]))
                self.assertEqual(len(ops), 1)

            op = ops[0]
            self.assertEqual(op.audit_author, self.visitor)
            self.assertEqual(op.audit_notes, "Assigned AM am")
            self.assertEqual(op.process, self.processes.app)
            self.assertEqual(op.am, self.ams.am)
            
    def test_forbidden(self):
        client = self.make_test_client(self.visitor)
        with patch.object(pmodels.Requirement, "permissions_of", return_value=set()):
            with self.collect_operations() as ops:
                response = client.get(reverse("process_assign_am", args=[self.processes.app.pk]))
                self.assertPermissionDenied(response)
                self.assertEqual(len(ops), 0)

            with self.collect_operations() as ops:
                response = client.post(reverse("process_assign_am", args=[self.processes.app.pk]), data={"am": self.persons.am.lookup_key})
                self.assertPermissionDenied(response)
                self.assertEqual(len(ops), 0)


class TestProcessAMUnassign(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessAMUnassign, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.amassignments.create("am", process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons.fd, assigned_time=now())

        cls.visitor = cls.persons.dc

    def test_basic_op(self):
        o = pops.ProcessUnassignAM(audit_author=self.persons.fd, assignment=self.amassignments.am)
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Unassigned AM am")
            self.assertEqual(o.assignment, self.amassignments.am)

    def test_op(self):
        mail.outbox = []
        o = pops.ProcessUnassignAM(audit_author=self.persons.fd, assignment=self.amassignments.am)
        o.execute()
        self.processes.app.refresh_from_db()
        self.assertIsNone(self.processes.app.current_am_assignment)
        assignment = self.amassignments.am
        assignment.refresh_from_db()
        self.assertEqual(assignment.process, self.processes.app)
        self.assertEqual(assignment.am, self.ams.am)
        self.assertEqual(assignment.paused, False)
        self.assertEqual(assignment.assigned_by, self.persons.fd)
        self.assertIsNotNone(assignment.assigned_time)
        self.assertEqual(assignment.unassigned_by, self.persons.fd)
        self.assertEqual(assignment.unassigned_time, o.audit_time)

    def test_success(self):
        client = self.make_test_client(self.visitor)
        with patch.object(pmodels.Requirement, "permissions_of", return_value={"am_unassign"}):
            with self.collect_operations() as ops:
                response = client.post(reverse("process_unassign_am", args=[self.processes.app.pk]))
                self.assertRedirectMatches(response, reverse("process_req_am_ok", args=[self.processes.app.pk]))
                self.assertEqual(len(ops), 1)
        op = ops[0]
        self.assertIsInstance(op, pops.ProcessUnassignAM)
        self.assertEqual(op.audit_author, self.visitor)
        self.assertEqual(op.audit_notes, "Unassigned AM am")
        self.assertEqual(op.assignment, self.amassignments.am)

    def test_forbidden(self):
        client = self.make_test_client(self.visitor)
        with patch.object(pmodels.Requirement, "permissions_of", return_value=set()):
            with self.collect_operations() as ops:
                response = client.post(reverse("process_unassign_am", args=[self.processes.app.pk]))
                self.assertPermissionDenied(response)
        self.assertEqual(len(ops), 0)
