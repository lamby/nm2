# coding: utf-8




from django.test import TestCase
from django.utils.timezone import now, utc
from django.core import mail
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin, ExpectedSets, TestSet
import process.models as pmodels
from .common import ProcessFixtureMixin
from process import maintenance
import datetime

def _ts(year=2016, month=6, day=1):
    return datetime.datetime(year, month, day, tzinfo=utc)


class TestPings(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPings, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)

    def test_just_started(self):
        self.processes.app.add_log(self.persons.fd, "created", logdate=_ts(day=2))
        self.assertEqual(len(mail.outbox), 0)

        maintenance.ping_stuck_processes(_ts(day=1), self.persons.fd, logdate=_ts(day=1))
        self.assertEqual(len(mail.outbox), 0)
        log = list(self.processes.app.log.all())
        self.assertEqual(len(log), 1)
        self.processes.app.refresh_from_db()
        self.assertIsNone(self.processes.app.closed)

        maintenance.ping_stuck_processes(_ts(day=3), self.persons.fd, logdate=_ts(day=3))
        self.assertEqual(len(mail.outbox), 1)
        log = list(self.processes.app.log.all())
        self.assertEqual(len(log), 2)
        self.processes.app.refresh_from_db()
        self.assertIsNone(self.processes.app.closed)

        maintenance.ping_stuck_processes(_ts(day=2), self.persons.fd, logdate=_ts(day=4))
        self.assertEqual(len(mail.outbox), 1)
        log = list(self.processes.app.log.all())
        self.assertEqual(len(log), 2)
        self.processes.app.refresh_from_db()
        self.assertIsNone(self.processes.app.closed)

        maintenance.ping_stuck_processes(_ts(day=4), self.persons.fd, logdate=_ts(day=5))
        self.assertEqual(len(mail.outbox), 2)
        log = list(self.processes.app.log.all())
        self.assertEqual(len(log), 3)
        self.processes.app.refresh_from_db()
        self.assertEqual(self.processes.app.closed, _ts(day=5))
