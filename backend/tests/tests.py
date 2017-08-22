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




import django
from django.utils.timezone import utc
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
        self.fd = bmodels.Person(username="enrico@debian.org", cn="Enrico", sn="Zini", email="enrico@debian.org", uid="enrico", status=bconst.STATUS_DD_U)
        self.fd.save(audit_skip=True)

        self.fd_am = bmodels.AM(person=self.fd, slots=1, is_am=True, is_fd=True, is_dam=True)
        self.fd_am.save()

        self.adv = bmodels.Person(username="andrea@debian.org", cn="Andrea", sn="Berardi", email="andrea@debian.org", uid="andrea", status=bconst.STATUS_DD_NU)
        self.adv.save(audit_skip=True)

        self.dd = bmodels.Person(username="lesley@debian.org", cn="Lesley", sn="Leisel", email="lesley@debian.org", uid="lesley", status=bconst.STATUS_DD_U)
        self.dd.save(audit_skip=True)

        self.am = bmodels.Person(username="jane@debian.org", cn="Jane", sn="Doe", email="jane@janedoe.org", uid="jane", status=bconst.STATUS_DD_U)
        self.am.save(audit_skip=True)

        self.am_am = bmodels.AM(person=self.am, slots=1, is_am=True)
        self.am_am.save()

        self.nm = bmodels.Person(username="john-guest@users.alioth.debian.org", cn="John", sn="Smith", email="doctor@example.com", status=bconst.STATUS_DC, bio="I meet people, I do things.")
        self.nm.save(audit_skip=True)

    def make_process_dm(self, progress=bconst.PROGRESS_DONE):
        self.process_dm = bmodels.Process(person=self.nm,
                                       applying_as=bconst.STATUS_DC,
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


class FingerprintTest(TransactionTestCase):
    def test_fpr_field(self):
        from django.db import connection
        p = bmodels.Person(cn="Test", sn="Test", email="test@example.org", uid="test",
                       status=bconst.STATUS_DC)
        p.save(audit_skip=True)

        # Verify how fingerprints are stored in the DB
        cr = connection.cursor()

        # Spaces are stripped
        f = bmodels.Fingerprint.objects.create(fpr="A410 5B0A 9F84 97EC AB5F  1683 8D5B 478C F7FE 4DAA", person=p, audit_skip=True)
        db_fpr = cr.execute("select fpr from fingerprints where id='{}'".format(f.id)).fetchone()[0]
        self.assertEqual(db_fpr, "A4105B0A9F8497ECAB5F16838D5B478CF7FE4DAA")

        # Letters are uppercased
        f = bmodels.Fingerprint.objects.create(fpr="a410 5b0a 9f84 97ec ab5f1683 8d5b 478c f7fe 4dab", person=p, audit_skip=True)
        on_db_valid_fpr = cr.execute("select fpr from fingerprints where id='{}'".format(f.id)).fetchone()[0]
        self.assertEqual(on_db_valid_fpr, "A4105B0A9F8497ECAB5F16838D5B478CF7FE4DAB")

        # Everything else is discarded
        with self.assertRaises(django.db.IntegrityError):
            bmodels.Fingerprint.objects.create(fpr="FIXME: I'll let you know later when I'll have a bit of a clue", person=p, audit_skip=True)

        with self.assertRaises(django.db.IntegrityError):
            bmodels.Fingerprint.objects.create(fpr="", audit_skip=True)


class PersonExpires(TransactionTestCase):
    def setUp(self):
        self.person = bmodels.Person(cn="Enrico", sn="Zini", email="enrico@debian.org", uid="enrico", status=bconst.STATUS_DC)
        self.person.save(audit_skip=True)

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
        self.person.save(audit_skip=True)
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertEqual(p.expires, today)

        self.person.expires = today + datetime.timedelta(days=1)
        self.person.save(audit_skip=True)
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertEqual(p.expires, today + datetime.timedelta(days=1))

        # if expires is older than today and Person is DC and there are no
        # processes, it expires
        self.person.expires = today - datetime.timedelta(days=1)
        self.person.save(audit_skip=True)
        p = run_maint()
        self.assertIsNone(p)

        # if expires is older than today and Person is not DC, then it does not
        # expire, and its 'expires' date is reset
        self.person.status = bconst.STATUS_DC_GA
        self.person.save(audit_skip=True)
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertIsNone(p.expires)

        # if expires is older than today and Person has open processes, then it
        # does not expire, and its 'expires' date is reset
        self.person.status = bconst.STATUS_DC
        self.person.save(audit_skip=True)
        proc = bmodels.Process(person=self.person,
                applying_as=self.person.status, applying_for=bconst.STATUS_DC_GA,
                progress=bconst.PROGRESS_APP_NEW, is_active=True)
        proc.save()
        p = run_maint()
        self.assertIsNotNone(p)
        self.assertIsNone(p.expires)
