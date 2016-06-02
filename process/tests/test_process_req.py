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
from .common import ProcessFixtureMixin, get_all_process_types, test_fingerprint1, test_fpr1_signed_valid_text


class TestProcessReq(ProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        for src, tgt in get_all_process_types():
            reqs = pmodels.Process.objects.compute_requirements(src, tgt)
            want_am = "am_ok" in reqs
            visitors = [None, "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "activeam", "fd", "dam", "app"]
            if want_am: visitors.append("am")
            for type in reqs:
                for visitor in visitors:
                    if want_am:
                        cls._add_method(cls._test_perms, type, src, tgt, visitor, am="dd_nu")
                        cls._add_method(cls._test_perms, type, src, tgt, visitor, am="dd_u")
                    else:
                        cls._add_method(cls._test_perms, type, src, tgt, visitor)

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

    def _test_perms(self, type, src, tgt, visitor, am=None):
        view = "process_req_" + type
        self.persons.create("app", status=src)
        self.fingerprints.create("app", person=self.persons.app, fpr=test_fingerprint1, is_active=True, audit_skip=True)
        self.processes.create("app", person=self.persons.app, applying_for=tgt, fd_comment="test")
        if am is not None:
            self.persons.create("am", status=am)
            self.ams.create("am", person=self.persons.am)

        req = pmodels.Requirement.objects.get(process=self.processes.app, type=type)
        if type in ("intent", "sc_dmup", "advocate", "am_ok"):
            pmodels.Statement.objects.create(requirement=req, fpr=self.fingerprints.app, statement=test_fpr1_signed_valid_text, uploaded_by=self.persons.app, uploaded_time=now())

        client = self.make_test_client(visitor)
        response = client.get(reverse(view, args=[self.processes.app.pk]))
        self.assertEqual(response.status_code, 200)
        visit_perms = req.permissions_of(self.persons[visitor])
        self.assertPageElements(response, visit_perms)

        # Assign am and repeat visit
        if am:
            pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())

            response = client.get(reverse(view, args=[self.processes.app.pk]))
            self.assertEqual(response.status_code, 200)
            visit_perms = req.permissions_of(self.persons[visitor])
            self.assertPageElements(response, visit_perms)

