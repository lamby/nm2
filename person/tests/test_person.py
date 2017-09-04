from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin, ExpectedSets, TestSet, PageElements
from unittest.mock import patch


class TestPerson(PersonFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPerson, cls).setUpClass()
        cls.page_elements = PageElements()
        cls.page_elements.add_id("view_person_fd_comment")
        cls.page_elements.add_id("edit_ldap_link")
        # cls.page_elements.add_id("edit_am_link") TODO: turn this into a permission-based element
        cls.page_elements.add_id("edit_bio_link")
        cls.page_elements.add_id("audit_log")

        cls.visited = cls.persons.activeam
        cls.visited.mn = "Test"
        cls.visited.save(audit_author=cls.persons.dam, audit_notes="test")
        cls.visitor = cls.persons.dc
        cls.url = cls.visited.get_absolute_url()

    def compute_wanted_page_elements(self, visit_perms):
        """
        Compute what page elements we want, based on visit_perms
        """
        wanted = []
        if "fd_comments" in visit_perms:
            wanted += ["view_person_fd_comment"]
        if "edit_ldap" in visit_perms:
            wanted += ["edit_ldap_link"]
        if "edit_bio" in visit_perms:
            wanted += ["edit_bio_link"]
        if "view_person_audit_log" in visit_perms:
            wanted += ["audit_log"]
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

    def test_person(self):
        self.tryVisitingWithPerms(set(["view_person_audit_log", "edit_bio"]))
        self.tryVisitingWithPerms(set(["view_person_audit_log", "edit_bio", "edit_ldap"]))

    def test_fd_dam(self):
        self.tryVisitingWithPerms(set(["view_person_audit_log", "edit_bio", "fd_comment"]))
        self.tryVisitingWithPerms(set(["view_person_audit_log", "edit_bio", "edit_ldap", "fd_comment"]))


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
        for name, (oldval, newval) in list(cls.all_fields.items()):
            setattr(cls.visited, name, oldval)
        cls.visited.save(audit_skip=True)

    def get_post_data(self):
        return { name: newval for name, (oldval, newval) in list(self.all_fields.items()) }

    def assertChanged(self):
        self.visited.refresh_from_db()
        for name, (oldval, newval) in list(self.all_fields.items()):
            if name in self.edited_fields:
                self.assertEqual(getattr(self.visited, name), newval)
            else:
                self.assertEqual(getattr(self.visited, name), oldval)

    def assertNotChanged(self):
        self.visited.refresh_from_db()
        for name, (oldval, newval) in list(self.all_fields.items()):
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
