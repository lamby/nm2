"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.test import TransactionTestCase
import backend.models as bmodels
import backend.const as bconst
import datetime

def dump_message(msg):
    import sys
    print >>sys.stderr, "FROM", msg.from_email
    print >>sys.stderr, "TO", msg.to
    print >>sys.stderr, "CC", msg.cc
    print >>sys.stderr, "BCC", msg.bcc
    print >>sys.stderr, "SUBJ", msg.subject
    print >>sys.stderr, "BODY", msg.body

class SimpleFixture(object):
    def __init__(self):
        self.fd = bmodels.Person(cn="Enrico", sn="Zini", email="enrico@debian.org", uid="enrico", status=bconst.STATUS_DD_U)
        self.fd.save()

        self.fd_am = bmodels.AM(person=self.fd, slots=1, is_am=True, is_fd=True, is_dam=True)
        self.fd_am.save()

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

    def make_process_dd(self, progress=bconst.PROGRESS_DONE):
        self.process_dd = bmodels.Process(person=self.nm,
                                       applying_as=bconst.STATUS_DM,
                                       applying_for=bconst.STATUS_DD_U,
                                       progress=progress,
                                       manager=self.am_am,
                                       is_active=progress==bconst.PROGRESS_DONE)
        self.process_dd.save()


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
        self.assertEqual(mail.outbox[0].from_email, 'Enrico Zini <enrico@debian.org>')
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
        self.assertEqual(mail.outbox[0].from_email, 'Enrico Zini <enrico@debian.org>')
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
        self.assertEqual(mail.outbox[0].from_email, 'Jane Doe <jane@debian.org>')
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
        self.assertEqual(mail.outbox[0].from_email, 'Enrico Zini <enrico@debian.org>')
        self.assertEqual(mail.outbox[0].to, ['John Smith <doctor@example.com>'])
        self.assertEqual(mail.outbox[0].cc, ['nm@debian.org', 'archive-doctor=example.com@nm.debian.org'])
