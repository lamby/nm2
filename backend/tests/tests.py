# coding: utf-8
# nm.debian.org website backend
#
# Copyright (C) 2012--2014  Enrico Zini <enrico@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TransactionTestCase
import backend.models as bmodels
import backend.const as bconst
import datetime

def dump_message(msg):
    import sys
    print("FROM", msg.from_email, file=sys.stderr)
    print("TO", msg.to, file=sys.stderr)
    print("CC", msg.cc, file=sys.stderr)
    print("BCC", msg.bcc, file=sys.stderr)
    print("SUBJ", msg.subject, file=sys.stderr)
    print("BODY", msg.body, file=sys.stderr)

class SimpleFixture(object):
    def __init__(self):
        self.fd = bmodels.Person(cn="Enrico", sn="Zini", email="enrico@debian.org", uid="enrico", status=bconst.STATUS_DD_U)
        self.fd.save()

        self.fd_am = bmodels.AM(person=self.fd, slots=1, is_am=True, is_fd=True, is_dam=True)
        self.fd_am.save()

        self.adv = bmodels.Person(cn="Andrea", sn="Berardi", email="andrea@debian.org", uid="andrea", status=bconst.STATUS_DD_NU)
        self.adv.save()

        self.dd = bmodels.Person(cn="Lesley", sn="Leisel", email="lesley@debian.org", uid="lesley", status=bconst.STATUS_DD_U)
        self.dd.save()

        self.am = bmodels.Person(cn="Jane", sn="Doe", email="jane@janedoe.org", uid="jane", status=bconst.STATUS_DD_U)
        self.am.save()

        self.am_am = bmodels.AM(person=self.am, slots=1, is_am=True)
        self.am_am.save()

        self.nm = bmodels.Person(cn="John", sn="Smith", email="doctor@example.com", status=bconst.STATUS_MM, bio="I meet people, I do things.")
        self.nm.save()

    def make_process_dm(self, progress=bconst.PROGRESS_DONE):
        self.process_dm = bmodels.Process(person=self.nm,
                                       applying_as=bconst.STATUS_MM,
                                       applying_for=bconst.STATUS_DM,
                                       progress=progress,
                                       manager=self.am_am,
                                       is_active=progress==bconst.PROGRESS_DONE)
        self.process_dm.save()
        return self.process_dm

    def make_process_dd(self, progress=bconst.PROGRESS_DONE, advocate=None):
        self.process_dd = bmodels.Process(person=self.nm,
                                       applying_as=bconst.STATUS_DM,
                                       applying_for=bconst.STATUS_DD_U,
                                       progress=progress,
                                       manager=self.am_am,
                                       is_active=progress!=bconst.PROGRESS_DONE)
        self.process_dd.save()
        if advocate is not None:
            self.process_dd.advocates.add(advocate)
        return self.process_dd


class LogTest(TransactionTestCase):
    def setUp(self):
        self.p = SimpleFixture()
        self.p.make_process_dm()
        self.p.make_process_dd(bconst.PROGRESS_APP_OK)

    def test_log_previous(self):
        """
        Check if Log.previous works
        """
        log_dm1 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dm,
                           progress=bconst.PROGRESS_APP_NEW,
                           logdate=datetime.datetime(2013, 1, 1, 0, 0, 0),
                           logtext="process started")
        log_dm1.save()

        log_dd1 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dd,
                           progress=bconst.PROGRESS_APP_NEW,
                           logdate=datetime.datetime(2013, 1, 1, 12, 0, 0),
                           logtext="process started")
        log_dd1.save()

        log_dm2 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dm,
                           progress=bconst.PROGRESS_DONE,
                           logdate=datetime.datetime(2013, 1, 2, 0, 0, 0),
                           logtext="all ok")
        log_dm2.save()

        log_dd2 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dd,
                           progress=bconst.PROGRESS_ADV_RCVD,
                           logdate=datetime.datetime(2013, 1, 2, 12, 0, 0),
                           logtext="all ok")
        log_dd2.save()

        self.assertEquals(log_dm2.previous, log_dm1)
        self.assertEquals(log_dd2.previous, log_dd1)

        log_dd3 = bmodels.Log(changed_by=self.p.am,
                           process=self.p.process_dd,
                           progress=bconst.PROGRESS_APP_OK,
                           logdate=datetime.datetime(2013, 1, 3, 0, 0, 0),
                           logtext="advocacies are ok")
        log_dd3.save()

        self.assertEquals(log_dd3.previous, log_dd2)
        self.assertEquals(log_dd3.previous.previous, log_dd1)


