# nm.debian.org website maintenance
#
# Copyright (C) 2012--2015  Enrico Zini <enrico@debian.org>
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
from django.utils.timezone import utc
from django.db import connection, transaction
from django.conf import settings
import optparse
import sys
import os
import re
import readline
import logging
import dateutil.parser
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

def ask(prompt, prefill=None):
    if prefill:
        readline.set_startup_hook(lambda: readline.insert_text(prefill))
        try:
            return raw_input(prompt)
        finally:
            readline.set_startup_hook()
    else:
        return raw_input(prompt)

def parse_datetime(s):
    if s is None: return None
    s = s.strip()
    dt = dateutil.parser.parse(s)
    # If we get an aware datetime, convert to utc and make it naive, since all
    # timestamps in nm.debian.org are UTC
    if dt.tzinfo:
        dt = dt.astimezone(utc)
        dt = dt.replace(tzinfo=None)
    return dt

def validate_new_fingerprint(person, fpr):
    if fpr == "revoked":
        return None
    else:
        fpr = fpr.replace(" ", "")
        fpr = fpr.upper()
        if len(fpr) != 40:
            log.error("Fingerprint %s is not 40 characters long", fpr)
            sys.exit(1)

        if not re.match("^[0-9A-F]+", fpr):
            log.error("Fingerprint %s contains invalid characters", fpr)
            sys.exit(1)

        if person.fpr != fpr:
            try:
                existing = bmodels.Person.objects.get(fpr=fpr)
            except bmodels.Person.DoesNotExist:
                existing = None

            if existing is not None:
                log.error("Fingerprint %s already exists in the database as %s", fpr, existing.lookup_key)
                sys.exit(1)

        return fpr

def validate_new_status(status):
    if status not in const.ALL_STATUS_DESCS:
        log.error("Status %s is unsupported", status)
        sys.exit(1)
    return status

class Command(BaseCommand):
    help = 'Change information about a person (use an empty string to set to NULL)'
    args = "person"

    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        #optparse.make_option("--cn", action="store", help="Set first name"),
        #optparse.make_option("--mn", action="store", help="Set middle name"),
        #optparse.make_option("--sn", action="store", help="Set last name"),
        #optparse.make_option("--email", action="store", help="Set email address"),
        #optparse.make_option("--uid", action="store", help="Set Debian uid"),
        optparse.make_option("--fpr", action="store", help="Set OpenPGP key fingerprint"),
        optparse.make_option("--status", action="store", help="Set status"),
        optparse.make_option("-t", "--status-changed", action="store", help="Set date when the status last changed"),
        #optparse.make_option("--fd-comment", action="store", help="Set FD comment"),
        #optparse.make_option("--created", action="store", help="Set date when the person record was created"),
        optparse.make_option("--rt", action="store", help="RT issue number"),
        optparse.make_option("-m", "--message", action="store", help="Message to use in audit notes"),
        optparse.make_option("-f", "--force", action="store", help="Skip interactive confirmations"),
        optparse.make_option("--author", action="store", default=None, help="Author"),
    )

    def handle(self, person, fpr=None, status=None, status_changed=None, rt=None, message=None, force=None, author=None, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        # Validate input
        person = lookup_person(person)
        log.info("Person: %s", person.lookup_key)

        # Author
        if not author and not force:
            author = ask("Author: ")
        author = lookup_person(author)
        log.info("Author: %s", author.lookup_key)

        # Fingerprint
        if not fpr and not force:
            fpr = ask("New fingerprint ('revoked' for removing the key): ", person.fpr or "")
        new_fpr = validate_new_fingerprint(person, fpr)

        # Status
        if not status and not force:
            status = ask("New status: ", person.status)
        new_status = validate_new_status(status)

        if person.status != new_status:
            if not status_changed and not force:
                status_changed = ask("Status change date[time]: ", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            new_status_changed = parse_datetime(status_changed)

        changed = False

        if person.fpr != new_fpr:
            log.info("Changing fingerprint from %s to %s", person.fpr, new_fpr)
            person.fpr = new_fpr
            changed = True

        if person.status != new_status:
            log.info("Changing status from %s to %s, in date %s", person.status, new_status, new_status_changed)
            person.status = new_status
            person.status_changed = new_status_changed
            changed = True

        if changed:
            # RT number
            if not rt and not force:
                rt = ask("RT issue number: ")
                if not rt:
                    rt = None
                else:
                    rt = rt.lstrip("#")

            # Audit notes
            if rt:
                audit_notes = "RT #{}".format(rt)
            else:
                audit_notes = "Manual database update"
            if not force:
                audit_notes = ask("Audit notes: ", audit_notes)

            person.save(audit_author=author, audit_notes=audit_notes)
            log.info("Saved")
        else:
            log.info("Nothing to do")


        #for field in ("cn", "mn", "sn", "email", "uid", "fpr", "status", "fd_comment"):
        #    val = opts[field]
        #    if val is None: continue
        #    if val == "": val = None
        #    setattr(p, field, val)
        #for field in ("status_changed", "created"):
        #    val = opts[field]
        #    if val is None: continue
        #    val = parse_datetime(val)
        #    setattr(p, field, val)

        #p.save()
