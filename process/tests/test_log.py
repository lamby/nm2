# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.timezone import now, utc
from django.core import mail
from backend import const
from mock import patch
from .common import ProcessFixtureMixin, get_all_process_types
import process.models as pmodels
import datetime
import uuid

mock_ts = datetime.datetime(2016, 1, 1, 0, 0, 0, tzinfo=utc)

class TestLog(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestLog, cls).setUpClass()
        cls.orig_ts = datetime.datetime(2015, 1, 1, 0, 0, 0, tzinfo=utc)

        # Create a process with an AM
        cls.persons.create("app", status=const.STATUS_DM)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U)
        cls.req_intent = pmodels.Requirement.objects.get(process=cls.processes.app, type="intent")
        cls.persons.create("am", status="dd_nu")
        cls.ams.create("am", person=cls.persons.am)
        cls.req_am_ok = pmodels.Requirement.objects.get(process=cls.processes.app, type="am_ok")

        cls.processes.app.frozen_by = cls.persons.fd
        cls.processes.app.frozen_time = cls.orig_ts
        cls.processes.app.approved_by = cls.persons.fd
        cls.processes.app.approved_time = cls.orig_ts
        cls.processes.app.closed = cls.orig_ts
        cls.processes.app.save()

        cls.req_intent.approved_by = cls.persons.fd
        cls.req_intent.approved_time = cls.orig_ts
        cls.req_intent.save()
        cls.req_am_ok.approved_by = cls.persons.fd
        cls.req_am_ok.approved_time = cls.orig_ts
        cls.req_am_ok.save()

        cls.url = reverse("process_add_log", args=[cls.processes.app.pk])

        cls.visitor = cls.persons.dc

    def get_new_log(self, process, logtext):
        entry = pmodels.Log.objects.get(process=process, logtext=logtext)
        self.assertEqual(entry.changed_by, self.visitor)
        self.assertEqual(entry.process, self.processes.app)
        return entry

    def assertProcUnchanged(self):
        self.processes.app.refresh_from_db()
        self.assertEqual(self.processes.app.frozen_by, self.persons.fd)
        self.assertEqual(self.processes.app.frozen_time, self.orig_ts)
        self.assertEqual(self.processes.app.approved_by, self.persons.fd)
        self.assertEqual(self.processes.app.approved_time, self.orig_ts)
        self.assertEqual(self.processes.app.closed, self.orig_ts)

    def assertIntentUnchanged(self):
        self.req_intent.refresh_from_db()
        self.assertEqual(self.req_intent.approved_by, self.persons.fd)
        self.assertEqual(self.req_intent.approved_time, self.orig_ts)

    def assertAmOkUnchanged(self):
        self.req_am_ok.refresh_from_db()
        self.assertEqual(self.req_am_ok.approved_by, self.persons.fd)
        self.assertEqual(self.req_am_ok.approved_time, self.orig_ts)

    def assertFailed(self, response, logtext):
        self.assertPermissionDenied(response)
        self.assertFalse(pmodels.Log.objects.filter(process=self.processes.app, logtext=logtext).exists())
        self.assertProcUnchanged()
        self.assertIntentUnchanged()
        self.assertAmOkUnchanged()

    def test_process_log_private(self):
        client = self.make_test_client(self.visitor)
        logtext = uuid.uuid4().hex

        with patch.object(pmodels.Process, "permissions_of", return_value=set()):
            response = client.post(self.url, data={"logtext": logtext, "add_action": "log_private"})
            self.assertFailed(response, logtext)
            self.assertEqual(len(mail.outbox), 0)

        with patch.object(pmodels.Process, "permissions_of", return_value=set(["add_log"])):
            response = client.post(self.url, data={"logtext": logtext, "add_action": "log_private"})
            self.assertRedirectMatches(response, self.processes.app.get_absolute_url())
            entry = self.get_new_log(self.processes.app, logtext)
            self.assertIsNone(entry.requirement)
            self.assertFalse(entry.is_public)
            self.assertEqual(entry.action, "")
            self.assertProcUnchanged()
            self.assertIntentUnchanged()
            self.assertAmOkUnchanged()
            self.assertEqual(len(mail.outbox), 1)

    def test_process_log_public(self):
        client = self.make_test_client(self.visitor)
        logtext = uuid.uuid4().hex

        with patch.object(pmodels.Process, "permissions_of", return_value=set()):
            response = client.post(self.url, data={"logtext": logtext, "add_action": "log_public"})
            self.assertFailed(response, logtext)
            self.assertEqual(len(mail.outbox), 0)

        with patch.object(pmodels.Process, "permissions_of", return_value=set(["add_log"])):
            response = client.post(self.url, data={"logtext": logtext, "add_action": "log_public"})
            self.assertRedirectMatches(response, self.processes.app.get_absolute_url())
            entry = self.get_new_log(self.processes.app, logtext)
            self.assertIsNone(entry.requirement)
            self.assertTrue(entry.is_public)
            self.assertEqual(entry.action, "")
            self.assertProcUnchanged()
            self.assertIntentUnchanged()
            self.assertAmOkUnchanged()
            self.assertEqual(len(mail.outbox), 1)

    def test_process_proc_freeze(self):
        with patch("process.views.now") as mock_now:
            mock_now.return_value = mock_ts
            client = self.make_test_client(self.visitor)
            logtext = uuid.uuid4().hex

            with patch.object(pmodels.Process, "permissions_of", return_value=set()):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "proc_freeze"})
                self.assertFailed(response, logtext)
                self.assertEqual(len(mail.outbox), 0)

            with patch.object(pmodels.Process, "permissions_of", return_value=set(["proc_freeze"])):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "proc_freeze"})
                self.assertRedirectMatches(response, self.processes.app.get_absolute_url())
                entry = self.get_new_log(self.processes.app, logtext)
                self.assertIsNone(entry.requirement)
                self.assertTrue(entry.is_public)
                self.assertEqual(entry.action, "proc_freeze")
                self.processes.app.refresh_from_db()
                self.assertEqual(self.processes.app.frozen_by, self.visitor)
                self.assertEqual(self.processes.app.frozen_time, mock_ts)
                self.assertEqual(self.processes.app.approved_by, self.persons.fd)
                self.assertEqual(self.processes.app.approved_time, self.orig_ts)
                self.assertEqual(self.processes.app.closed, self.orig_ts)
                self.assertIntentUnchanged()
                self.assertAmOkUnchanged()
                self.assertEqual(len(mail.outbox), 0)

    def test_process_proc_unfreeze(self):
        with patch("process.views.now") as mock_now:
            mock_now.return_value = mock_ts
            client = self.make_test_client(self.visitor)
            logtext = uuid.uuid4().hex

            with patch.object(pmodels.Process, "permissions_of", return_value=set()):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "proc_unfreeze"})
                self.assertFailed(response, logtext)
                self.assertEqual(len(mail.outbox), 0)

            with patch.object(pmodels.Process, "permissions_of", return_value=set(["proc_unfreeze"])):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "proc_unfreeze"})
                self.assertRedirectMatches(response, self.processes.app.get_absolute_url())
                entry = self.get_new_log(self.processes.app, logtext)
                self.assertIsNone(entry.requirement)
                self.assertTrue(entry.is_public)
                self.assertEqual(entry.action, "proc_unfreeze")
                self.processes.app.refresh_from_db()
                self.assertIsNone(self.processes.app.frozen_by)
                self.assertIsNone(self.processes.app.frozen_time)
                self.assertEqual(self.processes.app.approved_by, self.persons.fd)
                self.assertEqual(self.processes.app.approved_time, self.orig_ts)
                self.assertEqual(self.processes.app.closed, self.orig_ts)
                self.assertIntentUnchanged()
                self.assertAmOkUnchanged()
                self.assertEqual(len(mail.outbox), 0)

    def test_process_proc_approve(self):
        with patch("process.views.now") as mock_now:
            mock_now.return_value = mock_ts
            client = self.make_test_client(self.visitor)
            logtext = uuid.uuid4().hex

            with patch.object(pmodels.Process, "permissions_of", return_value=set()):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "proc_approve"})
                self.assertFailed(response, logtext)
                self.assertEqual(len(mail.outbox), 0)

            with patch.object(pmodels.Process, "permissions_of", return_value=set(["proc_approve"])):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "proc_approve"})
                self.assertRedirectMatches(response, self.processes.app.get_absolute_url())
                entry = self.get_new_log(self.processes.app, logtext)
                self.assertIsNone(entry.requirement)
                self.assertTrue(entry.is_public)
                self.assertEqual(entry.action, "proc_approve")
                self.processes.app.refresh_from_db()
                self.assertEqual(self.processes.app.frozen_by, self.persons.fd)
                self.assertEqual(self.processes.app.frozen_time, self.orig_ts)
                self.assertEqual(self.processes.app.approved_by, self.visitor)
                self.assertEqual(self.processes.app.approved_time, mock_ts)
                self.assertEqual(self.processes.app.closed, self.orig_ts)
                self.assertIntentUnchanged()
                self.assertAmOkUnchanged()
                self.assertEqual(len(mail.outbox), 0)

    def test_process_proc_unapprove(self):
        with patch("process.views.now") as mock_now:
            mock_now.return_value = mock_ts
            client = self.make_test_client(self.visitor)
            logtext = uuid.uuid4().hex

            with patch.object(pmodels.Process, "permissions_of", return_value=set()):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "proc_unapprove"})
                self.assertFailed(response, logtext)
                self.assertEqual(len(mail.outbox), 0)

            with patch.object(pmodels.Process, "permissions_of", return_value=set(["proc_unapprove"])):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "proc_unapprove"})
                self.assertRedirectMatches(response, self.processes.app.get_absolute_url())
                entry = self.get_new_log(self.processes.app, logtext)
                self.assertIsNone(entry.requirement)
                self.assertTrue(entry.is_public)
                self.assertEqual(entry.action, "proc_unapprove")
                self.processes.app.refresh_from_db()
                self.assertEqual(self.processes.app.frozen_by, self.persons.fd)
                self.assertEqual(self.processes.app.frozen_time, self.orig_ts)
                self.assertIsNone(self.processes.app.approved_by)
                self.assertIsNone(self.processes.app.approved_time)
                self.assertEqual(self.processes.app.closed, self.orig_ts)
                self.assertIntentUnchanged()
                self.assertAmOkUnchanged()
                self.assertEqual(len(mail.outbox), 0)

    def test_process_req_approve(self):
        with patch("process.views.now") as mock_now:
            mock_now.return_value = mock_ts
            client = self.make_test_client(self.visitor)
            logtext = uuid.uuid4().hex

            with patch.object(pmodels.Requirement, "permissions_of", return_value=set()):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "req_approve", "req_type": "intent"})
                self.assertFailed(response, logtext)
                self.assertEqual(len(mail.outbox), 0)

            with patch.object(pmodels.Requirement, "permissions_of", return_value=set(["req_approve"])):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "req_approve", "req_type": "intent"})
                self.assertRedirectMatches(response, self.req_intent.get_absolute_url())
                entry = self.get_new_log(self.processes.app, logtext)
                self.assertEqual(entry.requirement, self.req_intent)
                self.assertTrue(entry.is_public)
                self.assertEqual(entry.action, "req_approve")
                self.processes.app.refresh_from_db()
                self.assertProcUnchanged()
                self.req_intent.refresh_from_db()
                self.assertEqual(self.req_intent.approved_by, self.visitor)
                self.assertEqual(self.req_intent.approved_time, mock_ts)
                self.assertAmOkUnchanged()
                self.assertEqual(len(mail.outbox), 0)

    def test_process_req_unapprove(self):
        with patch("process.views.now") as mock_now:
            mock_now.return_value = mock_ts
            client = self.make_test_client(self.visitor)
            logtext = uuid.uuid4().hex

            with patch.object(pmodels.Requirement, "permissions_of", return_value=set()):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "req_unapprove", "req_type": "intent"})
                self.assertFailed(response, logtext)
                self.assertEqual(len(mail.outbox), 0)

            with patch.object(pmodels.Requirement, "permissions_of", return_value=set(["req_unapprove"])):
                response = client.post(self.url, data={"logtext": logtext, "add_action": "req_unapprove", "req_type": "intent"})
                self.assertRedirectMatches(response, self.processes.app.get_absolute_url())
                entry = self.get_new_log(self.processes.app, logtext)
                self.assertEqual(entry.requirement, self.req_intent)
                self.assertTrue(entry.is_public)
                self.assertEqual(entry.action, "req_unapprove")
                self.processes.app.refresh_from_db()
                self.assertProcUnchanged()
                self.req_intent.refresh_from_db()
                self.assertIsNone(self.req_intent.approved_by)
                self.assertIsNone(self.req_intent.approved_time)
                self.assertAmOkUnchanged()
                self.assertEqual(len(mail.outbox), 0)
