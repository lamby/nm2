# coding: utf-8




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
        self.assertEqual(key.fpr, test_fpr1)
        self.assertEqual(key.key, encoded)
        self.assertEqual(key.check_sigs, "")
        self.assertIsNone(key.check_sigs_updated)

        key.update_check_sigs()
        self.assertIsNotNone(key.check_sigs_updated)
        self.assertNotEqual(key.check_sigs, b"")

        results = key.keycheck()
        self.assertEqual(results.key.fpr, test_fpr1)
        self.assertIsInstance(results.errors, set)
        self.assertIsInstance(results.uids, list)
        for u in results.uids:
            if u.uid.name == "Enrico Zini <enrico@debian.org>":
                uid = u
                break
        else:
            self.fail("'Enrico Zini <enrico@debian.org>' not found in {}".format(repr([x.uid.name for x in results.uids])))

        self.assertEqual(uid.uid.name, "Enrico Zini <enrico@debian.org>")
        self.assertIsInstance(uid.errors, set)
        self.assertIsInstance(uid.sigs_ok, list)
        self.assertIsInstance(uid.sigs_no_key, list)
        self.assertIsInstance(uid.sigs_bad, list)

        # Test key signature verification
        self.assertEqual(key.verify(test_signed), "This is a test string\n")
        kmodels.Key.objects.test_preload(test_fpr2)
        key2 = kmodels.Key.objects.get_or_download(fpr=test_fpr2)
        with self.assertRaises(RuntimeError):
            key2.verify(test_signed)

    def test_keycheck(self):
        test_fpr = "1793D6AB75663E6BF104953A634F4BD1E7AD5568"
        kmodels.Key.objects.test_preload(test_fpr)
        c = Client()
        response = c.get(reverse("keyring_keycheck", kwargs={"fpr": test_fpr}))
        self.assertEqual(response.status_code, 200)
        decoded = json.loads(response.content)
        self.assertEqual(decoded["fpr"], test_fpr)
        self.assertIsInstance(decoded["errors"], list)
        self.assertIsInstance(decoded["uids"], list)
        for k in decoded["uids"]:
            if k["name"] == "Enrico Zini <enrico@debian.org>":
                uid = k
                break
        else:
            self.fail("'Enrico Zini <enrico@debian.org>' not found in {}".format(repr([x["name"] for x in decoded["uids"]])))

        self.assertEqual(uid["name"], "Enrico Zini <enrico@debian.org>")
        self.assertIsInstance(uid["errors"], list)
        self.assertIsInstance(uid["sigs_ok"], list)
        self.assertIsInstance(uid["sigs_no_key"], int)
        self.assertIsInstance(uid["sigs_bad"], int)

    def test_encoding(self):
        fpr = "3D983C52EB85980C46A56090357312559D1E064B"
        kmodels.Key.objects.test_preload(fpr)
        key = kmodels.Key.objects.get_or_download(fpr=fpr)
        results = key.keycheck()
        self.assertEqual(results.key.fpr, fpr)
        self.assertIsInstance(results.errors, set)
        self.assertIsInstance(results.uids, list)
        for u in results.uids:
            if u.uid.name == "Ondřej Nový <novy@ondrej.org>":
                uid = u
                break
        else:
            self.fail("'Ondřej Nový <novy@ondrej.org>' not found in {}".format(repr([x.uid.name for x in results.uids])))

        self.assertEqual(uid.uid.name, "Ondřej Nový <novy@ondrej.org>")
        self.assertIsInstance(uid.errors, set)
        self.assertIsInstance(uid.sigs_ok, list)
        self.assertIsInstance(uid.sigs_no_key, list)
        self.assertIsInstance(uid.sigs_bad, list)

        # Test key signature verification
        self.assertEqual(key.verify(test_signed_3D983C52EB85980C46A56090357312559D1E064B),
            "I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.\n"
            "I have read the Debian Machine Usage Policy and I accept them.\n")
        test_fpr2 = "66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB"
        kmodels.Key.objects.test_preload(test_fpr2)
        key2 = kmodels.Key.objects.get_or_download(fpr=test_fpr2)
        with self.assertRaises(RuntimeError):
            key2.verify(test_signed)


