from django.test import TestCase
from django.urls import reverse
from django.core import mail
from unittest.mock import patch
from backend.unittest import PersonFixtureMixin
from backend import const
import process.models as pmodels
import process.views as pviews
from process.unittest import ProcessFixtureMixin
from process import ops as pops


class TestCancel(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.create("proc", person=cls.persons.dc, applying_for=const.STATUS_DD_U)

    def test_base_op(self):
        o = pops.ProcessCancel(audit_author=self.persons.fd, process=self.processes.proc, is_public=False, statement="test statement")
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Process canceled")
            self.assertEqual(o.process, self.processes.proc)
            self.assertEqual(o.statement, "test statement")

        o = pops.ProcessCancelEmeritus(audit_author=self.persons.fd, process=self.processes.proc, is_public=False, statement="test statement")
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Process canceled")
            self.assertEqual(o.process, self.processes.proc)
            self.assertEqual(o.statement, "test statement")

    def test_op_regular(self):
        mail.outbox = []
        o = pops.ProcessCancel(audit_author=self.persons.fd, process=self.processes.proc, is_public=True, statement="test statement")
        o.execute()

        proc = self.processes.proc
        proc.refresh_from_db()
        self.assertTrue(proc.closed)
        log = proc.log.order_by("-logdate")[0]
        self.assertEqual(log.changed_by, self.persons.fd)
        self.assertIsNone(log.requirement)
        self.assertTrue(log.is_public)
        self.assertEqual(log.action, "proc_close")
        self.assertEqual(log.logtext, "test statement")

        self.assertEqual(len(mail.outbox), 0)

    def test_op_regular_private(self):
        mail.outbox = []
        o = pops.ProcessCancel(audit_author=self.persons.fd, process=self.processes.proc, is_public=False, statement="test statement")
        o.execute()

        proc = self.processes.proc
        proc.refresh_from_db()
        self.assertTrue(proc.closed)
        log = proc.log.order_by("-logdate")[0]
        self.assertEqual(log.changed_by, self.persons.fd)
        self.assertIsNone(log.requirement)
        self.assertFalse(log.is_public)
        self.assertEqual(log.action, "proc_close")
        self.assertEqual(log.logtext, "test statement")

        self.assertEqual(len(mail.outbox), 0)

    def test_op_emeritus(self):
        self.processes.proc.applying_for = const.STATUS_EMERITUS_DD
        self.processes.proc.save()

        mail.outbox = []
        o = pops.ProcessCancelEmeritus(audit_author=self.persons.fd, process=self.processes.proc, is_public=True, statement="test statement")
        o.execute()

        proc = self.processes.proc
        proc.refresh_from_db()
        self.assertTrue(proc.closed)
        log = proc.log.order_by("-logdate")[0]
        self.assertEqual(log.changed_by, self.persons.fd)
        self.assertIsNone(log.requirement)
        self.assertTrue(log.is_public)
        self.assertEqual(log.action, "proc_close")
        self.assertEqual(log.logtext, "test statement")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["nm@debian.org"])
        self.assertCountEqual(mail.outbox[0].cc, ["{} <{}>".format(proc.person.fullname, proc.person.email), proc.archive_email])
        self.assertCountEqual(mail.outbox[0].bcc, ["mia-{}@qa.debian.org".format(proc.person.uid)])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "in, ok; still active via nm.d.o")

    def test_op_emeritus_private(self):
        self.processes.proc.applying_for = const.STATUS_EMERITUS_DD
        self.processes.proc.save()

        mail.outbox = []
        o = pops.ProcessCancelEmeritus(audit_author=self.persons.fd, process=self.processes.proc, is_public=False, statement="test statement")
        o.execute()

        proc = self.processes.proc
        proc.refresh_from_db()
        self.assertTrue(proc.closed)
        log = proc.log.order_by("-logdate")[0]
        self.assertEqual(log.changed_by, self.persons.fd)
        self.assertIsNone(log.requirement)
        self.assertFalse(log.is_public)
        self.assertEqual(log.action, "proc_close")
        self.assertEqual(log.logtext, "test statement")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["nm@debian.org"])
        self.assertCountEqual(mail.outbox[0].cc, ["{} <{}>".format(proc.person.fullname, proc.person.email), proc.archive_email])
        self.assertCountEqual(mail.outbox[0].bcc, ["mia-{}@qa.debian.org".format(proc.person.uid)])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "in, ok; still active via nm.d.o")

    def test_anonymous(self):
        client = self.make_test_client(None)
        with self.collect_operations() as ops:
            response = client.get(reverse("process_cancel", args=[self.processes.proc.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, '<form id="cancel"')

            response = client.post(reverse("process_cancel", args=[self.processes.proc.pk]), data={
                "statement": "test statement",
                "is_public": True,
            })
            self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)

    def test_no_proc_close(self):
        client = self.make_test_client(self.persons.dc)
        with self.collect_operations() as ops:
            with patch.object(pmodels.Process, "permissions_of", return_value=set()):
                response = client.get(reverse("process_cancel", args=[self.processes.proc.pk]))
                self.assertPermissionDenied(response)

                response = client.post(reverse("process_cancel", args=[self.processes.proc.pk]), data={
                    "statement": "test statement",
                    "is_public": True,
                })
                self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)

    def test_proc_close(self):
        client = self.make_test_client(self.persons.dc)
        with self.collect_operations() as ops:
            with patch.object(pmodels.Process, "permissions_of", return_value=set(["proc_close"])):
                response = client.get(reverse("process_cancel", args=[self.processes.proc.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '<form id="cancel"')

                response = client.post(reverse("process_cancel", args=[self.processes.proc.pk]), data={
                    "statement": "test statement",
                    "is_public": True,
                })
                self.assertRedirectMatches(response, self.processes.proc.get_absolute_url())

        self.assertEqual(len(ops), 1)
        op = ops[0]
        self.assertIsInstance(op, pops.ProcessCancel)
        self.assertEqual(op.process, self.processes.proc)
        self.assertEqual(op.is_public, True)
        self.assertEqual(op.statement, "test statement")

    def test_proc_close_emeritus(self):
        self.processes.proc.applying_for = const.STATUS_EMERITUS_DD
        self.processes.proc.save()

        client = self.make_test_client(self.persons.dc)
        with self.collect_operations() as ops:
            with patch.object(pmodels.Process, "permissions_of", return_value=set(["proc_close"])):
                response = client.get(reverse("process_cancel", args=[self.processes.proc.pk]))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, '<form id="cancel"')

                response = client.post(reverse("process_cancel", args=[self.processes.proc.pk]), data={
                    "statement": "test statement",
                    "is_public": False,
                })
                self.assertRedirectMatches(response, self.processes.proc.get_absolute_url())

        self.assertEqual(len(ops), 1)
        op = ops[0]
        self.assertIsInstance(op, pops.ProcessCancelEmeritus)
        self.assertEqual(op.process, self.processes.proc)
        self.assertEqual(op.is_public, False)
        self.assertEqual(op.statement, "test statement")
