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
from .common import ProcessFixtureMixin, get_all_process_types


class TestProcessShow(ProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        for src, tgt in get_all_process_types():
            want_am = "am_ok" in pmodels.Process.objects.compute_requirements(src, tgt)
            visitors = [None, "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "activeam", "fd", "dam", "app"]
            if want_am: visitors.append("am")
            for visitor in visitors:
                if want_am:
                    cls._add_method(cls._test_perms, src, tgt, visitor, am="dd_nu")
                    cls._add_method(cls._test_perms, src, tgt, visitor, am="dd_u")
                else:
                    cls._add_method(cls._test_perms, src, tgt, visitor)

    @classmethod
    def setUpClass(cls):
        super(TestProcessShow, cls).setUpClass()
        cls.page_elements = PageElements()
        cls.page_elements.add_id("view_fd_comment")
        cls.page_elements.add_id("view_mbox")
        cls.page_elements.add_id("log_public")
        cls.page_elements.add_id("log_private")
        cls.page_elements.add_id("proc_freeze")
        cls.page_elements.add_id("proc_unfreeze")
        cls.page_elements.add_id("proc_approve")
        cls.page_elements.add_id("proc_unapprove")

    def assertPageElements(self, response, visit_perms):
        # Check page elements based on visit_perms
        wanted = []
        if visit_perms.visitor and visit_perms.visitor.is_admin:
            wanted.append("view_fd_comment")
        if "add_log" in visit_perms:
            wanted += ["log_public", "log_private"]
        for el in ("view_mbox", "proc_freeze", "proc_unfreeze", "proc_approve", "proc_unapprove"):
            if el in visit_perms: wanted.append(el)
        self.assertContainsElements(response, self.page_elements, *wanted)

    def _test_perms(self, src, tgt, visitor, am=None):
        self.persons.create("app", status=src)
        self.processes.create("app", person=self.persons.app, applying_for=tgt, fd_comment="test")
        if am is not None:
            self.persons.create("am", status=am)
            self.ams.create("am", person=self.persons.am)

        client = self.make_test_client(visitor)
        response = client.get(reverse("process_show", args=[self.processes.app.pk]))
        self.assertEqual(response.status_code, 200)
        visit_perms = self.processes.app.permissions_of(self.persons[visitor])
        self.assertPageElements(response, visit_perms)

        # Assign am and repeat visit
        if am:
            pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())

            response = client.get(reverse("process_show", args=[self.processes.app.pk]))
            self.assertEqual(response.status_code, 200)
            visit_perms = self.processes.app.permissions_of(self.persons[visitor])
            self.assertPageElements(response, visit_perms)
