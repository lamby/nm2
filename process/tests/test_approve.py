from django.test import TestCase
from django.utils.timezone import now
from django.urls import reverse
from django.core import mail
from unittest.mock import patch
from backend.unittest import PersonFixtureMixin
from backend import const
import process.models as pmodels
import process.views as pviews
from process.unittest import ProcessFixtureMixin
from process import ops as pops

class TestApproveOp(ProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        cls._add_method(cls._test_process_approve_dsa, "dc", const.STATUS_DC_GA)
        cls._add_method(cls._test_process_approve_dsa, "dm", const.STATUS_DM_GA)

        cls._add_method(cls._test_process_approve_fd_keyring, "dc", const.STATUS_DM)
        cls._add_method(cls._test_process_approve_dam_keyring, "dc", const.STATUS_DD_NU)
        cls._add_method(cls._test_process_approve_dam_keyring, "dc", const.STATUS_DD_U)
        cls._add_method(cls._test_process_approve_dam_keyring, "dc_ga", const.STATUS_DD_NU)
        cls._add_method(cls._test_process_approve_dam_keyring, "dc_ga", const.STATUS_DD_U)
        cls._add_method(cls._test_process_approve_dam_keyring, "dm", const.STATUS_DD_NU)
        cls._add_method(cls._test_process_approve_dam_keyring, "dm", const.STATUS_DD_U)
        cls._add_method(cls._test_process_approve_dam_keyring, "dm_ga", const.STATUS_DD_NU)
        cls._add_method(cls._test_process_approve_dam_keyring, "dm_ga", const.STATUS_DD_U)
        cls._add_method(cls._test_process_approve_dam_keyring, "dd_nu", const.STATUS_DD_U)
        cls._add_method(cls._test_process_approve_dam_keyring, "dd_nu", const.STATUS_EMERITUS_DD)
        cls._add_method(cls._test_process_approve_dam_keyring, "dd_nu", const.STATUS_REMOVED_DD)
        cls._add_method(cls._test_process_approve_dam_keyring, "dd_u", const.STATUS_EMERITUS_DD)
        cls._add_method(cls._test_process_approve_dam_keyring, "dd_u", const.STATUS_REMOVED_DD)

    def assertApproveCommon(self, o):
        self.assertEqual(o.audit_author, self.persons.fd)
        self.assertEqual(o.audit_notes, "Process approved")
        self.assertEqual(o.rt_id, "ticket/new")
        self.assertIsNone(o.rt_text)

    def _test_process_approve_dsa(self, person, applying_for):
        person = self.persons[person]
        # dc to have a guest account
        process = pmodels.Process.objects.create(person=person, applying_for=applying_for)
        o = pops.ProcessApproveRT(audit_author=self.persons.fd, process=process)
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertApproveCommon(o)
            self.assertEqual(o.process, process)
            self.assertEqual(o.rt_queue, "DSA - Incoming")
            self.assertEqual(o.rt_requestor, "da-manager@debian.org")
            self.assertEqual(o.rt_subject, "Guest account on porter machines for " + person.fullname)
            self.assertEqual(o.rt_cc, "{}, archive-{}@nm.debian.org, da-manager@debian.org".format(person.email, process.pk))

    def _test_process_approve_fd_keyring(self, person, applying_for):
        person = self.persons[person]
        # dc to have a guest account
        process = pmodels.Process.objects.create(person=person, applying_for=applying_for)
        o = pops.ProcessApproveRT(audit_author=self.persons.fd, process=process)
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertApproveCommon(o)
            self.assertEqual(o.process, process)
            self.assertEqual(o.rt_queue, "Keyring")
            self.assertEqual(o.rt_requestor, "nm@debian.org")
            self.assertEqual(o.rt_subject, person.fullname + " to become " + const.ALL_STATUS_DESCS[applying_for])
            self.assertEqual(o.rt_cc, "{}, archive-{}@nm.debian.org, nm@debian.org".format(person.email, process.pk))

    def _test_process_approve_dam_keyring(self, person, applying_for):
        person = self.persons[person]
        # dc to have a guest account
        process = pmodels.Process.objects.create(person=person, applying_for=applying_for)
        o = pops.ProcessApproveRT(audit_author=self.persons.fd, process=process)
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertApproveCommon(o)
            self.assertEqual(o.process, process)
            self.assertEqual(o.rt_queue, "Keyring")
            self.assertEqual(o.rt_requestor, "da-manager@debian.org")
            self.assertEqual(o.rt_subject, person.fullname + " to become " + const.ALL_STATUS_DESCS[applying_for])
            self.assertEqual(o.rt_cc, "{}, archive-{}@nm.debian.org, da-manager@debian.org".format(person.email, process.pk))


class TestApproveCommon(ProcessFixtureMixin):
    APPLICANT = None
    APPLYING_FOR = None

    class MockResponse:
        text = "\n".join([
            "RT/3.4.5 200 Ok",
            "",
            "# Ticket 1 created.",
        ])
        def raise_for_status(self):
            pass

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.applicant = cls.persons[cls.APPLICANT]
        cls.processes.create("proc", person=cls.applicant, applying_for=cls.APPLYING_FOR)

    def _make_op(self):
        return pops.ProcessApproveRT(
                audit_author=self.persons.fd,
                process=self.processes.proc,
                rt_id="test id",
                rt_queue="test queue",
                rt_requestor="test requestor",
                rt_subject="test subject",
                rt_cc="test cc",
                rt_text="test text")

    def _execute_op(self, o):
        with self.settings(RT_USER="rtuser", RT_PASS="rtpass"):
            with patch('requests.post') as mock_post:
                mock_post.return_value = self.MockResponse()
                o.execute()

                post_args, post_kw = mock_post.call_args
                self.assertEqual(len(post_args), 1)
                self.assertEqual(post_args[0], "https://rt.debian.org/REST/1.0/ticket/new")
                self.assertEqual(post_kw["params"], { "user": "rtuser", "pass": "rtpass" })
                content = post_kw["data"]["content"]

                self.assertEqual(content.splitlines(), [
                    "id: test id",
                    "Queue: test queue",
                    "Requestor: test requestor",
                    "Subject: test subject",
                    "Cc: test cc",
                    "Text:",
                    " test text"
                ])

        proc = self.processes.proc
        proc.refresh_from_db()
        self.assertEqual(proc.rt_ticket, 1)
        self.assertEqual(proc.rt_request, "test text")
        self.assertEqual(proc.approved_by, self.persons.fd)
        self.assertEqual(proc.approved_time, o.audit_time)

        log = proc.log.get()
        self.assertEqual(log.changed_by, self.persons.fd)
        self.assertIsNone(log.requirement)
        self.assertTrue(log.is_public)
        self.assertEqual(log.logdate, o.audit_time)
        self.assertEqual(log.action, "proc_approve")
        self.assertEqual(log.logtext, "Process approved")


class TestApprove(TestApproveCommon, TestCase):
    APPLICANT = "dc"
    APPLYING_FOR = const.STATUS_DD_U

    def test_op(self):
        mail.outbox = []

        o = self._make_op()
        self._execute_op(o)
        self.assertEqual(len(mail.outbox), 0)


class TestApproveEmeritus(TestApproveCommon, TestCase):
    APPLICANT = "dd_u"
    APPLYING_FOR = const.STATUS_EMERITUS_DD

    def test_op(self):
        mail.outbox = []

        o = self._make_op()
        self._execute_op(o)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mia-dd_u@qa.debian.org"])
        self.assertEqual(mail.outbox[0].cc, [self.processes.proc.archive_email])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "in, retired; emeritus via nm.d.o")
        self.assertIn("test text", mail.outbox[0].body)


