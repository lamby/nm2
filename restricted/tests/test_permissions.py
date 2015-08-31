# coding: utf8
"""
Test permissions
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase, TransactionTestCase
from backend import const
from backend.test_common import *
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

    def test_advocate(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_advocate", kwargs={ "key": self.users["app"].lookup_key, "applying_for": "dd_nu" })
        allowed = frozenset(("dd_u", "dd_nu", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

        # TODO: post

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


class PersonTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TransactionTestCase):
    def setUp(self):
        super(PersonTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_AM, manager=self.am, advocates=[self.adv])

    def test_person(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_person", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("app", "adv", "am", "fd", "dam"))
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
                self.person = users[person]
                data = { "cn": "Z", "fd_comment": "Z", "bio": "Z", "email": self.person.email, "status": const.STATUS_DC }
                self.orig_cn = self.person.cn
                self.orig_fd = self.person.fd_comment
                self.orig_bio = self.person.bio
                self.orig_status = self.person.status
                super(WhenPost, self).__init__(user=user, data=data, url=reverse("restricted_person", kwargs={ "key": self.person.lookup_key }), **kw)
            def tearDown(self, fixture):
                super(WhenPost, self).tearDown(fixture)
                self.person.cn = self.orig_cn
                self.person.fd_comment = self.orig_fd
                self.person.bio = self.orig_bio
                self.person.status = self.orig_status
                self.person.save(audit_skip=True)

        class ThenChanges(ThenRedirect):
            def __init__(self, cn=False, fd=False, bio=False, status=False):
                self.cn, self.fd, self.bio, self.status = cn, fd, bio, status
            def __call__(self, fixture, response, when, test_client):
                super(ThenChanges, self).__call__(fixture, response, when, test_client)
                person = bmodels.Person.objects.get(pk=when.person.pk)
                if self.cn:
                    fixture.assertEquals(person.cn, "Z")
                else:
                    fixture.assertEquals(person.cn, when.orig_cn)
                if self.fd:
                    fixture.assertEquals(person.fd_comment, "Z")
                else:
                    fixture.assertEquals(person.fd_comment, when.orig_fd)
                if self.bio:
                    fixture.assertEquals(person.bio, "Z")
                else:
                    fixture.assertEquals(person.bio, when.orig_bio)
                if self.status:
                    fixture.assertEquals(person.status, const.STATUS_DC )
                else:
                    fixture.assertEquals(person.status, when.orig_status)

        # Anonymous cannot post to anything
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(person=u), ThenForbidden())

        for u in self.users.viewkeys() - frozenset(("app", "adv", "am", "fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="app"), ThenForbidden())
        self.assertVisit(WhenPost(user="app", person="app"), ThenChanges(True, False, True, False))
        self.assertVisit(WhenPost(user="adv", person="app"), ThenChanges(True, False, True, False))
        self.assertVisit(WhenPost(user="am", person="app"), ThenChanges(True, False, True, False))
        self.assertVisit(WhenPost(user="fd", person="app"), ThenChanges(True, True, True, True))
        self.assertVisit(WhenPost(user="dam", person="app"), ThenChanges(True, True, True, True))

        for u in self.users.viewkeys() - frozenset(("adv", "fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="adv"), ThenForbidden())
        self.assertVisit(WhenPost(user="adv", person="adv"), ThenChanges(False, False, True, False))
        self.assertVisit(WhenPost(user="fd", person="adv"), ThenChanges(False, True, True, True))
        self.assertVisit(WhenPost(user="dam", person="adv"), ThenChanges(False, True, True, True))

        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="fd"), ThenForbidden())
        self.assertVisit(WhenPost(user="fd", person="fd"), ThenChanges(False, True, True, True))
        self.assertVisit(WhenPost(user="dam", person="fd"), ThenChanges(False, True, True, True))

        for u in self.users.viewkeys() - frozenset(("fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="dam"), ThenForbidden())
        self.assertVisit(WhenPost(user="fd", person="dam"), ThenChanges(False, True, True, True))
        self.assertVisit(WhenPost(user="dam", person="dam"), ThenChanges(False, True, True, True))


class PersonFingerprintTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TransactionTestCase):
    def setUp(self):
        super(PersonFingerprintTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_AM, manager=self.am, advocates=[self.adv])

    def test_get(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_person_fingerprints", kwargs={ "key": self.users["app"].lookup_key })
        allowed = frozenset(("app", "adv", "am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_post(self):
        users = self.users
        fpr = "0123456789abcdef00000123456789abcdef0000"
        class WhenPost(NMTestUtilsWhen):
            method = "post"
            def __init__(self, user=None, person=None, **kw):
                user = users[user] if user else None
                self.person = users[person]
                data = { "fpr": fpr }
                self.orig_fprs = self.person.fprs
                super(WhenPost, self).__init__(user=user, data=data, url=reverse("restricted_person_fingerprints", kwargs={ "key": self.person.lookup_key }), **kw)
            def tearDown(self, fixture):
                super(WhenPost, self).tearDown(fixture)
                self.person.fprs.filter(fpr=fpr).delete()

        class ThenAdded(ThenRedirect):
            def __call__(self, fixture, response, when, test_client):
                super(ThenAdded, self).__call__(fixture, response, when, test_client)
                person = bmodels.Person.objects.get(pk=when.person.pk)
                fixture.assertTrue(person.fprs.filter(fpr=fpr).exists())

        # Anonymous cannot post to anything
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(person=u), ThenForbidden())

        for u in self.users.viewkeys() - frozenset(("app", "adv", "am", "fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="app"), ThenForbidden())
        self.assertVisit(WhenPost(user="app", person="app"), ThenAdded())
        self.assertVisit(WhenPost(user="adv", person="app"), ThenAdded())
        self.assertVisit(WhenPost(user="am", person="app"), ThenAdded())
        self.assertVisit(WhenPost(user="fd", person="app"), ThenAdded())
        self.assertVisit(WhenPost(user="dam", person="app"), ThenAdded())

        # DDs have key in LDAP, need to manage them via keyring-maint
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(user=u, person="adv"), ThenForbidden())
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(user=u, person="fd"), ThenForbidden())
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(user=u, person="dam"), ThenForbidden())


class PersonFingerprintActivateTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TransactionTestCase):
    def setUp(self):
        super(PersonFingerprintActivateTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_AM, manager=self.am, advocates=[self.adv])

        for idx, u in enumerate(self.users.values()):
            bmodels.Fingerprint.objects.create(user=u, fpr="0123456789abcdef00000123456789abcdef{:04}".format(idx), is_active=False, audit_skip=True)

    def test_get(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("restricted_person_fingerprints_activate", kwargs={
                "key": self.users["app"].lookup_key,
                "fpr": self.users["app"].fprs.get().fpr,
            })
        allowed = frozenset(("app", "adv", "am", "fd", "dam"))
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys() - allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenForbidden())
        for u in allowed:
            self.assertVisit(WhenView(user=self.users[u]), ThenMethodNotAllowed())

    def test_post(self):
        users = self.users
        class WhenPost(NMTestUtilsWhen):
            method = "post"
            def __init__(self, user=None, person=None, **kw):
                user = users[user] if user else None
                self.person = users[person]
                data = {}
                self.orig_fprs = self.person.fprs
                super(WhenPost, self).__init__(user=user, data=data, url=reverse("restricted_person_fingerprints_activate", kwargs={
                    "key": self.person.lookup_key,
                    "fpr": self.person.fprs.get().fpr,
                }), **kw)
            def tearDown(self, fixture):
                super(WhenPost, self).tearDown(fixture)
                self.person.fprs.all().update(is_active=False)

        class ThenActive(ThenRedirect):
            def __call__(self, fixture, response, when, test_client):
                super(ThenActive, self).__call__(fixture, response, when, test_client)
                person = bmodels.Person.objects.get(pk=when.person.pk)
                fixture.assertTrue(person.fprs.get().is_active)

        # Anonymous cannot post to anything
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(person=u), ThenForbidden())

        for u in self.users.viewkeys() - frozenset(("app", "adv", "am", "fd", "dam")):
            self.assertVisit(WhenPost(user=u, person="app"), ThenForbidden())
        self.assertVisit(WhenPost(user="app", person="app"), ThenActive())
        self.assertVisit(WhenPost(user="adv", person="app"), ThenActive())
        self.assertVisit(WhenPost(user="am", person="app"), ThenActive())
        self.assertVisit(WhenPost(user="fd", person="app"), ThenActive())
        self.assertVisit(WhenPost(user="dam", person="app"), ThenActive())

        # DDs have key in LDAP, need to manage them via keyring-maint
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(user=u, person="adv"), ThenForbidden())
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(user=u, person="fd"), ThenForbidden())
        for u in self.users.viewkeys():
            self.assertVisit(WhenPost(user=u, person="dam"), ThenForbidden())