class TestVerify(TestCase):
    def test_verify(self):
        text = """
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

þiş is a têst message úsed while debügging nm.debiån.ørg ♥
-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1

iQIcBAEBCAAGBQJXVA4MAAoJEAPWVoyDcnWps0gP/iyWqN68kLsqVOs/pPJsQlLO
DT8XGCHukzw4O9mAzM3pj2TUKql+4GrePCB7Sia8zIOkMWNFIlOKN1PRE4D3fGeC
zbNdQddP+rdcjCU41+83F8XuWjpuqtT83vDww/iViyYuxgflx14Rj77yE6RZOYpH
wgQssQ15ykz7z2kYBxcfNSdQBGqdQ4PEc3cwn94yAZexZ6A/+R4w3gzF1VA5ldGn
MJKR1XT3NH2vnrQMW7ffE030ELiF7rdE3b77LPwtlqFtWqhPnZg+QmyLQoMRst+s
TWS0optG28zkH320yQnkl8UahEAXJiaW2IFG812O+M0/zYa9Tc/Z8cRpPjkPunvO
hZglwt7Z3f2edpT91L7yU1WfJzKXPwYLPYJRXp+ZYTeSiaPLftHIiN60ruGO0o20
E3yzCUISESYKERHc8eJYJub5MV5fz9z8q35yggftR8LT5pspsUEtqJzvjPB0VOwO
gtPwxxJr2pmU/exB7mAhd05Qq1C2YmLNhfD6OWpWLZJ7MumRZK4TVBv4XQ+FgLlT
QHfXETET8c9RHTxay9E5HC4VdNrmeN5R5cOKnzkGik6NNsQXs42cvlqFGhAfaL/8
BIdcCviy3rEnqRSc+sXQM6kpBGY+ZC5oejNjsgOJFUyAF3Yqgt5hqQZ8ii2SF5V3
Kbul7r6fmKMmeViXW8TS
=WzDm
-----END PGP SIGNATURE-----
"""
        test_fpr = "1793D6AB75663E6BF104953A634F4BD1E7AD5568"
        kmodels.Key.objects.test_preload(test_fpr)
        key = kmodels.Key.objects.get_or_download(fpr=test_fpr)
        decoded = key.verify(text)
        self.assertEqual(decoded, "þiş is a têst message úsed while debügging nm.debiån.ørg ♥\n")


class TestVerifyMIME(TestCase):
    def test_verify(self):
        with open("test_data/announce.mbox", "rb") as fd:
            text = fd.read()
        test_fpr = "1793D6AB75663E6BF104953A634F4BD1E7AD5568"
        kmodels.Key.objects.test_preload(test_fpr)
        key = kmodels.Key.objects.get_or_download(fpr=test_fpr)
        key.verify(text)

        with self.assertRaises(RuntimeError):
            key.verify(text.replace("NM process", "MN process"))


class TestParsePubFingerprints(TestCase):
    INPUT="""pub:-:4096:1:E5EC4AC9BD627B05:1415763159:1510628067::-:::scESC:::::::
fpr:::::::::B7A15F455B287F384174D5E9E5EC4AC9BD627B05:
uid:-::::1479092073::6585BDD130E2072419D0B256B410404B9C3B14C1::Donald Norwood <donald@debian.org>:
uid:-::::1479092073::B2F3C15935E51099250E412F9BF952D9F1645FBD::Donald Norwood <dnorwood@portalus.com>:
uid:-::::1479092073::BE0CD36B3EA9AC2DD784702F78E3E28E1828AF8B::Donald Norwood <dnorwood@portalias.net>:
sub:-:4096:1:26D3DdD16681E7552:1415763159:1510628097:::::e::::::
fpr:::::::::4A85A16dCD19249414D52BD6526D3DD16681E7552:
sub:r:4096:1:0F72B54C4E24CB3C:1415763650::::::e::::::
fpr:::::::::1EC0F8B8148B5F9F6375BA790F72B54C4E24CB3C:
sub:r:4096:1:578DD73DA3680393:1415825064::::::e::::::
fpr:::::::::389D8173D7BEA884D4961115578DD73DA3680393:
pub:-:4096:1:F22674467E4AF4A3:1405269788:1507051872::-:::scESC:::::::
fpr:::::::::445E3AD036903F47E19B37B2F22674467E4AF4A3:
uid:-::::1475515877::134619D9BCC9E05ED745F1B9E1F27065CFBE9C1D::Laura Arjona Reina <larjona@debian.org>:
uid:-::::1475515902::6EFD666072E40819975D493B50FF417E7FABDFEA::Laura Arjona Reina <larjona@fsfe.org>:
uid:-::::1475515902::861D0BDB8B4B6DA505245D754F027917F8F91293::Laura Arjona Reina <larjona99@gmail.com>:
uid:-::::1475515901::F30EB75DFE4DFBE6117791330DBE816DDAECF145::Laura Arjona Reina <larjona@larjona.net>:
uid:-::::1475515902::736F76B9B199686160E5FDCD5D2458C41826B6A4::Laura Arjona Reina <laura.arjona@upm.es>:
"""
    def test_parse(self):
        fprs = [x for x in kmodels._parse_pub_fingerprints(self.INPUT.splitlines())]
        self.assertEqual(fprs, ["B7A15F455B287F384174D5E9E5EC4AC9BD627B05", "445E3AD036903F47E19B37B2F22674467E4AF4A3"])
