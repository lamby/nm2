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

class PermissionsTestCase(NMBasicFixtureMixin, TestCase):
    def setUp(self):
        super(PermissionsTestCase, self).setUp()
        self.applicant = self.make_user("applicant", const.STATUS_MM)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.make_process(self.applicant, const.STATUS_DD_NU, const.PROGRESS_AM, manager=self.am)

    def assertPerms(self, pname, perms):
        self.assertEquals(sorted(self.users[pname].perms), perms)

    def test_person(self):
        self.assertPerms("pending", [])
        self.assertPerms("dc", [])
        self.assertPerms("dc_ga", [])
        self.assertPerms("dm", [])
        self.assertPerms("dm_ga", [])
        self.assertPerms("applicant", [])
        self.assertPerms("dd_nu", ["am_candidate", "dd"])
        self.assertPerms("dd_u", ["am_candidate", "dd"])
        self.assertPerms("am", ["am", "dd"])
        self.assertPerms("fd", ["admin", "am", "dd"])
        self.assertPerms("dam", ["admin", "am", "dd"])
