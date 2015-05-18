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
from backend.housekeeping import MakeLink, Housekeeper
from . import models as dmodels
from backend import const
import backend.models as bmodels
import logging

log = logging.getLogger(__name__)

class ProgressFinalisationsOnAccountsCreated(hk.Task):
    """
    Update pending dm_ga processes after the account is created
    """
    DEPENDS = [MakeLink, Housekeeper]

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
                proc.finalize(finalised_msg, audit_author=self.hk.housekeeper.user, audit_notes="DSA created the account: finalising process")
                log.info("%s: %s finalised: %s changes status %s->%s",
                         self.IDENTIFIER, self.hk.link(proc), proc.person.uid, old_status, proc.person.status)

class NewGuestAccountsFromDSA(hk.Task):
    """
    Create new Person entries for guest accounts created by DSA
    """
    DEPENDS = [MakeLink]

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

            try:
                fpr_person = bmodels.Person.objects.get(fpr=entry.single("keyFingerPrint"))
            except bmodels.Person.DoesNotExist:
                fpr_person = None

            try:
                email_person = bmodels.Person.objects.get(email=entry.single("emailForward"))
            except bmodels.Person.DoesNotExist:
                email_person = None

            if fpr_person and email_person and fpr_person.pk != email_person.pk:
                log.warn("%s: LDAP has new uid %s which corresponds to two different users in our db: %s (by fingerprint %s) and %s (by email %s)",
                         self.IDENTIFIER, entry.uid,
                         self.hk.link(fpr_person), entry.single("keyFingerPrint"),
                         self.hk.link(email_person), entry.single("emailForward"))
                continue

            # Now we either have fpr_person or email_person or none of them, or
            # both and they are the same: from now on we can work with only one
            # person
            person = fpr_person if fpr_person else email_person

            if not person:
                # New DC_GA
                person = bmodels.Person.objects.create_user(
                    cn=entry.single("cn"),
                    mn=entry.single("mn") or "",
                    sn=entry.single("sn") or "",
                    email=entry.single("emailForward"),
                    uid=entry.uid,
                    fpr=entry.single("keyFingerPrint"),
                    status=const.STATUS_DC_GA,
                    username="{}@invalid.example.org".format(entry.uid),
                    audit_author=self.hk.housekeeper.user,
                    audit_notes="created new guest account entry from LDAP",
                )
                log.info("%s: %s (guest account only) imported from LDAP", self.IDENTIFIER, self.hk.link(person))
            else:
                if person.status in (const.STATUS_DC_GA, const.STATUS_DM_GA):
                    # We already know about it: nothing to do
                    pass
                if person.status in (const.STATUS_DC, const.STATUS_DM):
                    if person.status == const.STATUS_DM:
                        # DM that becomes DM_GA (acquires uid)
                        person.status = const.STATUS_DM_GA
                    else:
                        # DC that becomes DC_GA (acquires uid)
                        person.status = const.STATUS_DC_GA
                    person.uid = entry.uid
                    audit_notes = "entry found in LDAP, adding 'guest account' status"
                    person.save(audit_author=self.hk.housekeeper.user, audit_notes=audit_notes)
                    log.info("%s: %s %s", self.IDENTIFIER, self.hk.link(person), audit_notes)
                else:
                    # New uid on a status that is not supposed to have one:
                    # just warn about it
                    log.warn("%s: LDAP has new uid %s for person %s, which already has status %s in our database",
                             self.IDENTIFIER, entry.uid, self.hk.link(person), const.ALL_STATUS_DESCS[person.status])


class CheckLDAPConsistency(hk.Task):
    """
    Show entries that do not match between LDAP and our DB
    """
    DEPENDS = [MakeLink, Housekeeper]

    def run_main(self, stage):
        # Prefetch people and index them by uid
        people_by_uid = dict()
        for p in bmodels.Person.objects.all():
            if p.uid is None: continue
            people_by_uid[p.uid] = p

        for entry in dmodels.list_people():
            person = people_by_uid.get(entry.uid, None)

            if person is None:
                fpr = entry.single("keyFingerPrint")
                if fpr:
                    log.warn("%s: %s has fingerprint %s and gid %s in LDAP, but is not in our db",
                             self.IDENTIFIER, entry.uid, fpr, entry.single("gidNumber"))
                else:
                    args = {
                        "cn": entry.single("cn"),
                        "mn": entry.single("mn") or "",
                        "sn": entry.single("sn") or "",
                        "email": entry.single("emailForward"),
                        "uid": entry.uid,
                        "fpr": "FIXME-REMOVED-" + entry.uid,
                        "username": "{}@invalid.example.org".format(entry.uid),
                        "audit_author": self.hk.housekeeper.user,
                    }
                    if entry.single("gidNumber") == "800":
                        args["status"] = const.STATUS_REMOVED_DD
                        args["audit_notes"] = "created to mirror a removed guest account from LDAP"
                        if not args["email"]: args["email"] = "{}@debian.org".format(entry.uid)
                    else:
                        args["status"] = const.STATUS_REMOVED_DC_GA
                        args["audit_notes"] = "created to mirror a removed DD account from LDAP"
                        if not args["email"]: args["email"] = "{}@example.org".format(entry.uid)
                    person = bmodels.Person.objects.create_user(**args)
                    log.warn("%s: %s: %s", self.IDENTIFIER, self.hk.link(person), args["audit_notes"])
            else:
                if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None:
                    if person.status not in (const.STATUS_DD_U, const.STATUS_DD_NU):
                        log.warn("%s: %s has gidNumber 800 and fingerprint %s in LDAP, but in our db the state is %s",
                                 self.IDENTIFIER, self.hk.link(person), entry.single("keyFingerPrint"), const.ALL_STATUS_DESCS[person.status])

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
