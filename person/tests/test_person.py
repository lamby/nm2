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
from mock import patch


class TestPerson(PersonFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPerson, cls).setUpClass()
        cls.page_elements = PageElements()
#        cls.page_elements.add_id("log_form")
#        cls.page_elements.add_id("log_public")
#        cls.page_elements.add_id("log_private")
#        cls.page_elements.add_id("proc_freeze")
#        cls.page_elements.add_id("proc_unfreeze")
#        cls.page_elements.add_id("proc_approve")
#        cls.page_elements.add_id("proc_unapprove")
#        cls.page_elements.add_id("req_approve")
#        cls.page_elements.add_id("req_unapprove")
#        cls.page_elements.add_id("statement_add")
#        cls.page_elements.add_class("statement_delete")

        cls.visited = cls.persons.activeam
        cls.visitor = cls.persons.dc
        cls.url = cls.visited.get_absolute_url()

    def compute_wanted_page_elements(self, visit_perms):
        """
        Compute what page elements we want, based on visit_perms
        """
        wanted = []
#        if "add_log" in visit_perms:
#            wanted += ["log_public", "log_private", "log_form"]
#        for el in ("req_approve", "req_unapprove"):
#            if el in visit_perms: wanted.append(el)
#        if "edit_statements" in visit_perms and self.req.type != "keycheck":
#            wanted.append("statement_add")
#            wanted.append("statement_delete")
        return wanted

    def assertPageElements(self, response):
        visit_perms = self.visited.permissions_of(self.visitor)
        wanted = self.compute_wanted_page_elements(visit_perms)
        self.assertContainsElements(response, self.page_elements, *wanted)

    def tryVisitingWithPerms(self, perms):
        client = self.make_test_client(self.visitor)
        with patch.object(bmodels.Person, "permissions_of", return_value=perms):
            response = client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertPageElements(response)

    def test_none(self):
        self.tryVisitingWithPerms(set())

#    def test_fd(self):
#        perms = self.req.permissions_of(self.persons.fd)
#        self.tryVisitingWithPerms(perms)
#
#    def test_dam(self):
#        perms = self.req.permissions_of(self.persons.dam)
#        self.tryVisitingWithPerms(perms)


class TestEditMixin(PersonFixtureMixin):
    @classmethod
    def setUpClass(cls):
        super(TestEditMixin, cls).setUpClass()
        cls.visited = cls.persons.dam
        cls.visitor = cls.persons.dc

        # All fields that this view is able to edit
        cls.edited_fields = []

        # All fields that we check, with an original and changed value
        cls.all_fields = {
            "username": ("old@debian.org", "new@debian.org"),
            "is_staff": (False, True),
            "cn": ("oldcn", "newcn"),
            "mn": ("oldmn", "newmn"),
            "sn": ("oldsn", "newsn"),
            "email": ("oldemail@example.org", "newemail@example.org"),
            "email_ldap": ("oldldap@example.org", "newldap@example.org"),
            "bio": ("oldbio", "newbio"),
            "uid": ("olduid", "newuid"),
            "status": ("dd_u", "dc"),
            "fd_comment": ("oldfd", "newfd"),
            "pending": ("oldpending", "newpending"),
        }

        # Set all fields to the original value
        for name, (oldval, newval) in cls.all_fields.items():
            setattr(cls.visited, name, oldval)
        cls.visited.save(audit_skip=True)

    def get_post_data(self):
        return { name: newval for name, (oldval, newval) in self.all_fields.items() }

    def assertChanged(self):
        self.visited.refresh_from_db()
        for name, (oldval, newval) in self.all_fields.items():
            if name in self.edited_fields:
                self.assertEqual(getattr(self.visited, name), newval)
            else:
                self.assertEqual(getattr(self.visited, name), oldval)

    def assertNotChanged(self):
        self.visited.refresh_from_db()
        for name, (oldval, newval) in self.all_fields.items():
            self.assertEqual(getattr(self.visited, name), oldval)

    def assertSuccess(self):
        client = self.make_test_client(self.visitor)

        response = client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotChanged()

        response = client.post(self.url, data=self.get_post_data())
        self.visited.refresh_from_db()
        self.assertRedirectMatches(response, self.visited.get_absolute_url())
        self.assertChanged()

    def assertForbidden(self):
        client = self.make_test_client(self.visitor)

        response = client.get(self.url)
        self.assertPermissionDenied(response)
        self.assertNotChanged()

        response = client.post(self.url, data=self.get_post_data())
        self.assertPermissionDenied(response)
        self.assertNotChanged()


class TestEditLDAP(TestEditMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEditLDAP, cls).setUpClass()
        cls.url = reverse("person_edit_ldap", args=[cls.visited.lookup_key])
        cls.edited_fields = ["cn", "mn", "sn", "email_ldap", "uid"]

    @patch.object(bmodels.Person, "permissions_of", return_value=["edit_ldap"])
    def test_success(self, perms):
        self.assertSuccess()

    @patch.object(bmodels.Person, "permissions_of", return_value=[])
    def test_forbidden(self, perms):
        self.assertForbidden()


class TestEditBio(TestEditMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEditBio, cls).setUpClass()
        cls.url = reverse("person_edit_bio", args=[cls.visited.lookup_key])
        cls.edited_fields = ["bio"]

    @patch.object(bmodels.Person, "permissions_of", return_value=["edit_bio"])
    def test_success(self, perms):
        self.assertSuccess()

    @patch.object(bmodels.Person, "permissions_of", return_value=[])
    def test_forbidden(self, perms):
        self.assertForbidden()


class TestEditEmail(TestEditMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestEditEmail, cls).setUpClass()
        cls.url = reverse("person_edit_email", args=[cls.visited.lookup_key])
        cls.edited_fields = ["email"]

    @patch.object(bmodels.Person, "permissions_of", return_value=["edit_email"])
    def test_success(self, perms):
        self.assertSuccess()

    @patch.object(bmodels.Person, "permissions_of", return_value=[])
    def test_forbidden(self, perms):
        self.assertForbidden()
