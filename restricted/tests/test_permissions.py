# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase, TransactionTestCase
from backend import const
from backend.test_common import *
from backend.unittest import PersonFixtureMixin, OldProcessFixtureMixin
import backend.models as bmodels

class PermissionsTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(PermissionsTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_AM, advocates=[self.adv], manager=self.am)

    def test_ammain(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_ammain")
        allowed = frozenset(("am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_impersonate(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("impersonate", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenRedirect("^http://testserver/$"))

    def test_db_export(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_db_export")
        allowed = frozenset(("dd_u", "dd_nu", "adv", "am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_db_export_full(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_db_export") + "?full"
        allowed = frozenset(("fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_mail_archive(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("download_mail_archive", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("app", "adv", "am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        # Success is a 404 because we did not create the file on disk
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenNotFound())

    def test_display_mail_archive(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("display_mail_archive", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("app", "adv", "am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        # Success is a 404 because we did not create the file on disk
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenNotFound())

    def test_minechangelogs(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_minechangelogs", kwargs={ "key": self.users["app"].lookup_key })
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys():
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

class AMProfileTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TransactionTestCase):
    def setUp(self):
        super(AMProfileTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.am_am = bmodels.AM.objects.create(person=self.am, slots=1, is_am=True)

    def test_amprofile(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_ammain")
        allowed = frozenset(("am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_post(self):
        users = self.users
        class WhenPost(NMTestUtilsWhen):
            method = "post"
            def __init__(self, user=None, person=None, **kw):
                user = users[user] if user else None
                self.person = users[person] if person else None
                self.visited = self.person if self.person else user
                self.am = self.visited.am_or_none
                data = { "slots": 2 }
                if self.am:
                    self.orig_slots = self.am.slots
                    self.orig_fd = self.am.is_fd
                    self.orig_dam = self.am.is_dam
                    if not self.am.is_fd: data["is_fd"] = "on"
                    if not self.am.is_dam: data["is_dam"] = "on"
                if self.person is None:
                    super(WhenPost, self).__init__(user=user, data=data, url=reverse("restricted_amprofile"), **kw)
                else:
                    super(WhenPost, self).__init__(user=user, data=data, url=reverse("restricted_amprofile", kwargs={ "key": self.person.lookup_key }), **kw)
            def tearDown(self, fixture):
                super(WhenPost, self).tearDown(fixture)
                if self.am:
                    self.am.slots = self.orig_slots
                    self.am.is_fd = self.orig_fd
                    self.am.is_dam = self.orig_dam
                    self.am.save()

        class ThenChanges(ThenSuccess):
            def __init__(self, slots=True, fd=False, dam=False):
                self.slots = slots
                self.fd = fd
                self.dam = dam
            def __call__(self, fixture, response, when, test_client):
                super(ThenChanges, self).__call__(fixture, response, when, test_client)
                am = bmodels.AM.objects.get(pk=when.person.am.pk)
                if self.slots:
                    fixture.assertEquals(am.slots, 2)
                else:
                    fixture.assertEquals(am.slots, when.orig_slots)
                if self.fd:
                    fixture.assertEquals(am.is_fd, not when.orig_fd)
                else:
                    fixture.assertEquals(am.is_fd, when.orig_fd)
                if self.dam:
                    fixture.assertEquals(am.is_dam, not when.orig_dam)
                else:
                    fixture.assertEquals(am.is_dam, when.orig_dam)

        # Anonymous cannot post to anything
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(person=u), ThenForbidden())

        for u in self.users.viewkeys() - frozenset(("am", "fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="am"), ThenForbidden())
        self.assertVisit(WhenPost(user="am", person="am"), ThenChanges())
        self.assertVisit(WhenPost(user="fd", person="am"), ThenChanges(fd=True))
        self.assertVisit(WhenPost(user="dam", person="am"), ThenChanges(fd=True, dam=True))

        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="fd"), ThenForbidden())
        self.assertVisit(WhenPost(user="fd", person="fd"), ThenChanges(fd=True))
        self.assertVisit(WhenPost(user="dam", person="fd"), ThenChanges(fd=True, dam=True))

        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="dam"), ThenForbidden())
        self.assertVisit(WhenPost(user="fd", person="dam"), ThenChanges(fd=True))
        self.assertVisit(WhenPost(user="dam", person="dam"), ThenChanges(fd=True, dam=True))

class AssignAMTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(AssignAMTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.am_am = bmodels.AM.objects.create(person=self.am, slots=1, is_am=True)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_APP_OK, advocates=[self.adv])

    def test_assign_am(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("assign_am", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

        # TODO: post

class AssignAMAgainTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(AssignAMAgainTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_AM, manager=self.am, advocates=[self.adv])

    def test_assign_am(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("assign_am", kwargs={ "key": self.users["app"].lookup_key })
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys():
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())

        # TODO: post


class PersonTestCase(OldProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(PersonTestCase, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        cls.persons.create("adv", status=const.STATUS_DD_NU)
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_NU, progress=const.PROGRESS_AM, manager=cls.persons.am, advocates=[cls.persons.adv])

    @classmethod
    def __add_extra_tests__(cls):
        # Anonymous cannot see or post to anyone's page
        for visited in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "app", "adv", "am", "fd", "dam"):
            cls._add_method(cls._test_get_forbidden, None, visited)
            cls._add_method(cls._test_post_forbidden, None, visited)

        # Only app, adv, am, fd, dam can edit other people's LDAP information
        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "app", "adv", "am", "fd", "dam"):
            for visited in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "app", "adv", "am", "fd", "dam"):
                cls._add_method(cls._test_maybe_allowed, visitor, visited)

    def _test_get_forbidden(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.get(reverse("restricted_person", kwargs={"key": self.persons[visited].lookup_key}))
        self.assertPermissionDenied(response)

    def _test_post_forbidden(self, visitor, visited):
        client = self.make_test_client(visitor)
        visited = self.persons[visited]
        orig_cn = visited.cn
        orig_fd_comment = visited.fd_comment
        orig_bio = visited.bio
        orig_email = visited.email
        orig_status = visited.status
        response = client.post(reverse("restricted_person", kwargs={"key": visited.lookup_key}), data={
            "cn": "Z", "fd_comment": "Z", "bio": "Z", "email": "foo@example.org", "status": const.STATUS_DC
        })
        self.assertPermissionDenied(response)
        visited.refresh_from_db()
        self.assertEquals(visited.cn, orig_cn)
        self.assertEquals(visited.fd_comment, orig_fd_comment)
        self.assertEquals(visited.bio, orig_bio)
        self.assertEquals(visited.email, orig_email)
        self.assertEquals(visited.status, orig_status)

    def _test_maybe_allowed(self, visitor, visited):
        # Just check that the actions correspond to the right permissions. That
        # the permissions are right is checked elsewhere
        visit_perms = self.persons[visited].permissions_of(self.persons[visitor])
        if "edit_ldap" not in visit_perms and "edit_bio" not in visit_perms:
            self._test_post_forbidden(visitor, visited)
            return

        client = self.make_test_client(visitor)
        visited = self.persons[visited]
        orig_cn = visited.cn
        orig_fd_comment = visited.fd_comment
        orig_bio = visited.bio
        orig_email = visited.email
        orig_status = visited.status

        new_status = const.STATUS_DC if visited.status != const.STATUS_DC else const.STATUS_DM
        response = client.post(reverse("restricted_person", kwargs={"key": visited.lookup_key}), data={
            "cn": "Z", "fd_comment": "Z", "bio": "Z", "email_ldap": "foo@example.org", "status": new_status
        })
        visited.refresh_from_db()
        self.assertRedirectMatches(response, visited.get_absolute_url())

        if "edit_ldap" in visit_perms:
            self.assertEquals(visited.cn, "Z")
            self.assertEquals(visited.email_ldap, "foo@example.org")
        else:
            self.assertEquals(visited.cn, orig_cn)
            self.assertEquals(visited.email_ldap, orig_email)
        if "edit_bio" in visit_perms:
            self.assertEquals(visited.bio, "Z")
        else:
            self.assertEquals(visited.bio, orig_bio)
        if self.persons[visitor].is_admin:
            self.assertEquals(visited.fd_comment, "Z")
            self.assertEquals(visited.status, new_status)
        else:
            self.assertEquals(visited.fd_comment, orig_fd_comment)
            self.assertEquals(visited.status, orig_status)
