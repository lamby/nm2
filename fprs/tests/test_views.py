# coding: utf-8
"""
Test DM claim interface
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
from backend.models import Person, Fingerprint
from backend import const
from backend.unittest import PersonFixtureMixin
from keyring.models import Key

test_fingerprint1 = "1793D6AB75663E6BF104953A634F4BD1E7AD5568"
test_fingerprint2 = "66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB"

# Signed with key 1793D6AB75663E6BF104953A634F4BD1E7AD5568
test_fpr1_signed_invalid_text = """
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

# Signed with key 1793D6AB75663E6BF104953A634F4BD1E7AD5568
test_fpr1_signed_valid_text = """
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.
I have read the Debian Machine Usage Policy and I accept them.
-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1

iQIcBAEBCAAGBQJXPCbAAAoJEAPWVoyDcnWpmtYQAJo8r4Ve1xSYKs2s9MwAZLiD
q5XWRo9SFmIOyu7jq4giTGA5GMOFiGOMDHMWSNDnraVfhAZ2CrtwvyvaHcsYMDLb
kumcBqE2wYJNVMlgDX7celUMeeSeIVXvk1ef3/m0R2L0b/f+p/6/4IzaR3ZVCbkv
JwqZ7XJLH0YKih50fpnKjYnKEzVNOKGXcwm9I7XXJkl9a8c9TkC7IXnbHyL2AuZX
/kvOv+Y0EWXLEBgQx2PbxxZoM31nFIIa+MNLdz8dEOgc7g1aR8CCT0XyGTViL8W5
rrZSGMxdTXLPf3v+GqfehCUMCvy6/R4oqny2ijYVlaPFrMhPlpa7ydtgstySxc8Z
bCNFbSQM1ZSZUhcyFLhq5SbXW3T74jUHF0ApeM6n92erb02HDmv1uqsNBnFJCqdt
Zhg0mm1YPlAEPx7RSCwt0Zyu0Cuj/wK1d6YakWkxZwj5wkRvejsuMjcjWA5q/84I
zGoXT7GlqGdrvczrecoE1nzvqF8m5QXxOthaSjPqEviEde4YhQWxJfItULsLzGEb
OD+WdwaUol7byxcxmUIy60lFYsl2ryTvvxaRX1eUZtBkeeyP70SNqIgm+pbz2yba
0YW/mUIu3a+Dct/X/b05acQNRFcEWu0YWF6neBxR3Xd4cX1TJ2+9ICxSe2B8auxr
lsFwsnOvPjKD0iEMVmGe
=zlA9
-----END PGP SIGNATURE-----
"""

# Signed with key 66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB
test_fpr2_signed_valid_text = """
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.
I have read the Debian Machine Usage Policy and I accept them.
-----BEGIN PGP SIGNATURE-----
Version: GnuPG v1

iQIcBAEBCAAGBQJXPCcaAAoJEB5qw/OH8O2sbD8QAMrbXQYAGA/8EmXkSMKcAisk
jSqxkBDbnNeXn+Vso5aT/aVY/n63v/uDh2YDlz9Q4rC1GWS23KaQAf35spkyLCua
NSw3gbRJWByTuPxp+E3M2+9N56ZJGFwHAeatxbZJUeP88Dtsp7F+he9FaT2BUFCb
zYV9IbR8g47B8BDSTxjURWg34gVxsghUnYW6kYT8ATI1xls5zweiOt1UCe7UKVqo
PFNgaEPjdsuqE8pYIcLNjwx/adXjbXVsu3U7aYXCfZNZfi9FocCBUL2w0Ry8RqQa
tw/Ag6nQY7e7T8eIu3n49qVV9QarfiqB4JoaH9KTDZn6BHM+IgIxYbZabMVq/+9H
O0yeJGt/Pj1SISchDcDzebsXZfLl4HYhtncKwjLVwlPcV6Iopmw7uXklzOgD1xim
eqj0s84751kt/68TU3Hps/7PzQfCOfs2GZ4XCUzRcnluKJROBWX+xg3z3zEa0Luy
7Kn2Pq+AYNc0T9r6Ii4ioxraq3o/4G8mNCo6HVEFAC6jEejxyBjN3xFb5hAAKzPM
qNOSwQp380PzgE1L8eYcvNaUPgPqRVdPJzLX04NRsAyFgxPkBCo5V3WRSQpbEozi
vEKSopp/HEL4wBq8JYlvA0DuHTB7+X91XI6LreJQAe+6Jo07iuqmeZd9/pl1Anch
1hXsFK826L36Be03CwGL
=io+s
-----END PGP SIGNATURE-----
"""


