# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin, ExpectedSets, TestSet, PageElements
import process.models as pmodels
from mock import patch
import tempfile
import mailbox
from .common import ProcessFixtureMixin
from .common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text, test_fpr1_signed_valid_text_nonascii,
                     test_fingerprint2, test_fpr2_signed_valid_text)

class TestDownloadStatements(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestDownloadStatements, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.amassignments.create("am", process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons["fd"], assigned_time=now())

        cls.visitor = cls.persons.dc

        cls.fingerprints.create("app", person=cls.persons.app, fpr=test_fingerprint1, is_active=True, audit_skip=True)
        cls.fingerprints.create("dd_nu", person=cls.persons.dd_nu, fpr=test_fingerprint2, is_active=True, audit_skip=True)

        cls.statements.create("intent", requirement=cls.processes.app.requirements.get(type="intent"), fpr=cls.fingerprints.app, statement=test_fpr1_signed_valid_text, uploaded_by=cls.persons.app, uploaded_time=now())
        cls.statements.create("sc_dmup", requirement=cls.processes.app.requirements.get(type="sc_dmup"), fpr=cls.fingerprints.app, statement=test_fpr1_signed_valid_text_nonascii, uploaded_by=cls.persons.app, uploaded_time=now())
        cls.statements.create("advocate", requirement=cls.processes.app.requirements.get(type="advocate"), fpr=cls.fingerprints.dd_nu, statement=test_fpr2_signed_valid_text, uploaded_by=cls.persons.dd_nu, uploaded_time=now())

    def test_backend(self):
        mbox_data = self.processes.app.get_statements_as_mbox()
        with tempfile.NamedTemporaryFile() as tf:
            tf.write(mbox_data)
            mbox = mailbox.mbox(tf.name)
            self.assertEquals(len(mbox), 3)

    def test_download(self):
        url = reverse("process_download_statements", args=[self.processes.app.pk])
        client = self.make_test_client(self.visitor)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        with tempfile.NamedTemporaryFile() as tf:
            tf.write(response.content)
            mbox = mailbox.mbox(tf.name)
            self.assertEquals(len(mbox), 3)
