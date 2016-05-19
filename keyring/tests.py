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

test_signed_3D983C52EB85980C46A56090357312559D1E064B = """
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA512

I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.
I have read the Debian Machine Usage Policy and I accept them.
-----BEGIN PGP SIGNATURE-----
Comment: GPGTools - https://gpgtools.org

iQIcBAEBCgAGBQJXPXQkAAoJEDVzElWdHgZLibsQAIhlC5bf3h7zSNNV9m5KX1Id
oIG++wN8KNA3wTnv0EYNUQkJRdWWK0fIL8GLcmeA/MuhRTP3O+stv3mkIZkMPS9s
0fpFPj7F3EkrskXrAEd9hOfik6lqG4iv4iEYPl3PA4wJiX9zjV+6l2LxzfvRUrWU
rlkvBsqLkG+CcJ+wCKVYZRgS7PKOu3kEdvzFE0efqyWOPwEsrDoQ3Ax3KRe5W/pv
R5aiTiobKu//eObqjHNJGxsKkmXew7XMMcdzaQcre8e59WWdNUcTrfCg8sn4ykrk
5Bq6i1/FFcyEY1xqVeN54LRjqdlPSQN7YqXBLD9Gus2yhvyBA7MiDvJc1QsWB9tv
TcSVct9UKbKZs7BvRzvM7lm1J/y4dUVEq3fk5i8zNEFzsKWqgxYn9kHWrTB1MuNK
8rY3WZyxlTQdqjmWnu1jfpxbcuBrteHEZ2XwXjER9m0OXJahxk2t3YSAbr627UXH
G/loATZLoUNXFqeplHar1nIL7Kd/HDFznSN7N9M6NSzaBUgMlyhNSKa4SWYSuzlI
UBV4Alx80fkIG8pyWpcuHQtbyci6lW9P26VaK1w5OIkAIK/GrSkMeQ1BzilhGjV7
ayKnst/3J4IXlpye92gm+xNiISlDCL1aXa503AuKSC6zKsfaKqYtIiQZyBluSjTk
IJsNoeacVLqO2u0JYEwF
=pBe0
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
        test_fpr1 = "1793D6AB75663E6BF104953A634F4BD1E7AD5568"
        test_fpr2 = "66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB"

        encoded = kmodels.Key.objects.download(test_fpr1)
        self.assertTrue(encoded.startswith("-----BEGIN PGP PUBLIC KEY BLOCK-----"))
        key = kmodels.Key.objects.get_or_download(fpr=test_fpr1, body=encoded)
        self.assertEquals(key.fpr, test_fpr1)
        self.assertEquals(key.key, encoded)
        self.assertEquals(key.check_sigs, "")
        self.assertIsNone(key.check_sigs_updated)

        key.update_check_sigs()
        self.assertIsNotNone(key.check_sigs_updated)
        self.assertNotEquals(key.check_sigs, b"")

        results = key.keycheck()
        self.assertEquals(results.key.fpr, test_fpr1)
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

        # Test key signature verification
        self.assertEquals(key.verify(test_signed), "This is a test string\n")
        kmodels.Key.objects.test_preload(test_fpr2)
        key2 = kmodels.Key.objects.get_or_download(fpr=test_fpr2)
        with self.assertRaises(RuntimeError):
            key2.verify(test_signed)

    def test_keycheck(self):
        test_fpr = "1793D6AB75663E6BF104953A634F4BD1E7AD5568"
        kmodels.Key.objects.test_preload(test_fpr)
        c = Client()
        response = c.get(reverse("keyring_keycheck", kwargs={"fpr": test_fpr}))
        self.assertEquals(response.status_code, 200)
        decoded = json.loads(response.content)
        self.assertEquals(decoded["fpr"], test_fpr)
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

    def test_encoding(self):
        fpr = "3D983C52EB85980C46A56090357312559D1E064B"
        kmodels.Key.objects.test_preload(fpr)
        key = kmodels.Key.objects.get_or_download(fpr=fpr)
        results = key.keycheck()
        self.assertEquals(results.key.fpr, fpr)
        self.assertIsInstance(results.errors, set)
        self.assertIsInstance(results.uids, list)
        for u in results.uids:
            if u.uid.name == "Ondřej Nový <novy@ondrej.org>":
                uid = u
                break
        else:
            self.fail("'Ondřej Nový <novy@ondrej.org>' not found in {}".format(repr([x.uid.name for x in results.uids])))

        self.assertEquals(uid.uid.name, "Ondřej Nový <novy@ondrej.org>")
        self.assertIsInstance(uid.errors, set)
        self.assertIsInstance(uid.sigs_ok, list)
        self.assertIsInstance(uid.sigs_no_key, list)
        self.assertIsInstance(uid.sigs_bad, list)

        # Test key signature verification
        self.assertEquals(key.verify(test_signed_3D983C52EB85980C46A56090357312559D1E064B),
            "I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.\n"
            "I have read the Debian Machine Usage Policy and I accept them.\n")
        test_fpr2 = "66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB"
        kmodels.Key.objects.test_preload(test_fpr2)
        key2 = kmodels.Key.objects.get_or_download(fpr=test_fpr2)
        with self.assertRaises(RuntimeError):
            key2.verify(test_signed)

