# nm.debian.org website maintenance
#
# Copyright (C) 2012  Enrico Zini <enrico@debian.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.core.management.base import BaseCommand, CommandError
import django.db
from django.db import connection, transaction
from django.conf import settings
import optparse
import sys
import os
import re
import logging
import datetime
from backend import models as bmodels
from backend import const

log = logging.getLogger(__name__)

def lookup_person(s):
    if s.endswith("@debian.org"):
        return bmodels.Person.objects.get(uid=s[:-11])
    elif '@' in s:
        return bmodels.Person.objects.get(email=s)
    elif re.match(r"(?:0x)?[A-F0-9]{16}", s):
        if s.startswith("0x"): s = s[2:]
        return bmodels.Person.objects.get(fpr__endswith=s)
    elif re.match(r"[A-F0-9]{40}", s):
        return bmodels.Person.objects.get(fpr__endswith=s)
    else:
        return bmodels.Person.lookup(s)


class Command(BaseCommand):
    help = 'Change the fingerprint of a person'
    args = "person_key new_fpr"

    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("--rt", action="store", default=None, help="RT ticket number"),
        optparse.make_option("--author", action="store", default=None, help="Author"),
    )

    def handle(self, person, fpr, rt=None, author=None, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        # Validate input

        # Person
        person = lookup_person(person)
        log.info("Person: %s", person.lookup_key)

        # New fingerprint
        if fpr == "revoked":
            fpr = None
            log.info("Key has been revoked.")
        else:
            fpr = fpr.replace(" ", "")
            fpr = fpr.upper()
            if len(fpr) != 40:
                log.error("Fingerprint %s is not 40 characters long", fpr)
                sys.exit(1)

            if not re.match("^[0-9A-F]+", fpr):
                log.error("Fingerprint %s contains invalid characters", fpr)
                sys.exit(1)
            log.info("New fingerprint: %s", fpr)

        # RT number
        if not rt:
            rt = raw_input("RT issue number: ")
            if not rt:
                rt = None
            else:
                rt = rt.lstrip("#")
        if not rt:
            log.info("RT: not specificed")
        else:
            log.info("RT: #%s", rt)

        # Author
        if not author:
            author = raw_input("Author: ")
        author = lookup_person(author)
        log.info("Author: %s", author.lookup_key)

        if fpr is None:
            if rt:
                audit_notes = "Key revoked, rt#{}".format(rt)
            else:
                audit_notes = "Key revoked"
        else:
            if rt:
                audit_notes = "Key replaced, rt#{}".format(rt)
            else:
                audit_notes = "Key replaced, rt unknown".format(rt)

        person.fpr = fpr
        person.save(audit_author=author, audit_notes=audit_notes)
        log.info("Saved")
