from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin
import process.models as pmodels
from unittest.mock import patch
from .common import ProcessFixtureMixin


class TestProcessAMAssign(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessAMAssign, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)

        cls.visitor = cls.persons.dc

    def test_success(self):
        with patch.object(pmodels.Requirement, "permissions_of", return_value={"am_assign"}):
            client = self.make_test_client(self.visitor)
            response = client.get(reverse("process_assign_am", args=[self.processes.app.pk]))
            self.assertEqual(response.status_code, 200)
            self.processes.app.refresh_from_db()
            self.assertIsNone(self.processes.app.current_am_assignment)

            response = client.post(reverse("process_assign_am", args=[self.processes.app.pk]), data={"am": self.persons.am.lookup_key})
            self.assertRedirectMatches(response, reverse("process_req_am_ok", args=[self.processes.app.pk]))
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

            from django.core import mail
            self.assertEqual(len(mail.outbox), 1)
            self.assertEqual(mail.outbox[0].cc, [self.processes.app.archive_email])
            self.assertEqual(mail.outbox[0].subject, "New Member process, Debian Developer, uploading")

    def test_forbidden(self):
        with patch.object(pmodels.Requirement, "permissions_of", return_value=set()):
            client = self.make_test_client(self.visitor)
            response = client.get(reverse("process_assign_am", args=[self.processes.app.pk]))
            self.assertPermissionDenied(response)
            self.processes.app.refresh_from_db()
            self.assertIsNone(self.processes.app.current_am_assignment)

            response = client.post(reverse("process_assign_am", args=[self.processes.app.pk]), data={"am": self.persons.am.lookup_key})
            self.assertPermissionDenied(response)
            self.processes.app.refresh_from_db()
            self.assertIsNone(self.processes.app.current_am_assignment)


class TestProcessAMUnassign(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessAMUnassign, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.amassignments.create("am", process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons["fd"], assigned_time=now())

        cls.visitor = cls.persons.dc

    def test_success(self):
        with patch.object(pmodels.Requirement, "permissions_of", return_value={"am_unassign"}):
            client = self.make_test_client(self.visitor)
            response = client.post(reverse("process_unassign_am", args=[self.processes.app.pk]))
            self.assertRedirectMatches(response, reverse("process_req_am_ok", args=[self.processes.app.pk]))
            self.processes.app.refresh_from_db()
            self.assertIsNone(self.processes.app.current_am_assignment)
            assignment = self.amassignments.am
            assignment.refresh_from_db()
            self.assertEqual(assignment.process, self.processes.app)
            self.assertEqual(assignment.am, self.ams.am)
            self.assertEqual(assignment.paused, False)
            self.assertEqual(assignment.assigned_by, self.persons.fd)
            self.assertIsNotNone(assignment.assigned_time)
            self.assertEqual(assignment.unassigned_by, self.visitor)
            self.assertIsNotNone(assignment.unassigned_time)

    def test_forbidden(self):
        with patch.object(pmodels.Requirement, "permissions_of", return_value=set()):
            client = self.make_test_client(self.visitor)
            response = client.post(reverse("process_unassign_am", args=[self.processes.app.pk]))
            self.assertPermissionDenied(response)
            self.processes.app.refresh_from_db()
            self.assertIsNotNone(self.processes.app.current_am_assignment)
