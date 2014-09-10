# coding: utf8
"""
Test permissions
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from backend import const
from backend.test_common import *

class PermissionsTestCase(NMBasicFixtureMixin, NMTestUtilsMixin, TestCase):
    def setUp(self):
        super(PermissionsTestCase, self).setUp()
        self.app = self.make_user("app", const.STATUS_DC, alioth=True, fd_comment="FD_COMMENTS")
        self.adv = self.make_user("adv", const.STATUS_DD_NU)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.proc = self.make_process(self.app, const.STATUS_DD_NU, const.PROGRESS_AM, advocates=[self.adv], manager=self.am)

    def test_status_all(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("api_status")
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys():
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_status_one(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("api_status")
            data = { "person": "enrico@debian.org" }
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.viewkeys():
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_status_status(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("api_status")
            data = { "status": "dd_u,dd_nu" }
        self.assertVisit(WhenView(), ThenForbidden())
        for u in self.users.viewkeys():
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())

    def test_status_post(self):
        class WhenView(NMTestUtilsWhen):
            url = reverse("api_status")
            method = "post"
            data_content_type = "application/json"
            data = '["enrico@debian.org","example-guest@users.alioth.debian.org"]'
        self.assertVisit(WhenView(), ThenSuccess())
        for u in self.users.viewkeys():
            self.assertVisit(WhenView(user=self.users[u]), ThenSuccess())
