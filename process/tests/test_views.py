from django.test import TestCase
from django.core.urlresolvers import reverse
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


class TestEmailLookup(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEmailLookup, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")

    def test_lookup(self):
        client = self.make_test_client(self.persons.dd_nu)
        mbox_file = "test_data/process-{}.mbox".format(self.processes.app.pk)
        with self.settings(PROCESS_MAILBOX_DIR=os.path.abspath("test_data")):
            shutil.copy("test_data/debian-newmaint.mbox", mbox_file)
            try:
                response = client.post(
                    reverse("process_email_lookup", args=[self.processes.app.pk]),
                    data={"url": "https://lists.debian.org/debian-newmaint/2016/06/msg00044.html"}
                )
                self.assertEqual(response.status_code, 200)
                decoded = json.loads(response.content.decode("utf8"))
                self.assertNotIn("error", decoded)
                self.assertIn("msg", decoded)
                with open("test_data/debian-newmaint.mbox", "rt") as fd:
                    self.assertEqual(decoded["msg"].rstrip(), "".join(list(fd)[1:]).rstrip())
            finally:
                os.unlink(mbox_file)



class TestRTTicket(ProcessFixtureMixin, TestCase):
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

        process.approved_by = self.persons.dam
        process.approved_time = now()

        return process

    def test_dc_dcga(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DC, const.STATUS_DC_GA)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dc_dm(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DC, const.STATUS_DM)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dc_ddnu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DC, const.STATUS_DD_NU)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dc_ddu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DC, const.STATUS_DD_U)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dcga_dmga(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DC_GA, const.STATUS_DM_GA)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dcga_ddnu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DC_GA, const.STATUS_DD_NU)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dcga_ddu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DC_GA, const.STATUS_DD_U)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dm_dmga(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DM, const.STATUS_DM_GA)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dm_dd_nu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DM, const.STATUS_DD_NU)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dm_ddu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DM, const.STATUS_DD_U)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dmga_ddnu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DM_GA, const.STATUS_DD_NU)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dmga_ddu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DM_GA, const.STATUS_DD_U)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_ddnu_ddu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_DD_NU, const.STATUS_DD_U)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dde_ddnu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_EMERITUS_DD, const.STATUS_DD_NU)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)

    def test_dde_ddu(self):
        client = self.make_test_client(self.persons.dam)
        process = self.make_process(const.STATUS_EMERITUS_DD, const.STATUS_DD_U)
        response = client.get(reverse("process_rt_ticket", args=[process.pk]))
        self.assertEqual(response.status_code, 200)
