"""
Code used to access Debian's LDAP
"""
from django.db import models
from django.conf import settings
import ldap3

LDAP_SERVER = getattr(settings, "LDAP_SERVER", "ldap://db.debian.org")

class Entry(object):
    def __init__(self):
        self.dn = None
        self.attrs = None
        self.uid = None

    def init(self, entry):
        """
        Init entry to point at these attributes
        """
        self.dn = entry.entry_get_dn()
        self.attrs = entry
        self.uid = entry["uid"][0]

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
    conn = ldap3.Connection(LDAP_SERVER, auto_bind=True)
    conn.search("dc=debian,dc=org", "(objectclass=inetOrgPerson)", ldap3.SUBTREE, attributes=ldap3.ALL_ATTRIBUTES)
    # Create the object only once
    entry = Entry()
    for e in conn.entries:
        entry.init(e)
        yield entry
