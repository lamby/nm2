# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase, Client
from django.core.urlresolvers import reverse
from . import models as kmodels
import json


class LookupTest(TestCase):
    def test_dd_u(self):
        fpr = next(kmodels.list_dd_u())
        self.assertTrue(kmodels.is_dd_u(fpr))
        self.assertFalse(kmodels.is_dm(fpr))
        self.assertFalse(kmodels.is_dd_nu(fpr))

    def test_dd_nu(self):
        fpr = next(kmodels.list_dd_nu())
        self.assertTrue(kmodels.is_dd_nu(fpr))
        self.assertFalse(kmodels.is_dm(fpr))
        self.assertFalse(kmodels.is_dd_u(fpr))

    def test_dm(self):
        fpr = next(kmodels.list_dm())
        self.assertTrue(kmodels.is_dm(fpr))
        self.assertFalse(kmodels.is_dd_u(fpr))
        self.assertFalse(kmodels.is_dd_nu(fpr))

class TestKeycheck(TestCase):
    def test_backend(self):
        encoded = kmodels.Key.objects.download("1793D6AB75663E6BF104953A634F4BD1E7AD5568")
        self.assertTrue(encoded.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"))
        key = kmodels.Key.objects.get_or_download(fpr="1793D6AB75663E6BF104953A634F4BD1E7AD5568", body=encoded)
        self.assertEquals(key.fpr, "1793D6AB75663E6BF104953A634F4BD1E7AD5568")
        self.assertEquals(key.key, encoded)
        self.assertEquals(key.check_sigs, "")
        self.assertIsNone(key.check_sigs_updated)

        key.update_check_sigs()
        self.assertIsNotNone(key.check_sigs_updated)
        self.assertNotEquals(key.check_sigs, "")

        results = key.keycheck()
        self.assertEquals(results.key.fpr, "1793D6AB75663E6BF104953A634F4BD1E7AD5568")
        self.assertIsInstance(results.errors, set)
        self.assertIsInstance(results.uids, list)
        for u in results.uids:
            if u.uid.name == "Enrico Zini <enrico@debian.org>":
                uid = u
                break
        else:
            self.fail("'Enrico Zini <enrico@debian.org>' not found in {}".format(repr([x.uid.name for x in results.uids])))

        self.assertEquals(uid.uid.name, "Enrico Zini <enrico@debian.org>")
        self.assertIsInstance(uid.errors, set)
        self.assertIsInstance(uid.sigs_ok, list)
        self.assertIsInstance(uid.sigs_no_key, list)
        self.assertIsInstance(uid.sigs_bad, list)

    def test_keycheck(self):
        c = Client()
        response = c.get(reverse("keyring_keycheck", kwargs={"fpr": "1793D6AB75663E6BF104953A634F4BD1E7AD5568"}))
        self.assertEquals(response.status_code, 200)
        decoded = json.loads(response.content)
        self.assertEquals(decoded["fpr"], "1793D6AB75663E6BF104953A634F4BD1E7AD5568")
        self.assertIsInstance(decoded["errors"], list)
        self.assertIsInstance(decoded["uids"], list)
        for k in decoded["uids"]:
            if k["name"] == "Enrico Zini <enrico@debian.org>":
                uid = k
                break
        else:
            self.fail("'Enrico Zini <enrico@debian.org>' not found in {}".format(repr([x["name"] for x in decoded["uids"]])))

        self.assertEquals(uid["name"], "Enrico Zini <enrico@debian.org>")
        self.assertIsInstance(uid["errors"], list)
        self.assertIsInstance(uid["sigs_ok"], list)
        self.assertIsInstance(uid["sigs_no_key"], int)
        self.assertIsInstance(uid["sigs_bad"], int)
