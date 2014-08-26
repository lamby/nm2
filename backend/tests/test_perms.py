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
        self.e_dd = self.make_user("e_dd", const.STATUS_EMERITUS_DD)
        self.e_dm = self.make_user("e_dm", const.STATUS_EMERITUS_DM)
        self.r_dd = self.make_user("r_dd", const.STATUS_REMOVED_DD)
        self.r_dm = self.make_user("r_dm", const.STATUS_REMOVED_DM)
        self.am_e_dd = self.make_user("am_e_dd", const.STATUS_EMERITUS_DD)
        self.am_r_dd = self.make_user("am_r_dd", const.STATUS_REMOVED_DD)
        self.applicant1 = self.make_user("applicant1", const.STATUS_MM)
        self.make_process(self.applicant1, const.STATUS_DD_NU, const.PROGRESS_AM, manager=self.am_e_dd)
        self.applicant2 = self.make_user("applicant2", const.STATUS_MM)
        self.make_process(self.applicant2, const.STATUS_DD_NU, const.PROGRESS_AM, manager=self.am_r_dd)

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
        self.assertPerms("e_dd", [])
        self.assertPerms("e_dm", [])
        self.assertPerms("r_dd", [])
        self.assertPerms("r_dm", [])
        self.assertPerms("am_e_dd", [])
        self.assertPerms("am_r_dd", [])
        self.assertPerms("fd", ["admin", "am", "dd"])
        self.assertPerms("dam", ["admin", "am", "dd"])
