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
from .common import ProcessFixtureMixin, get_all_process_types


class TestProcessShow(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessShow, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)

        cls.visitor = cls.persons.dc

        cls.page_elements = PageElements()
        cls.page_elements.add_id("view_fd_comment")
        cls.page_elements.add_id("view_mbox")
        cls.page_elements.add_id("log_public")
        cls.page_elements.add_id("log_private")
        cls.page_elements.add_id("proc_freeze")
        cls.page_elements.add_id("proc_unfreeze")
        cls.page_elements.add_id("proc_approve")
        cls.page_elements.add_id("proc_unapprove")

    def assertPageElements(self, response):
        # Check page elements based on visit_perms
        visit_perms = self.processes.app.permissions_of(self.visitor)
        wanted = []
        if "fd_comment" in visit_perms:
            wanted.append("view_fd_comment")
        if "add_log" in visit_perms:
            wanted += ["log_public", "log_private"]
        for el in ("view_mbox", "proc_freeze", "proc_unfreeze", "proc_approve", "proc_unapprove"):
            if el in visit_perms: wanted.append(el)
        self.assertContainsElements(response, self.page_elements, *wanted)

    def tryVisitingWithPerms(self, perms):
        client = self.make_test_client(self.visitor)
        with patch.object(pmodels.Process, "permissions_of", return_value=perms):
            response = client.get(self.processes.app.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            self.assertPageElements(response)

    def test_none(self):
        self.tryVisitingWithPerms(set())
        pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
        self.tryVisitingWithPerms(set())

    def test_add_log(self):
        self.tryVisitingWithPerms(set(["add_log"]))
        pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
        self.tryVisitingWithPerms(set(["add_log"]))

    def test_view_mbox(self):
        self.tryVisitingWithPerms(set(["view_mbox"]))
        pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
        self.tryVisitingWithPerms(set(["view_mbox"]))

    def test_proc_freeze(self):
        self.tryVisitingWithPerms(set(["proc_freeze"]))
        pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
        self.tryVisitingWithPerms(set(["proc_freeze"]))

    def test_proc_unfreeze(self):
        self.tryVisitingWithPerms(set(["proc_unfreeze"]))
        pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
        self.tryVisitingWithPerms(set(["proc_unfreeze"]))

    def test_proc_approve(self):
        self.tryVisitingWithPerms(set(["proc_approve"]))
        pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
        self.tryVisitingWithPerms(set(["proc_approve"]))

    def test_proc_unapprove(self):
        self.tryVisitingWithPerms(set(["proc_unapprove"]))
        pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
        self.tryVisitingWithPerms(set(["proc_unapprove"]))
