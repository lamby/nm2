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
from .common import (ProcessFixtureMixin, get_all_process_types,
                     test_fingerprint1, test_fpr1_signed_valid_text,
                     test_fingerprint2, test_fpr2_signed_valid_text,
                     test_fingerprint3, test_fpr3_signed_valid_text)


class TestProcessReq(ProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        for src, tgt in get_all_process_types():
            want_am = "am_ok" in pmodels.Process.objects.compute_requirements(src, tgt)
            visitors = [None, "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "activeam", "fd", "dam", "app"]
            if want_am: visitors.append("am")
            for visitor in visitors:
                if want_am:
                    cls._add_method(cls._test_perms, src, tgt, visitor, am="dd_nu")
                else:
                    cls._add_method(cls._test_perms, src, tgt, visitor)

    @classmethod
    def setUpClass(cls):
        super(TestProcessReq, cls).setUpClass()
        cls.page_elements = PageElements()
        cls.page_elements.add_id("log_public")
        cls.page_elements.add_id("log_private")
        cls.page_elements.add_id("req_approve")
        cls.page_elements.add_id("req_unapprove")
        cls.page_elements.add_id("statement_add")
        cls.page_elements.add_class("statement_delete")
        cls.page_elements_bytype = {}
        for req_type in ("intent", "sc_dmup", "advocate", "am_ok", "keycheck"):
            cls.page_elements_bytype[req_type] = cls.page_elements.clone()
        cls.page_elements_bytype["am_ok"].add_id("am_assign")
        cls.page_elements_bytype["am_ok"].add_id("am_unassign")

    def assertPageElements(self, response, visit_perms):
        # Check page elements based on visit_perms
        wanted = []
        if "add_log" in visit_perms:
            wanted += ["log_public", "log_private"]
        for el in ("req_approve", "req_unapprove"):
            if el in visit_perms: wanted.append(el)
        if "edit_statements" in visit_perms:
            wanted.append("statement_add")
            wanted.append("statement_delete")
        self.assertContainsElements(response, self.page_elements, *wanted)

    def _test_requirement_generic(self, req, visitor):
        client = self.make_test_client(visitor)
        response = client.get(req.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        visit_perms = req.permissions_of(self.persons[visitor])
        self.assertPageElements(response, visit_perms)

    def _test_requirement_intent(self, visitor):
        req = pmodels.Requirement.objects.get(process=self.processes.app, type="intent")
        pmodels.Statement.objects.create(requirement=req, fpr=self.fingerprints.app, statement=test_fpr1_signed_valid_text, uploaded_by=self.persons.app, uploaded_time=now())
        self._test_requirement_generic(req, visitor)

    def _test_requirement_sc_dmup(self, visitor):
        req = pmodels.Requirement.objects.get(process=self.processes.app, type="sc_dmup")
        pmodels.Statement.objects.create(requirement=req, fpr=self.fingerprints.app, statement=test_fpr1_signed_valid_text, uploaded_by=self.persons.app, uploaded_time=now())
        self._test_requirement_generic(req, visitor)

    def _test_requirement_advocate(self, visitor):
        req = pmodels.Requirement.objects.get(process=self.processes.app, type="advocate")
        pmodels.Statement.objects.create(requirement=req, fpr=self.fingerprints.dd_nu, statement=test_fpr2_signed_valid_text, uploaded_by=self.persons.dd_nu, uploaded_time=now())
        self._test_requirement_generic(req, visitor)

    def _test_requirement_keycheck(self, visitor):
        req = pmodels.Requirement.objects.get(process=self.processes.app, type="keycheck")
        self._test_requirement_generic(req, visitor)

    def _test_requirement_am_ok(self, visitor):
        req = pmodels.Requirement.objects.get(process=self.processes.app, type="am_ok")
        pmodels.Statement.objects.create(requirement=req, fpr=self.fingerprints.am, statement=test_fpr3_signed_valid_text, uploaded_by=self.persons.am, uploaded_time=now())
        self._test_requirement_generic(req, visitor)

    def _test_perms(self, src, tgt, visitor, am=None):
        # Create process
        self.persons.create("app", status=src)
        self.fingerprints.create("app", person=self.persons.app, fpr=test_fingerprint1, is_active=True, audit_skip=True)
        self.processes.create("app", person=self.persons.app, applying_for=tgt, fd_comment="test")
        self.fingerprints.create("dd_nu", person=self.persons.dd_nu, fpr=test_fingerprint2, is_active=True, audit_skip=True)
        if am is not None:
            self.persons.create("am", status=am)
            self.fingerprints.create("am", person=self.persons.am, fpr=test_fingerprint3, is_active=True, audit_skip=True)
            self.ams.create("am", person=self.persons.am)

        reqs = pmodels.Process.objects.compute_requirements(src, tgt)
        if "intent" in reqs: self._test_requirement_intent(visitor)
        if "sc_dmup" in reqs: self._test_requirement_sc_dmup(visitor)
        if "advocate" in reqs: self._test_requirement_advocate(visitor)
        if "keycheck" in reqs: self._test_requirement_keycheck(visitor)
        if "am_ok" in reqs: self._test_requirement_am_ok(visitor)

        # Assign am and repeat visit
        if am:
            pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
            if "intent" in reqs: self._test_requirement_intent(visitor)
            if "sc_dmup" in reqs: self._test_requirement_sc_dmup(visitor)
            if "advocate" in reqs: self._test_requirement_advocate(visitor)
            if "keycheck" in reqs: self._test_requirement_keycheck(visitor)
            if "am_ok" in reqs: self._test_requirement_am_ok(visitor)
