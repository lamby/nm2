"""
Code used to access Debian's LDAP
"""

from django.db import models
from django.conf import settings
try:
    import ldap
except ImportError:
    import ldap3 as ldap

LDAP_SERVER = getattr(settings, "LDAP_SERVER", "ldap://db.debian.org")

class Entry(object):
    def __init__(self):
        self.dn = None
        self.attrs = None
        self.uid = None

    def init(self, dn, attrs):
        """
        Init entry to point at these attributes
        """
        self.dn = dn
        self.attrs = attrs
        self.uid = attrs["uid"][0]

    def single(self, name):
        """
        Return a single value for a LDAP attribute
        """
        if name not in self.attrs:
            return None
        val = self.attrs[name]
        if not val:
            return None
        return val[0]

    @property
    def is_dd(self):
        return "Debian" in self.attrs["supplementaryGid"]

    @property
    def is_guest(self):
        return "guest" in self.attrs["supplementaryGid"]

def list_people():
    search_base = "dc=debian,dc=org"
    l = ldap.initialize(LDAP_SERVER)
    l.simple_bind_s("","")
    # Create the object only once
    entry = Entry()
    for dn, attrs in l.search_s(search_base, ldap.SCOPE_SUBTREE, "objectclass=inetOrgPerson"):
        entry.init(dn, attrs)
        yield entry
