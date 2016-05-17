# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase, Client
from django.core.urlresolvers import reverse
from . import models as kmodels
import io
import json

test_signed = """
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

This is a test string
-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1

iQIcBAEBCAAGBQJXO5CSAAoJEAPWVoyDcnWpArgP/3EBdxc4gu5iQX7HQdmc93p8
4BSd/6evtqNtSJehQtZIRiJIqP3pcKDgnWQ+PqkEDkrMnlp7hQyLLXqENcwU54l1
Pj3OiS4O5EMkF4rvteIajX/GXO/qou7+zJYny/DBJUaDg9Dem7Zr8TzVoQsEMOcs
3VPdKQTZHOYcKvCoBMv34ZD9cKRsLACt7x+MTQIIZg62oaaCoHEraT6KSkkcn28P
IC5LTZaMRJm8di3zpxxHpM6RHhJpLEjmZNgRFaGPKam9ba7OeQy96tgTRYs4yKvx
gO2zcDLoXC2s/vhF7A0VTbg7GGfvFlQpRr6tempK39UbUaGGDlaPkyYeRdIXhxoP
yOUZS+ejGI2lxiECYWR5hVUO+Py+sHM2FWwphaRF226yPdq3bIIobQ22FgDaEiPw
bWrRVNG35TRJYSn4xb3XovIrcY8rmgOV5gSCpZh4Iy/92PuVg5gp1y2fFHp42PrC
OQqk1JXE1PHAX6ZqWQJW3MUcyBqKyEnz5Ylez7yyDqCWobey/s62dybYtdtQ/aZO
xBT0EeU3M5W1yBzEWVCLUUBIsmzFI+uUqZwO20XWmdMYFtWyvxmVQ9JCXo3ncWwf
a+KEa+sSqB8ZN0fIzGLL2uOOPdQGoVHxnObCJ5gBKjZ73JajY3cfLysY0UW45/eh
+5lxImpwauF6Tf+pMHKD
=86an
-----END PGP SIGNATURE-----
"""

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
        self.assertNotEquals(key.check_sigs, b"")

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

        self.assertEquals(key.verify(test_signed), "This is a test string\n")

        with io.open("test_data/F4B4B0CC797EBFAB.txt", "rt") as fd:
            key1 = kmodels.Key.objects.get_or_download(fpr="66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB", body=fd.read())
        with self.assertRaises(RuntimeError):
            key1.verify(test_signed)

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
