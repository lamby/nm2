from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin, ExpectedSets, TestSet, PageElements
import process.models as pmodels
from unittest.mock import patch
import tempfile
import mailbox
import os
import shutil
import json
from .common import ProcessFixtureMixin
from .common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text, test_fpr1_signed_valid_text_nonascii,
                     test_fingerprint2, test_fpr2_signed_valid_text,
                     test_fingerprint3, test_fpr3_signed_valid_text)

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
        # Python2's mbox seems to explode on non-ascii in headers
        cls.persons.dd_nu.cn = "Ondřej"
        cls.persons.dd_nu.sn = "Nový"
        cls.persons.dd_nu.save(audit_skip=True)
        cls.statements.create("advocate", requirement=cls.processes.app.requirements.get(type="advocate"), fpr=cls.fingerprints.dd_nu, statement=test_fpr2_signed_valid_text, uploaded_by=cls.persons.dd_nu, uploaded_time=now())

    def test_backend(self):
        mbox_data = self.processes.app.get_statements_as_mbox()
        with tempfile.NamedTemporaryFile() as tf:
            tf.write(mbox_data)
            tf.flush()
            mbox = mailbox.mbox(tf.name)
            self.assertEqual(len(mbox), 3)

    def test_download(self):
        url = reverse("process_download_statements", args=[self.processes.app.pk])
        client = self.make_test_client(self.visitor)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        with tempfile.NamedTemporaryFile() as tf:
            tf.write(response.content)
            tf.flush()
            mbox = mailbox.mbox(tf.name)
            self.assertEqual(len(mbox), 3)


class TestApprovals(ProcessFixtureMixin, TestCase):
    def make_process(self, status, applying_for):
        """
        Create a process with all requirements satisfied
        """
        person = bmodels.Person.objects.create_user(username="app", cn="app", status=status, email="app@example.org", uid="app", audit_skip=True)
        bmodels.Fingerprint.objects.create(person=person, fpr=test_fingerprint1, is_active=True, audit_skip=True)
        process = pmodels.Process.objects.create(person, applying_for)
        reqs = { r.type: r for r in process.requirements.all() }
        if "intent" in reqs:
            pmodels.Statement.objects.create(
                requirement=reqs["intent"],
                fpr=person.fingerprint,
                statement=test_fpr1_signed_valid_text,
                uploaded_by=person,
                uploaded_time=now())
            reqs["intent"].approved_by = person
            reqs["intent"].approved_time = now()
            reqs["intent"].save()

        if "sc_dmup" in reqs:
            pmodels.Statement.objects.create(
                requirement=reqs["sc_dmup"],
                fpr=person.fingerprint,
                statement=test_fpr1_signed_valid_text_nonascii,
                uploaded_by=person,
                uploaded_time=now())
            reqs["sc_dmup"].approved_by = person
            reqs["sc_dmup"].approved_time = now()
            reqs["sc_dmup"].save()

        if "advocate" in reqs:
            advocate = bmodels.Person.objects.create_user(username="adv", cn="adv", status=const.STATUS_DD_NU, email="adv@example.org", uid="adv", audit_skip=True)
            bmodels.Fingerprint.objects.create(person=advocate, fpr=test_fingerprint2, is_active=True, audit_skip=True)
            pmodels.Statement.objects.create(
                requirement=reqs["advocate"],
                fpr=advocate.fingerprint,
                statement=test_fpr2_signed_valid_text,
                uploaded_by=advocate,
                uploaded_time=now())
            reqs["advocate"].approved_by = advocate
            reqs["advocate"].approved_time = now()
            reqs["advocate"].save()

        if "am_ok" in reqs:
            am = bmodels.Person.objects.create_user(username="am", cn="am", status=const.STATUS_DD_NU, email="am@example.org", uid="am", audit_skip=True)
            bmodels.Fingerprint.objects.create(person=am, fpr=test_fingerprint3, is_active=True, audit_skip=True)
            pmodels.Statement.objects.create(
                requirement=reqs["am_ok"],
                fpr=am.fingerprint,
                statement=test_fpr3_signed_valid_text,
                uploaded_by=am,
                uploaded_time=now())
            reqs["am_ok"].approved_by = am
            reqs["am_ok"].approved_time = now()
            reqs["am_ok"].save()

        process.frozen_by = self.persons.dam
        process.frozen_time = now()
        process.save()

        return process

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in "fd", "dam":
            cls._add_method(cls._test_success, visitor, const.STATUS_DC, const.STATUS_DC_GA)
            cls._add_method(cls._test_success, visitor, const.STATUS_DC, const.STATUS_DM)
            cls._add_method(cls._test_success, visitor, const.STATUS_DC_GA, const.STATUS_DM_GA)
            cls._add_method(cls._test_success, visitor, const.STATUS_DM, const.STATUS_DM_GA)

        cls._add_method(cls._test_success, "dam", const.STATUS_DC, const.STATUS_DD_NU)
        cls._add_method(cls._test_success, "dam", const.STATUS_DC, const.STATUS_DD_U)
        cls._add_method(cls._test_success, "dam", const.STATUS_DC_GA, const.STATUS_DD_NU)
        cls._add_method(cls._test_success, "dam", const.STATUS_DC_GA, const.STATUS_DD_U)
        cls._add_method(cls._test_success, "dam", const.STATUS_DM, const.STATUS_DD_NU)
        cls._add_method(cls._test_success, "dam", const.STATUS_DM, const.STATUS_DD_U)
        cls._add_method(cls._test_success, "dam", const.STATUS_DM_GA, const.STATUS_DD_NU)
        cls._add_method(cls._test_success, "dam", const.STATUS_DM_GA, const.STATUS_DD_U)
        cls._add_method(cls._test_success, "dam", const.STATUS_DD_NU, const.STATUS_DD_U)
        cls._add_method(cls._test_success, "dam", const.STATUS_EMERITUS_DD, const.STATUS_DD_NU)
        cls._add_method(cls._test_success, "dam", const.STATUS_EMERITUS_DD, const.STATUS_DD_U)

    def _test_success(self, visitor, current_status, new_status):
        client = self.make_test_client(visitor)
        process = self.make_process(current_status, new_status)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

        class MockPost:
            def raise_for_status(self):
                pass
            text = "RT/0.test 200 Ok\n" \
                   "\n" \
                   "# Ticket 4242 created.\n"

        with patch("requests.post") as mock_post:
            mock_post.return_value = MockPost()
            response = client.post(reverse("process_approve", args=[process.pk]), data={"signed": "signed text"})
        self.assertRedirectMatches(response, process.get_absolute_url())
        process.refresh_from_db()
        self.assertEquals(process.rt_request, "signed text")
        self.assertEquals(process.rt_ticket, 4242)