class TestPersonFingerprints(PersonFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestPersonFingerprints, cls).setUpClass()
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)

    @classmethod
    def __add_extra_tests__(cls):
        # Anonymous cannot see or edit anyone's keys
        for person in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "fd", "dam"):
            cls._add_method(cls._test_get_forbidden, None, person)
            cls._add_method(cls._test_post_forbidden, None, person)

        # Only confirmed people with no entries in LDAP can see and edit their own keys
        for person in ("dc", "dm"):
            cls._add_method(cls._test_get_success, person, person)
            cls._add_method(cls._test_post_success, person, person)
        for person in ("pending", "dc_ga", "dm_ga", "dd_nu", "dd_u", "fd", "dam"):
            cls._add_method(cls._test_get_forbidden, person, person)
            cls._add_method(cls._test_post_forbidden, person, person)

        # active ams, fd and dam can see and edit the keys of anyone who is not in LDAP
        for visitor in ("am", "fd", "dam"):
            for visited in ("dc", "dm"):
                cls._add_method(cls._test_get_success, visitor, visited)
                cls._add_method(cls._test_post_success, visitor, visited)
        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u"):
            for visited in ("dc", "dm"):
                if visitor == visited: continue
                cls._add_method(cls._test_get_forbidden, visitor, visited)
                cls._add_method(cls._test_post_forbidden, visitor, visited)

    def _test_get_success(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.get(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        self.assertEquals(response.status_code, 200)

    def _test_post_success(self, visitor, visited):
        client = self.make_test_client(visitor)

        # Add one fingerprint
        response = client.post(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}), data={"fpr": test_fingerprint1})
        self.assertRedirectMatches(response, reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        fpr1 = Fingerprint.objects.get(fpr=test_fingerprint1)
        self.assertEquals(fpr1.is_active, True)
        self.assertEquals(fpr1.person, self.persons[visited])

        # Add a second one, it becomes the active one
        response = client.post(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}), data={"fpr": test_fingerprint2})
        self.assertRedirectMatches(response, reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        fpr2 = Fingerprint.objects.get(fpr=test_fingerprint2)
        self.assertEquals(fpr2.is_active, True)
        self.assertEquals(fpr2.person, self.persons[visited])

        fpr1 = Fingerprint.objects.get(fpr=test_fingerprint1)
        self.assertEquals(fpr1.is_active, False)

        # Activate the first one
        response = client.post(reverse("fprs_person_activate", kwargs={"key": self.persons[visited].lookup_key, "fpr": test_fingerprint1}))
        self.assertRedirectMatches(response, reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        fpr1 = Fingerprint.objects.get(fpr=test_fingerprint1)
        fpr2 = Fingerprint.objects.get(fpr=test_fingerprint2)
        self.assertEquals(fpr1.is_active, True)
        self.assertEquals(fpr2.is_active, False)

    def _test_get_forbidden(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.get(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}))
        self.assertPermissionDenied(response)

    def _test_post_forbidden(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.post(reverse("fprs_person_list", kwargs={"key": self.persons[visited].lookup_key}), data={"fpr": test_fingerprint1})
        self.assertPermissionDenied(response)
