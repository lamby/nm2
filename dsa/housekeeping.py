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
import django_housekeeping as hk
from django.db import transaction
from backend.housekeeping import MakeLink, Housekeeper
from . import models as dmodels
from backend import const
import backend.models as bmodels
import process.models as pmodels
import backend.ops as bops
import process.ops as pops
import logging

log = logging.getLogger(__name__)


class NewGuestAccountsFromDSA(hk.Task):
    """
    Create new Person entries for guest accounts created by DSA
    """
    DEPENDS = [MakeLink]

    @transaction.atomic
    def run_main(self, stage):
        for entry in dmodels.list_people():
            # Skip DDs
            if entry.is_dd and entry.single("keyFingerPrint") is not None: continue

            fpr = entry.single("keyFingerPrint")

            # Skip people without fingerprints
            if fpr is None: continue

            email = entry.single("emailForward")

            # Skip entries without emails (happens when running outside of the Debian network)
            if email is None: continue

            # Find the corresponding person in our database
            person = bmodels.Person.objects.get_from_other_db(
                "LDAP",
                uid=entry.uid,
                fpr=fpr,
                email=email,
                format_person=self.hk.link,
            )

            if not person:
                # New DC_GA
                audit_notes = "created new guest account entry from LDAP"
                person = bmodels.Person.objects.create_user(
                    cn=entry.single("cn"),
                    mn=entry.single("mn") or "",
                    sn=entry.single("sn") or "",
                    email=email,
                    email_ldap=email,
                    uid=entry.uid,
                    fpr=fpr,
                    status=const.STATUS_DC_GA,
                    username="{}@invalid.example.org".format(entry.uid),
                    audit_author=self.hk.housekeeper.user,
                    audit_notes=audit_notes,
                )
                log.warn("%s: %s %s", self.IDENTIFIER, self.hk.link(person), audit_notes)
            else:
                # Validate fields
                if person.uid is not None and person.uid != entry.uid:
                    log.warn("%s: LDAP has uid %s for person %s, but uid is %s in our database",
                             self.IDENTIFIER, entry.uid, self.hk.link(person), person.uid)
                    continue

                if person.fpr is not None and person.fpr != fpr:
                    log.warn("%s: LDAP has fingerprint %s for person %s, but fingerprint is %s in our database",
                             self.IDENTIFIER, fpr, self.hk.link(person), person.fpr)
                    continue

                audit_notes = ["entry found in LDAP"]

                # Ignore differences in email forward: they are caught by
                # CheckLDAPConsistency

                if person.status in (const.STATUS_DC_GA, const.STATUS_DM_GA):
                    # We already know about it: nothing to do
                    pass
                elif person.status in (const.STATUS_DC, const.STATUS_DM):
                    if person.status == const.STATUS_DM:
                        # DM that becomes DM_GA (acquires uid)
                        new_status = const.STATUS_DM_GA
                    else:
                        # DC that becomes DC_GA (acquires uid)
                        new_status = const.STATUS_DC_GA
                    audit_notes = "entry found in LDAP, adding 'guest account' status"

                    try:
                        process = pmodels.Process.objects.get(person=person, applying_for=new_status)
                    except pmodels.Process.DoesNotExist:
                        process = None

                    if process is None:
                        op = bops.ChangeStatus(
                            audit_author=self.hk.housekeeper.user, audit_notes=audit_notes,
                            person=person, status=new_status)
                        op.execute()
                    else:
                        op = pops.ProcessClose(
                            audit_author=self.hk.housekeeper.user, audit_notes=audit_notes,
                            process=process,
                        )
                        op.execute()

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
                        "email_ldap": entry.single("emailForward"),
                        "uid": entry.uid,
                        "fpr": "FIXME-REMOVED-" + entry.uid,
                        "username": "{}@invalid.example.org".format(entry.uid),
                        "audit_author": self.hk.housekeeper.user,
                    }
                    if entry.is_dd:
                        args["status"] = const.STATUS_REMOVED_DD
                        args["audit_notes"] = "created to mirror a removed DD account from LDAP"
                        if not args["email"]: args["email"] = "{}@debian.org".format(entry.uid)
                    else:
                        args["status"] = const.STATUS_DC_GA
                        args["audit_notes"] = "created to mirror a removed guest account from LDAP"
                        if not args["email"]: args["email"] = "{}@example.org".format(entry.uid)
                    person = bmodels.Person.objects.create_user(**args)
                    log.warn("%s: %s: %s", self.IDENTIFIER, self.hk.link(person), args["audit_notes"])
            else:
                dsa_status = entry.single("accountStatus")
                if dsa_status is not None:
                    dsa_status = dsa_status.split()[0]

                if dsa_status in ("retiring", "inactive"):
                    if person.status in (const.STATUS_DC_GA, const.STATUS_DM_GA):
                        pass # TODO: handle guest accounts that have been closed
                    elif person.status not in (const.STATUS_REMOVED_DD, const.STATUS_EMERITUS_DD):
                        log.warn("%s: %s has accountStatus '%s' but in our db the state is %s",
                                 self.IDENTIFIER, self.hk.link(person), entry.single("accountStatus"), const.ALL_STATUS_DESCS[person.status])

                if entry.is_dd and entry.single("keyFingerPrint") is not None:
                    if person.status not in (const.STATUS_DD_U, const.STATUS_DD_NU):
                        log.warn("%s: %s has supplementaryGid 'Debian' and fingerprint %s in LDAP, but in our db the state is %s",
                                 self.IDENTIFIER, self.hk.link(person), entry.single("keyFingerPrint"), const.ALL_STATUS_DESCS[person.status])

                email = entry.single("emailForward")
                if email != person.email:
                    if email is not None:
                        log.info("%s: %s changing email_ldap from %s to %s (source: LDAP)",
                                self.IDENTIFIER, self.hk.link(person), person.email, email)
                        person.email_ldap = email
                        person.save(audit_author=self.hk.housekeeper.user, audit_notes="updated email_ldap from LDAP")
                    # It gives lots of errors when run outside of the debian.org
                    # network, since emailForward is not exported there, and it has
                    # no use case I can think of so far
                    #
                    # else:
                    #     log.info("%s: %s has email %s but emailForward is empty in LDAP",
                    #              self.IDENTIFIER, self.hk.link(person), person.email)
