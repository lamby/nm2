from backend.unittest import NamedObjects, PersonFixtureMixin
import backend.models as bmodels
import process.models as pmodels

test_fingerprint1 = "1793D6AB75663E6BF104953A634F4BD1E7AD5568"
test_fingerprint2 = "66B4DFB68CB24EBBD8650BC4F4B4B0CC797EBFAB"
test_fingerprint3 = "0EED77DC41D760FDE44035FF5556A34E04A3610B"

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

# Signed with key 1793D6AB75663E6BF104953A634F4BD1E7AD5568
test_fpr1_signed_valid_text_nonascii = """
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


# Signed with key 0EED77DC41D760FDE44035FF5556A34E04A3610B
test_fpr3_signed_valid_text = """
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA256

I agree to uphold the Social Contract and the Debian Free Software Guidelines in my Debian work.
I have read the Debian Machine Usage Policy and I accept them.
-----BEGIN PGP SIGNATURE-----
Version: GnuPG v2

iQIcBAEBCAAGBQJXPZKwAAoJEOjTeuLwn0hy1McP/iZPp6N/ng+P5jXGpuVoAJOa
Fn5b4RHAVZoQ+6k4NruN56bzn4NysAD4KMaMOOO5Wbu8Q+3CYlA1Kc6sVCHCTK47
34/oOszvW6WKD4Lf0H8KEiUcpdTMvVktiLjyCHlZDnnydWPG+72KzDm/TqoTxFW9
mFB1KIbYe2kJPV8yZOoxIEvmyrV4SgwZwG2FkdBn/0JFfJCbE7cXt0KKP0lUctka
ymB2mLLikXpJepd32ehUs15UAQZMbUSVbyLq28176og6lSWPVpEEeEdUmVuaii99
qNIKEA0k4UJPmgtJZxnPiGUgIMB9wRarnoZb2rAP0RhQ1lFYfIEz2tAMZ1o9c+Ia
5KEYnoLEHsF6nWZhrKKFm7TjaseQ5tcYCoZmG6pgraVnjdpUavH54mneQFmO5B7l
etrcCic0zb2/gDovjFPqJ2xDK+K0LOapUXrrLSOvdwB6tm3e7sGCSOZbibVpIrvC
WpgKnjrntfADnPx44xRS/RvAqr3TUUICbJq/czKr1+mDKwV/WKCYOWwe8GXRR0IR
uxODvexBbPuPeImQbpUVPvuIL7gyoxvdlNQwzKX12/GI5CZOEWx87MemRMB0r5oh
XD3vxTAcdhGDNK+LdTichQxp8nUs1IX5ziPP92jRXF2LjE58a9O4XC2vtEwm8wLm
kFBhaqNexUs/V1sIBuY5
=tMbR
-----END PGP SIGNATURE-----
"""


class ProcessFixtureMixin(PersonFixtureMixin):
    @classmethod
    def setUpClass(cls):
        super(ProcessFixtureMixin, cls).setUpClass()
        cls.amassignments = NamedObjects(pmodels.AMAssignment)
        cls.statements = NamedObjects(pmodels.Statement)

    @classmethod
    def tearDownClass(cls):
        cls.statements.delete_all()
        cls.amassignments.delete_all()
        super(ProcessFixtureMixin, cls).tearDownClass()

    def setUp(self):
        super(ProcessFixtureMixin, self).setUp()
        self.amassignments.refresh()
        self.statements.refresh()


def get_all_process_types():
    """
    Generate all valid (source_status, applying_for) pairs for all possible
    processes.
    """
    for src, tgts in list(bmodels.Person._new_status_table.items()):
        for tgt in tgts:
            yield src, tgt



