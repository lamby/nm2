# coding: utf-8




from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin, ExpectedSets, TestSet, PageElements
import process.models as pmodels
from mock import patch
from .common import ProcessFixtureMixin


class TestProcessShow(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessShow, cls).setUpClass()
        cls.visitor = cls.persons.dc

        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.amassignments.create("am", process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons["fd"], assigned_time=now())

        cls.processes.app.add_log(cls.persons.fd, "xxxx_public_xxxx", is_public=True)
        cls.processes.app.add_log(cls.persons.fd, "xxxx_private_xxxx", is_public=False)
        cls.processes.app.add_log(cls.visitor, "xxxx_ownprivate_xxxx", is_public=False)

        cls.page_elements = PageElements()
        cls.page_elements.add_id("view_fd_comment")
        cls.page_elements.add_id("view_mbox")
        cls.page_elements.add_id("log_form")
        cls.page_elements.add_id("log_public")
        cls.page_elements.add_id("log_private")
        cls.page_elements.add_id("proc_freeze")
        cls.page_elements.add_id("proc_unfreeze")
        cls.page_elements.add_id("proc_approve")
        cls.page_elements.add_id("proc_unapprove")
        cls.page_elements.add_string("view_public_log", "xxxx_public_xxxx")
        cls.page_elements.add_string("view_private_log", "xxxx_private_xxxx")
        cls.page_elements.add_string("view_ownprivate_log", "xxxx_ownprivate_xxxx")

    def assertPageElements(self, response):
        # Check page elements based on visit_perms
        visit_perms = self.processes.app.permissions_of(self.visitor)
        wanted = ["view_public_log", "view_ownprivate_log"]
        if "fd_comments" in visit_perms:
            wanted.append("view_fd_comment")
        if "add_log" in visit_perms:
            wanted += ["log_public", "log_private", "log_form"]
        for el in ("view_mbox", "view_private_log", "proc_freeze", "proc_unfreeze", "proc_approve", "proc_unapprove"):
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

    def test_view_private_log(self):
        self.tryVisitingWithPerms(set(["view_private_log"]))

    def test_view_mbox(self):
        self.tryVisitingWithPerms(set(["view_mbox"]))

    def test_fd_comments(self):
        self.tryVisitingWithPerms(set(["fd_comments"]))

    def test_add_log(self):
        self.tryVisitingWithPerms(set(["add_log"]))

    def test_view_mbox(self):
        self.tryVisitingWithPerms(set(["view_mbox"]))

    def test_proc_freeze(self):
        self.tryVisitingWithPerms(set(["add_log", "proc_freeze"]))

    def test_proc_unfreeze(self):
        self.tryVisitingWithPerms(set(["add_log", "proc_unfreeze"]))

    def test_proc_approve(self):
        self.tryVisitingWithPerms(set(["add_log", "proc_approve"]))

    def test_proc_unapprove(self):
        self.tryVisitingWithPerms(set(["add_log", "proc_unapprove"]))