class TestApproveRemoved(TestApproveCommon, TestCase):
    APPLICANT = "dd_u"
    APPLYING_FOR = const.STATUS_REMOVED_DD

    def test_op(self):
        mail.outbox = []

        o = self._make_op()
        self._execute_op(o)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["mia-dd_u@qa.debian.org"])
        self.assertEqual(mail.outbox[0].cc, [self.processes.proc.archive_email])
        self.assertEqual(mail.outbox[0].extra_headers["X-MIA-Summary"], "in, removed; removed via nm.d.o")
        self.assertIn("test text", mail.outbox[0].body)


class TestApprovePerms(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.create("proc", person=cls.persons.dc, applying_for=const.STATUS_DD_NU)
        cls.processes.proc.frozen_by = cls.persons.fd
        cls.processes.proc.frozen_time = now()
        cls.processes.proc.save()
        cls.url = reverse("process_approve", args=[cls.processes.proc.pk])

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "fd", "dam":
            cls._add_method(cls._test_success, visitor)

        for visitor in "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r":
            cls._add_method(cls._test_forbidden, visitor)

    def _test_success(self, visitor):
        client = self.make_test_client(visitor)

        with self.collect_operations() as ops:
            response = client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(ops), 0)

            response = client.post(self.url, data={"signed": "test statement"})
            self.assertRedirectMatches(response, self.processes.proc.get_absolute_url())
            self.assertEqual(len(ops), 1)

        op = ops[0]
        self.assertEqual(op.audit_author, client.visitor)
        self.assertEqual(op.audit_notes, "Process approved")
        self.assertEqual(op.process, self.processes.proc)
        self.assertEqual(op.rt_text, "test statement")

        with self.collect_operations() as ops:
            self.processes.proc.frozen_by = None
            self.processes.proc.frozen_time = None
            self.processes.proc.save()

            # Denied because the process is not frozen
            response = client.get(self.url)
            self.assertPermissionDenied(response)
            response = client.post(self.url, data={"signed": "test statement"})
            self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)

            self.processes.proc.frozen_by = self.persons.fd
            self.processes.proc.frozen_time = now()
            self.processes.proc.approved_by = self.persons.fd
            self.processes.proc.approved_time = now()
            self.processes.proc.save()

            # Denied because the process is already approved
            response = client.get(self.url)
            self.assertPermissionDenied(response)
            response = client.post(self.url, data={"signed": "test statement"})
            self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)


    def _test_forbidden(self, visitor):
        client = self.make_test_client(visitor)

        with self.collect_operations() as ops:
            response = client.get(self.url)
            self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)

            response = client.post(self.url, data={"signed": "test statement"})
            self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)
