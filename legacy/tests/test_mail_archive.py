from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from django.conf import settings
from backend import const
from backend import models as bmodels
from backend.unittest import NamedObjects
import process.models as pmodels
from process.unittest import ProcessFixtureMixin
import os


class TestAMDashboard(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.add_named_objects(legacy_processes=NamedObjects(bmodels.Process))
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.legacy_processes.create("dc", person=cls.persons.dc, applying_as=cls.persons.dc.status, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_DONE, is_active=False, manager=cls.ams.am)
        cls.legacy_processes.dc.advocates.add(cls.persons.dd_nu)
        cls.mailbox_pathname = os.path.join(settings.PROCESS_MAILBOX_DIR, cls.legacy_processes.dc.archive_key) + ".mbox"
        with open(cls.mailbox_pathname, "wt") as fd:
            print("""From nobody Sun Jun 24 19:12:52 2012
From: Enrico Zini <enrico@debian.org>
Subject: Test

Test
""", file=fd)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        os.unlink(cls.mailbox_pathname)

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "dc", "dd_nu", "am", "activeam", "fd", "dam":
            cls._add_method(cls._test_success, visitor)

        for visitor in None, "pending", "dc_ga", "dm", "dm_ga", "dd_u", "dd_e", "dd_r":
            cls._add_method(cls._test_forbidden, visitor)

    def _test_success(self, visitor):
        client = self.make_test_client(visitor)

        response = client.get(reverse("legacy_download_mail_archive", kwargs={ "key": self.legacy_processes.dc.lookup_key }))
        self.assertEqual(response.status_code, 200)

        response = client.get(reverse("legacy_display_mail_archive", kwargs={ "key": self.legacy_processes.dc.lookup_key }))
        self.assertEqual(response.status_code, 200)

    def _test_forbidden(self, visitor):
        client = self.make_test_client(visitor)

        response = client.get(reverse("legacy_download_mail_archive", kwargs={ "key": self.legacy_processes.dc.lookup_key }))
        self.assertPermissionDenied(response)

        response = client.get(reverse("legacy_display_mail_archive", kwargs={ "key": self.legacy_processes.dc.lookup_key }))
        self.assertPermissionDenied(response)