class NotificationTest(TransactionTestCase):
    def setUp(self):
        self.p = SimpleFixture()

    def test_notify_am_queue(self):
        self.p.make_process_dd(bconst.PROGRESS_ADV_RCVD)

        l1 = bmodels.Log.for_process(self.p.process_dd)
        l1.changed_by = self.p.fd
        l1.logtext = "got advocates"
        l1.save()

        self.p.process_dd.progress = bconst.PROGRESS_APP_OK
        self.p.process_dd.save()

        l2 = bmodels.Log.for_process(self.p.process_dd)
        l2.changed_by = self.p.fd
        l2.logtext = "ready to get an AM"
        l2.save()

        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, 'Enrico Zini via nm <enrico@debian.org>')
        self.assertEqual(mail.outbox[0].to, ['John Smith <doctor@example.com>'])
        self.assertEqual(mail.outbox[0].cc, ['archive-doctor=example.com@nm.debian.org'])

    def test_notify_assigned(self):
        self.p.make_process_dd(bconst.PROGRESS_APP_OK)

        l1 = bmodels.Log.for_process(self.p.process_dd)
        l1.changed_by = self.p.fd
        l1.logtext = "ready to get an AM"
        l1.save()

        self.p.process_dd.progress = bconst.PROGRESS_AM_RCVD
        self.p.process_dd.save()

        l2 = bmodels.Log.for_process(self.p.process_dd)
        l2.changed_by = self.p.fd
        l2.logtext = "assigned_am"
        l2.save()

        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, 'Enrico Zini via nm <enrico@debian.org>')
        self.assertEqual(mail.outbox[0].to, ['Jane Doe <jane@debian.org>'])
        self.assertEqual(mail.outbox[0].cc, ['archive-doctor=example.com@nm.debian.org'])

    def test_notify_am_approved(self):
        self.p.make_process_dd(bconst.PROGRESS_AM)

        l1 = bmodels.Log.for_process(self.p.process_dd)
        l1.changed_by = self.p.am
        l1.logtext = "all is good so far"
        l1.save()

        self.p.process_dd.progress = bconst.PROGRESS_AM_OK
        self.p.process_dd.save()

        l2 = bmodels.Log.for_process(self.p.process_dd)
        l2.changed_by = self.p.am
        l2.logtext = "what a fantastic applicant!"
        l2.save()

        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, 'Jane Doe via nm <jane@debian.org>')
        self.assertEqual(mail.outbox[0].to, ['debian-newmaint@lists.debian.org'])
        self.assertEqual(mail.outbox[0].cc, ['John Smith <doctor@example.com>', 'nm@debian.org', 'archive-doctor=example.com@nm.debian.org'])

    def test_notify_fd_approved(self):
        self.p.make_process_dd(bconst.PROGRESS_AM_OK)

        l1 = bmodels.Log.for_process(self.p.process_dd)
        l1.changed_by = self.p.am
        l1.logtext = "what a fantastic applicant!"
        l1.save()

        self.p.process_dd.progress = bconst.PROGRESS_FD_OK
        self.p.process_dd.save()

        l2 = bmodels.Log.for_process(self.p.process_dd)
        l2.changed_by = self.p.fd
        l2.logtext = "all good, ready for DAM"
        l2.save()

        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].from_email, 'Enrico Zini via nm <enrico@debian.org>')
        self.assertEqual(mail.outbox[0].to, ['John Smith <doctor@example.com>'])
        self.assertEqual(mail.outbox[0].cc, ['nm@debian.org', 'archive-doctor=example.com@nm.debian.org'])

