from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin, ExpectedSets, TestSet, PageElements
import process.models as pmodels
from unittest.mock import patch
from .common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text,
                     test_fingerprint2, test_fpr2_signed_valid_text,
                     test_fingerprint3, test_fpr3_signed_valid_text)


class TestProcessReqMixin(ProcessFixtureMixin):
    req_type = None

    @classmethod
    def setUpClass(cls):
        super(TestProcessReqMixin, cls).setUpClass()
        # Create a process with all requirements
        cls.persons.create("app", status=const.STATUS_DC)
        cls.fingerprints.create("app", person=cls.persons.app, fpr=test_fingerprint1, is_active=True, audit_skip=True)
        cls.fingerprints.create("dd_nu", person=cls.persons.dd_nu, fpr=test_fingerprint2, is_active=True, audit_skip=True)
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.fingerprints.create("am", person=cls.persons.am, fpr=test_fingerprint3, is_active=True, audit_skip=True)
        cls.ams.create("am", person=cls.persons.am)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        pmodels.AMAssignment.objects.create(process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons["fd"], assigned_time=now())

        pmodels.Statement.objects.create(requirement=cls.processes.app.requirements.get(type="intent"), fpr=cls.fingerprints.app, statement=test_fpr1_signed_valid_text, uploaded_by=cls.persons.app, uploaded_time=now())
        pmodels.Statement.objects.create(requirement=cls.processes.app.requirements.get(type="sc_dmup"), fpr=cls.fingerprints.app, statement=test_fpr1_signed_valid_text, uploaded_by=cls.persons.app, uploaded_time=now())
        pmodels.Statement.objects.create(requirement=cls.processes.app.requirements.get(type="advocate"), fpr=cls.fingerprints.dd_nu, statement=test_fpr2_signed_valid_text, uploaded_by=cls.persons.dd_nu, uploaded_time=now())
        pmodels.Statement.objects.create(requirement=cls.processes.app.requirements.get(type="am_ok"), fpr=cls.fingerprints.am, statement=test_fpr3_signed_valid_text, uploaded_by=cls.persons.am, uploaded_time=now())

        cls.visitor = cls.persons.dc

        cls.page_elements = PageElements()
        cls.page_elements.add_id("log_form")
        cls.page_elements.add_id("log_public")
        cls.page_elements.add_id("log_private")
        cls.page_elements.add_id("proc_freeze")
        cls.page_elements.add_id("proc_unfreeze")
        cls.page_elements.add_id("proc_approve")
        cls.page_elements.add_id("proc_unapprove")
        cls.page_elements.add_id("req_approve")
        cls.page_elements.add_id("req_unapprove")
        cls.page_elements.add_id("statement_add")
        cls.page_elements.add_class("statement_delete")
        cls.page_elements.add_id("emeritus")
        cls.page_elements.add_id("removal_notice")

        cls.req = cls.processes.app.requirements.get(type=cls.req_type)

    def compute_wanted_page_elements(self, visit_perms):
        """
        Compute what page elements we want, based on visit_perms
        """
        wanted = []
        if "add_log" in visit_perms:
            wanted += ["log_public", "log_private", "log_form"]
        for el in ("req_approve", "req_unapprove"):
            if el in visit_perms: wanted.append(el)
        if "edit_statements" in visit_perms and self.req.type != "keycheck":
            wanted.append("statement_add")
            wanted.append("statement_delete")
        return wanted

    def assertPageElements(self, response):
        visit_perms = self.req.permissions_of(self.visitor)
        wanted = self.compute_wanted_page_elements(visit_perms)

        self.assertContainsElements(response, self.page_elements, *wanted)

    def tryVisitingWithPerms(self, perms):
        client = self.make_test_client(self.visitor)
        with patch.object(pmodels.Requirement, "permissions_of", return_value=perms):
            response = client.get(self.req.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            self.assertPageElements(response)

    def test_none(self):
        self.tryVisitingWithPerms(set())

    def test_add_log(self):
        self.tryVisitingWithPerms(set(["add_log"]))

    def test_req_approve(self):
        self.tryVisitingWithPerms(set(["add_log", "req_approve"]))

    def test_req_unapprove(self):
        self.tryVisitingWithPerms(set(["add_log", "req_unapprove"]))

    def test_edit_statements(self):
        self.tryVisitingWithPerms(set(["edit_statements"]))

    def test_dd_nu(self):
        perms = self.req.permissions_of(self.persons.dd_nu)
        self.tryVisitingWithPerms(perms)

    def test_dd_u(self):
        perms = self.req.permissions_of(self.persons.dd_u)
        self.tryVisitingWithPerms(perms)

    def test_fd(self):
        perms = self.req.permissions_of(self.persons.fd)
        self.tryVisitingWithPerms(perms)

    def test_dam(self):
        perms = self.req.permissions_of(self.persons.dam)
        self.tryVisitingWithPerms(perms)


class TestProcessReqIntent(TestProcessReqMixin, TestCase):
    req_type = "intent"

class TestProcessReqIntentEmeritus(TestProcessReqMixin, TestCase):
    req_type = "intent"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.app.applying_for = const.STATUS_EMERITUS_DD
        cls.processes.app.save()

    def compute_wanted_page_elements(self, visit_perms):
        wanted = super().compute_wanted_page_elements(visit_perms)
        if "statement_add" in wanted:
            wanted.remove("statement_add")
            wanted.append("emeritus")
        return wanted


class TestProcessReqIntentRemoved(TestProcessReqMixin, TestCase):
    req_type = "intent"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.processes.app.applying_for = const.STATUS_REMOVED_DD
        cls.processes.app.save()

    def compute_wanted_page_elements(self, visit_perms):
        wanted = super().compute_wanted_page_elements(visit_perms)
        if "statement_add" in wanted:
            wanted.remove("statement_add")
            wanted.append("removal_notice")
        return wanted


class TestProcessReqScDmup(TestProcessReqMixin, TestCase):
    req_type = "sc_dmup"

class TestProcessReqAdvocate(TestProcessReqMixin, TestCase):
    req_type = "advocate"

class TestProcessReqAmOk(TestProcessReqMixin, TestCase):
    req_type = "am_ok"

    @classmethod
    def setUpClass(cls):
        super(TestProcessReqAmOk, cls).setUpClass()
        cls.page_elements.add_id("am_assign")
        cls.page_elements.add_id("am_unassign")

    def compute_wanted_page_elements(self, visit_perms):
        wanted = super(TestProcessReqAmOk, self).compute_wanted_page_elements(visit_perms)
        for el in ("am_assign", "am_unassign"):
            if el in visit_perms: wanted.append(el)
        return wanted

    def test_req_am_assign(self):
        self.tryVisitingWithPerms(set(["am_assign"]))

    def test_req_am_assign(self):
        self.tryVisitingWithPerms(set(["am_unassign"]))

class TestProcessReqKeycheck(TestProcessReqMixin, TestCase):
    req_type = "keycheck"
