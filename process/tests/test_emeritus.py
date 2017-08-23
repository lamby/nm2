from django.test import TestCase
from django.urls import reverse
from django.core import mail
from django.utils.timezone import now
from backend.unittest import PersonFixtureMixin
from backend import const
from unittest.mock import patch
import time
import process.models as pmodels
import process.views as pviews
from process.unittest import ProcessFixtureMixin
from process import ops as pops


class TestEmeritus(ProcessFixtureMixin, TestCase):
    def test_base_op(self):
        o = pops.RequestEmeritus(audit_author=self.persons.fd, person=self.persons.dd_u, statement="test bye")
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Requested to become emeritus")
            self.assertEqual(o.person, self.persons.dd_u)
            self.assertEqual(o.statement, "test bye")

    def test_op_new_process(self):
        self._test_op_common()

    def test_op_existing_process(self):
        self.processes.create("dd_u", person=self.persons.dd_u, applying_for=const.STATUS_EMERITUS_DD, fd_comment="test")
        self._test_op_common()

    def _test_op_common(self):
        o = pops.RequestEmeritus(audit_author=self.persons.fd, person=self.persons.dd_u, statement="test bye")
        o.execute()

        # No creation of duplicate processes
        self.assertEquals(pmodels.Process.objects.filter(person=self.persons.dd_u).count(), 1)

        stm = o._statement
        req = stm.requirement
        process = req.process

        status = req.compute_status()
        self.assertTrue(status["satisfied"])
        self.assertEqual(req.statements.count(), 1)

        self.assertIsNone(stm.fpr)
        self.assertEqual(stm.statement, "test bye")
        self.assertEqual(stm.uploaded_by, self.persons.fd)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["debian-private@lists.debian.org"])
        self.assertCountEqual(mail.outbox[0].cc, ["{} <{}>".format(process.person.fullname, process.person.email), process.archive_email, "mia-{}@qa.debian.org".format(process.person.uid)])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "in, retired; emeritus via nm.d.o")
        self.assertIn(stm.statement, mail.outbox[0].body)

        # Submit again, it adds a new one
        mail.outbox = []
        o = pops.RequestEmeritus(audit_author=self.persons.fd, person=self.persons.dd_u, statement="test bye 1")
        o.execute()
        req.refresh_from_db()
        status = req.compute_status()
        self.assertTrue(status["satisfied"])
        self.assertEqual(req.statements.count(), 2)

        stm = req.statements.get(statement="test bye 1")
        self.assertIsNone(stm.fpr)
        self.assertEqual(stm.uploaded_by, self.persons.fd)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["debian-private@lists.debian.org"])
        self.assertCountEqual(mail.outbox[0].cc, ["{} <{}>".format(process.person.fullname, process.person.email), process.archive_email, "mia-{}@qa.debian.org".format(process.person.uid)])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "in, retired; emeritus via nm.d.o")
        self.assertIn(stm.statement, mail.outbox[0].body)

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "dd_nu", "dd_u", "fd", "dam":
            cls._add_method(cls._test_success, visitor)
            cls._add_method(cls._test_nonsso_success, visitor)
            cls._add_method(cls._test_blocked, visitor)
            cls._add_method(cls._test_nonsso_blocked, visitor)
            cls._add_method(cls._test_expired_token, visitor)

        for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_e", "dd_r":
            cls._add_method(cls._test_forbidden, visitor)
            cls._add_method(cls._test_nonsso_forbidden, visitor)
            cls._add_method(cls._test_expired_token, visitor)

    def _test_success(self, visitor):
        client = self.make_test_client(visitor)
        self._test_success_common(visitor, client, reverse("process_emeritus"))

    def _test_nonsso_success(self, visitor):
        url = pviews.Emeritus.get_nonauth_url(self.persons[visitor])
        client = self.make_test_client(None)
        self._test_success_common(visitor, client, url)

    def _test_success_common(self, visitor, client, url):
        visitor = self.persons[visitor]
        with self.collect_operations() as ops:
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, url)
            self.assertEqual(len(ops), 0)

            response = client.post(url, data={"statement": "test statement"})
            self.assertRedirectMatches(response, r"/process/1$")
            self.assertEqual(len(ops), 1)

        op = ops[0]
        self.assertEqual(op.audit_author, visitor)
        self.assertEqual(op.audit_notes, "Requested to become emeritus")
        self.assertEqual(op.person, visitor)
        self.assertEqual(op.statement, "test statement")

    def _test_blocked(self, visitor):
        client = self.make_test_client(visitor)
        self.processes.create("dd_u", person=self.persons[visitor], applying_for=const.STATUS_EMERITUS_DD, fd_comment="test")
        self._test_blocked_common(visitor, client, reverse("process_emeritus"))

    def _test_nonsso_blocked(self, visitor):
        url = pviews.Emeritus.get_nonauth_url(self.persons[visitor])
        client = self.make_test_client(None)
        self.processes.create("dd_u", person=self.persons[visitor], applying_for=const.STATUS_EMERITUS_DD, fd_comment="test")
        self._test_blocked_common(visitor, client, url)

    def _test_blocked_common(self, visitor, client, url):
        process = self.processes.dd_u

        # check for closed EMERITUS_DD process
        process.closed = now()
        process.save()
        self._test_blocked_request(client, url)

        # check that if the process is turned into REMOVED_DD, the visitor can
        # no longer insert statements
        process.closed = None
        process.applying_for = const.STATUS_REMOVED_DD
        process.save()
        self._test_blocked_request(client, url)

        # check for closed REMOVED_DD process
        process.closed = now()
        process.save()
        self._test_blocked_request(client, url)

    def _test_blocked_request(self, client, url):
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["expired"])
        self.assertContains(response, "expired")  # XXX
        self.assertNotContains(response, "<textarea")
        with self.collect_operations() as ops:
            response = client.post(url, data={"statement": "test statement"})
            self.assertPermissionDenied(response)
            self.assertEquals(len(ops), 0)

    def _test_forbidden(self, visitor):
        client = self.make_test_client(visitor)
        self._test_forbidden_common(visitor, client, reverse("process_emeritus"))

    def _test_nonsso_forbidden(self, visitor):
        url = pviews.Emeritus.get_nonauth_url(self.persons[visitor])
        client = self.make_test_client(None)
        self._test_forbidden_common(visitor, client, url)

    def _test_expired_token(self, visitor):
        url = pviews.Emeritus.get_nonauth_url(self.persons[visitor])
        client = self.make_test_client(None)
        expired = time.time() + 92 * 3600 * 24
        with patch('time.time', return_value=expired) as mock_time:
            assert time.time() == expired

            self._test_forbidden_common(visitor, client, url)

    def _test_forbidden_common(self, visitor, client, url):
        with self.collect_operations() as ops:
            response = client.get(url)
            self.assertPermissionDenied(response)
            response = client.post(url, data={"statement": "test statement"})
            self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)