class SimpleFixtureFingerprintField(object):
    def __init__(self):
        bmodels.Person(cn="Marco", sn="Bardelli", email="safanaj@debian.org", uid="safanaj",
                       status=bconst.STATUS_MM_GA,
                       fpr="A410 5B0A 9F84 97EC AB5F  1683 8D5B 478C F7FE 4DAA").save()

        bmodels.Person(cn="Invalid", sn="FPR", email="invalid@debian.org", uid="invalid_fpr",
                       status=bconst.STATUS_MM,
                       fpr="FIXME: I'll let you know later when I'll have a bit of a clue").save()

        bmodels.Person(cn="Empty", sn="FPR", email="empty@debian.org", uid="empty",
                       status=bconst.STATUS_DD_NU,
                       fpr="").save()

class FingerprintTest(TransactionTestCase):
    def setUp(self):
        self.fpr = SimpleFixtureFingerprintField()

    def test_fpr_field(self):
        from django.db import connection
        cr = connection.cursor()
        on_db_valid_fpr = cr.execute("select fpr from person where uid = 'safanaj'").fetchone()[0]
        self.assertEquals(on_db_valid_fpr, "A4105B0A9F8497ECAB5F16838D5B478CF7FE4DAA")
        on_db_invalid_fpr = cr.execute("select fpr from person where uid = 'invalid_fpr'").fetchone()[0]
        self.assertEquals(on_db_invalid_fpr, "FIXME-I-ll-let-you-know-later-when-I-ll-")
        on_db_empty_fpr = cr.execute("select fpr from person where uid = 'empty'").fetchone()[0]
        self.assertIsNone(on_db_empty_fpr)

        p = bmodels.Person(cn="Invalid", sn="FPR", email="invalid1@debian.org", uid="invalid_fpr1",
                       status=bconst.STATUS_MM,
                       fpr="66B4 Invalid FPR BFAB")
        p.save()
        p1 = bmodels.Person.objects.get(uid="invalid_fpr1")
        self.assertIsNone(p1.fpr)


class PersonExpires(TransactionTestCase):
    def setUp(self):
        self.person = bmodels.Person(cn="Enrico", sn="Zini", email="enrico@debian.org", uid="enrico",
                                     status=bconst.STATUS_MM, fpr="66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB")
        self.person.save()

    def test_expires(self):
        from django_housekeeping import Housekeeping
        def run_maint():
            from backend.housekeeping import BackupDB
            hk = Housekeeping(test_mock=BackupDB)
            hk.autodiscover()
            hk.init()
            hk.run(run_filter=lambda name:"PersonExpires" in name)
            res = Person.objects.filter(pk=self.person.id)
            if res.exists():
                return res[0]
            else:
                return None
        Person = bmodels.Person
        today = datetime.date.today()

        # if expires is Null, it won't expire
        self.assertIsNone(self.person.expires)
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertIsNone(p.expires)

        # if expires is today or later, it hasn't expired yet
        self.person.expires = today
        self.person.save()
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertEquals(p.expires, today)

        self.person.expires = today + datetime.timedelta(days=1)
        self.person.save()
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertEquals(p.expires, today + datetime.timedelta(days=1))

        # if expires is older than today and Person is DC and there are no
        # processes, it expires
        self.person.expires = today - datetime.timedelta(days=1)
        self.person.save()
        p = run_maint()
        self.assertIsNone(p)

        # if expires is older than today and Person is not DC, then it does not
        # expire, and its 'expires' date is reset
        self.person.status = bconst.STATUS_MM_GA
        self.person.save()
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertIsNone(p.expires)

        # if expires is older than today and Person has open processes, then it
        # does not expire, and its 'expires' date is reset
        self.person.status = bconst.STATUS_MM
        self.person.save()
        proc = bmodels.Process(person=self.person,
                applying_as=self.person.status, applying_for=bconst.STATUS_MM_GA,
                progress=bconst.PROGRESS_APP_NEW, is_active=True)
        proc.save()
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertIsNone(p.expires)