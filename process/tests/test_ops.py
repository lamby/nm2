# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.utils.timezone import now
from django.core import mail
from backend import const
from backend import models as bmodels
from process import models as pmodels
from process import ops as pops
from .common import ProcessFixtureMixin

class TestOps(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestOps, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.now = now()

    def test_close_process_dm(self):
        self.processes.app.applying_for = const.STATUS_DM
        self.processes.app.save()
        op = pops.CloseProcess(audit_author=self.persons.dam,
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
        op = pops.CloseProcess(audit_author=self.persons.dam,
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
        op = pops.CloseProcess(audit_author=self.persons.dam,
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
