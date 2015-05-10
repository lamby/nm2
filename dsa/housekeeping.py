# nm.debian.org website housekeeping
#
# Copyright (C) 2012--2014  Enrico Zini <enrico@debian.org>
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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import django_housekeeping as hk
from django.db import transaction
from backend.housekeeping import MakeLink, Inconsistencies, Housekeeper
from . import models as dmodels
from backend import const
import backend.models as bmodels
import logging

log = logging.getLogger(__name__)

class ProgressFinalisationsOnAccountsCreated(hk.Task):
    """
    Update pending dm_ga processes after the account is created
    """
    DEPENDS = [MakeLink]

    @transaction.atomic
    def run_main(self, stage):
        # Get a lits of accounts from DSA
        dm_ga_uids = set()
        dd_uids = set()
        for entry in dmodels.list_people():
            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None:
                dd_uids.add(entry.uid)
            else:
                dm_ga_uids.add(entry.uid)

        # Check if pending processes got an account
        for proc in bmodels.Process.objects.filter(is_active=True):
            if proc.progress != const.PROGRESS_DAM_OK: continue
            finalised_msg = None

            if proc.applying_for == const.STATUS_DM_GA and proc.person.uid in dm_ga_uids:
                finalised_msg = "guest LDAP account created by DSA"
            if proc.applying_for in (const.STATUS_DD_NU, const.STATUS_DD_U) and proc.person.uid in dd_uids:
                finalised_msg = "LDAP account created by DSA"

            if finalised_msg is not None:
                old_status = proc.person.status
                proc.finalize(finalised_msg)
                log.info("%s: %s finalised: %s changes status %s->%s",
                         self.IDENTIFIER, self.hk.link(proc), proc.person.uid, old_status, proc.person.status)

class NewGuestAccountsFromDSA(hk.Task):
    """
    Create new Person entries for guest accounts created by DSA
    """
    DEPENDS = [MakeLink, Inconsistencies]

    @transaction.atomic
    def run_main(self, stage):
        for entry in dmodels.list_people():
            # Skip DDs
            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None: continue

            # Skip people we already know of
            if bmodels.Person.objects.filter(uid=entry.uid).exists(): continue

            # Skip people without fingerprints
            if entry.single("keyFingerPrint") is None: continue

            # Skip entries without emails (happens when running outside of the Debian network)
            if entry.single("emailForward") is None: continue

            # Check for fingerprint duplicates
            try:
                p = bmodels.Person.objects.get(fpr=entry.single("keyFingerPrint"))
                self.hk.inconsistencies.log_person(self, p,
                                                      "has the same fingerprint as LDAP uid {}".format(entry.uid),
                                                      ldap_uid=entry.uid)
                continue
            except bmodels.Person.DoesNotExist:
                pass

            p = bmodels.Person.objects.create_user(
                cn=entry.single("cn"),
                mn=entry.single("mn") or "",
                sn=entry.single("sn") or "",
                email=entry.single("emailForward"),
                uid=entry.uid,
                fpr=entry.single("keyFingerPrint"),
                status=const.STATUS_DC_GA,
                audit_author=self.hk.housekeeper.user,
                audit_notes="created new guest account entry from LDAP",
            )
            log.info("%s (guest account only) imported from LDAP", self.hk.link(p))

class CheckLDAPConsistency(hk.Task):
    """
    Show entries that do not match between LDAP and our DB
    """
    DEPENDS = [MakeLink, Inconsistencies, Housekeeper]

    def run_main(self, stage):
        # Prefetch people and index them by uid
        people_by_uid = dict()
        for p in bmodels.Person.objects.all():
            if p.uid is None: continue
            people_by_uid[p.uid] = p

        for entry in dmodels.list_people():
            try:
                person = bmodels.Person.objects.get(uid=entry.uid)
            except bmodels.Person.DoesNotExist:
                fpr = entry.single("keyFingerPrint")
                if fpr:
                    self.hk.inconsistencies.log_fingerprint(self, fpr,
                                                               "is in LDAP as {} but not in our db".format(entry.uid),
                                                               ldap_uid=entry.uid)
                else:
                    log.warning("%s: person %s exists (without fingerprint) in LDAP, but not in our db", self.IDENTIFIER, entry.uid)
                continue

            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None:
                if person.status not in (const.STATUS_DD_U, const.STATUS_DD_NU):
                    self.hk.inconsistencies.log_person(self, person,
                                                          "has gidNumber 800 and a key, but the db has state {}".format(person.status),
                                                          dsa_status="dd")

            email = entry.single("emailForward")
            if email != person.email:
                if email is not None:
                    log.info("%s: %s changing email from %s to %s (source: LDAP)",
                             self.IDENTIFIER, self.hk.link(person), person.email, email)
                    person.email = email
                    person.save(audit_author=self.hk.housekeeper.user, audit_notes="updated email from LDAP")
                # It gives lots of errors when run outside of the debian.org
                # network, since emailForward is not exported there, and it has
                # no use case I can think of so far
                #
                # else:
                #     log.info("%s: %s has email %s but emailForward is empty in LDAP",
                #              self.IDENTIFIER, self.hk.link(person), person.email)
