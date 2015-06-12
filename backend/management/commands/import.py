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
import os
import re
import sys
import logging
import json
import datetime
from backend import models as bmodels
from backend import const

log = logging.getLogger(__name__)

def parse_datetime(s):
    if s is None: return None
    return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

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

class Importer(object):
    def __init__(self, author):
        # Audit author
        self.author = lookup_person(author)
        # Key->Person mapping
        self.people = dict()
        # Key->AM mapping
        self.ams = dict()

    def import_person(self, key, info):
        """
        Import Person and AM objects, caching them in self.people and self.ams
        """
        p = bmodels.Person(
            username=info["username"],
            cn=info["cn"],
            mn=info["mn"],
            sn=info["sn"],
            email=info["email"],
            uid=info["uid"],
            fpr=info["fpr"],
            status=info["status"],
            status_changed=parse_datetime(info["status_changed"]),
            created=parse_datetime(info["created"]),
            fd_comment=info["fd_comment"],
        )
        p.save(audit_author=self.author, audit_notes="imported from json database export")
        self.people[key] = p

        aminfo = info["am"]
        if aminfo:
            am = bmodels.AM(
                person=p,
                slots=aminfo["slots"],
                is_am=aminfo["is_am"],
                is_fd=aminfo["is_fd"],
                is_dam=aminfo["is_dam"],
                is_am_ctte=aminfo["is_am_ctte"],
                created=parse_datetime(aminfo["created"]),
            )
            am.save()
            self.ams[key] = am

    def import_process(self, person, info):
        """
        Import a process for the given person
        """
        # Create process
        pr = bmodels.Process(
            person=person,
            applying_as=info["applying_as"],
            applying_for=info["applying_for"],
            progress=info["progress"],
            archive_key=info["archive_key"],
            is_active=info["is_active"],
        )
        if info["manager"]:
            pr.manager = self.ams[info["manager"]]
        pr.save()

        # Add advocates
        for a in info["advocates"]:
            pr.advocates.add(self.people[a])

        # Add log
        for li in info["log"]:
            l = bmodels.Log(
                process=pr,
                progress=li["progress"],
                logdate=parse_datetime(li["logdate"]),
                logtext=li["logtext"],
            )

            if li["changed_by"]:
                l.changed_by = self.people[li["changed_by"]]
            l.save()

    @transaction.atomic
    def import_people(self, people):
        count_people = 0
        count_procs = 0

        # Pass 1: import people and AMs
        for info in people:
            try:
                if count_people and count_people % 300 == 0:
                    log.info("%d people imported", count_people)
                self.import_person(info["key"], info)
                count_people += 1
            except:
                import json
                log.info("Offending record at pass 1: %s", json.dumps(info, indent=2))
                raise

        # Pass 2: import processes and logs
        for info in people:
            try:
                person = self.people[info["key"]]
                for proc in info["processes"]:
                    if count_procs and count_procs % 300 == 0:
                        log.info("%d processes imported", count_procs)
                    self.import_process(person, proc)
                    count_procs += 1
            except:
                import json
                log.info("Offending record at pass 2: %s", json.dumps(info, indent=2))
                raise

        return dict(
            people=count_people,
            procs=count_procs,
        )


class Command(BaseCommand):
    help = 'Import a JSON database dump'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("--ldap", action="store", default="ldap://db.debian.org", help="LDAP server to use. Default: %default"),
        optparse.make_option("--author", action="store", default=os.environ("USER"), help="user to use as author for the import. Default: %default"),
        #l = ldap.initialize("ldap://localhost:3389")
    )

    def handle(self, *fnames, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        if not fnames:
            print >>sys.stderr, "please provide a JSON dump file name"
            sys.exit(1)

        importer = Importer(author=opts["author"])
        for fname in fnames:
            with open(fname) as fd:
                stats = importer.import_people(json.load(fd))
            log.info("%s: imported %d people and %d processes", fname, stats["people"], stats["procs"])
