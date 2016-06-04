# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from backend import const
from backend import models as bmodels
from process import models as pmodels
from backend.unittest import BaseFixtureMixin, PersonFixtureMixin

class TestRequirements(PersonFixtureMixin, TestCase):
    def assertRequirements(self, status, applying_for, expected):
        computed = pmodels.Process.objects.compute_requirements(status, applying_for)
        self.assertItemsEqual(computed, expected)

    def assertInvalid(self, status, applying_for):
        with self.assertRaises(RuntimeError) as re:
            pmodels.Process.objects.compute_requirements(status, applying_for)

    def test_requirements(self):
        all_statuses = {s.tag for s in const.ALL_STATUS}

        for dest in all_statuses - { const.STATUS_DC_GA, const.STATUS_DM, const.STATUS_DD_NU, const.STATUS_DD_U }:
            self.assertInvalid("dc", dest)
        self.assertRequirements("dc", const.STATUS_DC_GA, ["intent", "sc_dmup", "advocate"])
        self.assertRequirements("dc", const.STATUS_DM, ["intent", "sc_dmup", "advocate", "keycheck"])
        self.assertRequirements("dc", const.STATUS_DD_NU, ["intent", "sc_dmup", "advocate", "keycheck", "am_ok"])
        self.assertRequirements("dc", const.STATUS_DD_U, ["intent", "sc_dmup", "advocate", "keycheck", "am_ok"])

        for dest in all_statuses - { const.STATUS_DM_GA, const.STATUS_DD_NU, const.STATUS_DD_U }:
            self.assertInvalid("dc_ga", dest)
        self.assertRequirements("dc_ga", const.STATUS_DM_GA, ["intent", "sc_dmup", "advocate", "keycheck"])
        self.assertRequirements("dc_ga", const.STATUS_DD_NU, ["intent", "sc_dmup", "advocate", "keycheck", "am_ok"])
        self.assertRequirements("dc_ga", const.STATUS_DD_U, ["intent", "sc_dmup", "advocate", "keycheck", "am_ok"])

        for dest in all_statuses - { const.STATUS_DM_GA, const.STATUS_DD_NU, const.STATUS_DD_U }:
            self.assertInvalid("dm", dest)
        self.assertRequirements("dm", const.STATUS_DM_GA, ["intent", "sc_dmup"])
        self.assertRequirements("dm", const.STATUS_DD_NU, ["intent", "sc_dmup", "advocate", "keycheck", "am_ok"])
        self.assertRequirements("dm", const.STATUS_DD_U, ["intent", "sc_dmup", "advocate", "keycheck", "am_ok"])

        for dest in all_statuses - { const.STATUS_DD_NU, const.STATUS_DD_U }:
            self.assertInvalid("dm_ga", dest)
        self.assertRequirements("dm_ga", const.STATUS_DD_NU, ["intent", "sc_dmup", "advocate", "keycheck", "am_ok"])
        self.assertRequirements("dm_ga", const.STATUS_DD_U, ["intent", "sc_dmup", "advocate", "keycheck", "am_ok"])

        for dest in all_statuses - set([const.STATUS_DD_U]):
            self.assertInvalid("dd_nu", dest)
        self.assertRequirements("dd_nu", const.STATUS_DD_U, ["intent", "sc_dmup", "advocate"])

        for dest in all_statuses:
            self.assertInvalid("dd_u", dest)

        for dest in all_statuses - { const.STATUS_DD_NU, const.STATUS_DD_U }:
            self.assertInvalid("dd_e", dest)
        self.assertRequirements("dd_e", const.STATUS_DD_NU, ["intent", "sc_dmup", "keycheck", "am_ok"])
        self.assertRequirements("dd_e", const.STATUS_DD_U, ["intent", "sc_dmup", "keycheck", "am_ok"])

        for dest in all_statuses - { const.STATUS_DD_NU, const.STATUS_DD_U }:
            self.assertInvalid("dd_r", dest)
        self.assertRequirements("dd_r", const.STATUS_DD_NU, ["intent", "sc_dmup", "keycheck", "am_ok"])
        self.assertRequirements("dd_r", const.STATUS_DD_U, ["intent", "sc_dmup", "keycheck", "am_ok"])
