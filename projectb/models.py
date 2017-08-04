"""
Functions used to access the dak database used by ftp-master.

We mainly use it to make a list of DMs
"""

from django.db import models
from django.db import connections
from django.conf import settings

import datetime
import sys
import os, os.path
import re
import time
import subprocess
import pickle
import psycopg2
import logging

log = logging.getLogger(__name__)

def cursor():
    """
    Return a Django sane-dbapi-style db cursor to the projectb database
    """
    return connections['projectb'].cursor()


CACHE_FILE="make-dm-list.cache"

KEYRINGS = getattr(settings, "KEYRINGS", "/srv/keyring.debian.org/keyrings")

# Reused from dak, to exactly follow what they do
#
# <Culus> 'The standard sucks, but my tool is supposed to interoperate
#          with it. I know - I'll fix the suckage and make things
#          incompatible!'
re_parse_maintainer = re.compile(r"^\s*(\S.*\S)\s*\<([^\>]+)\>")
def fix_maintainer(maintainer):
    """
    Parses a Maintainer or Changed-By field and returns (name, email)
    """
    maintainer = maintainer.strip()
    if not maintainer:
        return ('', '')

    if maintainer.find("<") == -1:
        email = maintainer
        name = ""
    elif (maintainer[0] == "<" and maintainer[-1:] == ">"):
        email = maintainer[1:-1]
        name = ""
    else:
        m = re_parse_maintainer.match(maintainer)
        if not m:
            raise ValueError("Doesn't parse as a valid Maintainer field.")
        name = m.group(1)
        email = m.group(2)

    if email.find("@") == -1 and email.find("buildd_") != 0:
        raise ValueError("No @ found in email address part.")

    return name, email

def read_gpg():
    "Read DM info from the DB keyring"
    keyring = os.path.join(KEYRINGS, "debian-maintainers.gpg")
    re_email = re.compile(r"<(.+?)>")
    re_unmangle = re.compile(r"\\x([0-9A-Fa-f][0-9A-Fa-f])")
    proc = subprocess.Popen(["/usr/bin/gpg", "--no-permission-warning", "--with-colons", "--with-fingerprint", "--no-default-keyring", "--keyring", keyring, "--list-keys"], stdout=subprocess.PIPE)
    rec = None
    for line in proc.stdout:
        if line.startswith("pub:"):
            if rec is not None: yield rec
            row = line.strip().split(":")
            # Unmangle gpg output
            uid = re_unmangle.sub(lambda mo: chr(int(mo.group(1), 16)), row[9])
            uid = uid.decode("utf-8", "replace")
            mo = re_email.search(uid)
            if mo:
                email = mo.group(1)
            else:
                email = uid
            rec = dict(sz=int(row[2]), id=row[4], date=row[5], uid=uid, email=email)
        elif line.startswith("fpr:"):
            row = line.strip().split(":")
            rec["fpr"] = row[9]
    if rec is not None: yield rec
    if proc.wait() != 0:
        raise RuntimeError("gpg exited with error {}".format(proc.returncode))
