# coding: utf-8
# nm.debian.org website import from keyring-maint
#
# Copyright (C) 2015  Enrico Zini <enrico@debian.org>
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
import backend.models as bmodels
from backend import const
import os
import os.path
import datetime
import re
import requests
import logging

log = logging.getLogger(__name__)

class KeyringMaintImport(object):
    def __init__(self, logtag, persons, person_link):
        self.logtag = logtag
        # Ref to [housekeeping].keyring_maint.persons
        self.persons = persons
        # Ref to [housekeeping].link
        self.person_link = person_link

    def _fetch_url(self, url):
        bundle="/etc/ssl/ca-debian/ca-certificates.crt"
        if os.path.exists(bundle):
            return requests.get(url, verify=bundle)
        else:
            return requests.get(url)

    def _get_author(self, state):
        """
        Get the author person entry from a keyring maint commit state
        """
        email = state["author_email"]
        author = self.persons.get(email, None)
        return author

    def _split_subject(self, subject):
        """
        Arbitrary split a full name into cn, mn, sn

        This is better than nothing, but not a lot better than that.
        """
        # See http://www.kalzumeus.com/2010/06/17/falsehoods-programmers-believe-about-names/
        fn = subject.split()
        if len(fn) == 1:
            return fn[0], "", ""
        elif len(fn) == 2:
            return fn[0], "", fn[1]
        elif len(fn) == 3:
            return fn
        else:
            middle = len(fn) // 2
            return " ".join(fn[:middle]), "", " ".join(fn[middle:])

    def _get_dm_info(self, state, operation):
        """
        Dig all information from a commit body that we can use to create a new
        DM
        """
        commit = state.get("commit", None)
        ts = state.get("ts", None)
        if ts is None:
            log.warn("%s: ts field not found in state for commit %s", self.logtag, commit)
            return None
        ts = datetime.datetime.utcfromtimestamp(ts)

        fpr = operation.get("New-key", None)
        if fpr is None:
            log.warn("%s: New-key field not found in commit %s", self.logtag, commit)
            return None

        fn = operation.get("Subject", None)
        if fn is None:
            log.warn("%s: Subject field not found in commit %s", self.logtag, commit)
            return None
        cn, mn, sn = self._split_subject(fn)

        rt = operation.get("RT-Ticket", None)

        # To get the email, we need to go and scan the agreement post from the
        # list archives
        email = None
        agreement_url = operation.get("Agreement", None)
        if agreement_url is not None:
            r = self._fetch_url(agreement_url.strip())
            if r.status_code == 200:
                mo = re.search(r'<link rev="made" href="mailto:([^"]+)">', r.text)
                if mo:
                    email = mo.group(1)

        if email is None:
            log.warn("%s: Email not found in commit %s", self.logtag, commit)
            return None

        return {
            # Dummy username used to avoid unique entry conflicts
            "username": "{}@example.org".format(fpr),
            "fpr": fpr,
            "cn": cn,
            "mn": mn,
            "sn": sn,
            "rt": rt,
            "email": email,
            "status": const.STATUS_DM,
            "status_changed": ts,
        }

    def _get_dd_info(self, state, operation):
        """
        Dig all information from a commit body that we can use to create a new
        DD
        """
        commit = state.get("commit", None)
        ts = state.get("ts", None)
        if ts is None:
            log.warn("%s: ts field not found in state for commit %s", self.logtag, commit)
            return None
        ts = datetime.datetime.utcfromtimestamp(ts)

        fpr = operation.get("New-key", None)
        if fpr is None:
            log.warn("%s: New-key field not found in commit %s", self.logtag, commit)
            return None

        fn = operation.get("Subject", None)
        if fn is None:
            log.warn("%s: Subject field not found in commit %s", self.logtag, commit)
            return None
        cn, mn, sn = self._split_subject(fn)

        rt = operation.get("RT-Ticket", None)

        uid = operation.get("Username", None)

        return {
            # Dummy username used to avoid unique entry conflicts
            "username": "{}@debian.org".format(uid),
            "uid": uid,
            "fpr": fpr,
            "cn": cn,
            "mn": mn,
            "sn": sn,
            "rt": rt,
            "email": "{}@debian.org".format(uid),
            "status": const.STATUS_DM,
            "status_changed": ts,
        }

    def do_add(self, state, operation):
        commit = state.get("commit", None)
        author = self._get_author(state)
        if author is None:
            log.warn("%s: author not found for commit %s", self.logtag, commit)
            return False

        role = operation.get("Role", None)
        if role is None:
            log.warn("%s: role not found for commit %s", self.logtag, commit)
            return False

        if role == "DM":
            info = self._get_dm_info(state, operation)
            if info is None: return False
            info["audit_author"] = author
            return self.do_add_dm(commit, info)
        elif role in ("DD", "DN"):
            info = self._get_dd_info(state, operation)
            if info is None: return False
            info["audit_author"] = author
            return self.do_add_dd(commit, role, info)
        else:
            log.warn("%s: Unhandled add action in commit %s", self.logtag, commit)
            return False

        #import json
        #print("ADD", json.dumps(dict(state), indent=1), json.dumps(dict(operation), indent=1))

            #    if 'rt-ticket' in operation:
            #        self.out.write("# Commit " + state['commit'] + "\n")
            #        if role_is_dd(operation['role']):
            #            self.out.write("rt edit ticket/" + operation['rt-ticket'] +
            #                    " set queue=DSA\n")
            #        elif operation['role'] == 'DM':
            #            self.out.write("rt correspond -s resolved -m " +
            #                "'This key has now been added to the active DM keyring.' " +
            #                operation['rt-ticket'] + "\n")
            #        else:
            #            self.out.write("rt correspond -s resolved -m " +
            #                "'This key has now been added to the " +
            #                operation['role'] + " keyring.' " +
            #                operation['rt-ticket'] + "\n")

    def do_add_dm(self, commit, info):
        # Check for existing records in the database
        try:
            fpr_person = bmodels.Person.objects.get(fpr=info["fpr"])
        except bmodels.Person.DoesNotExist:
            fpr_person = None
        try:
            email_person = bmodels.Person.objects.get(email=info["email"])
        except bmodels.Person.DoesNotExist:
            email_person = None

        # If it is all new, create and we are done
        if fpr_person is None and email_person is None:
            rt = info.pop("rt", None)
            if rt:
                info["audit_notes"] = "Created DM entry, RT #{}".format(rt)
            else:
                info["audit_notes"] = "Created DM entry, RT unknown"
            p = bmodels.Person.objects.create_user(**info)
            log.info("%s: %s: %s", self.logtag, self.person_link(p), info["audit_notes"])
            return True

        # Otherwise, see if we are unambiguously referring to a record that we
        # can update
        if fpr_person == email_person:
            person = fpr_person
        elif fpr_person is None:
            person = email_person
        elif email_person is None:
            person = fpr_person
        else:
            log.warn("%s: commit %s has a new DM with email and fingerprints corresponding to two different users: email %s is %s and fpr %s is %s",
                     self.logtag, commit, info["email"], self.person_link(email_person), info["fpr"], self.person_link(fpr_person))
            return False

        if person.status in (const.STATUS_DM, const.STATUS_DM_GA):
            # Already a DM, nothing to do
            log.info("%s: %s is already a DM: skipping duplicate entry", self.logtag, self.person_link(person))
            return True
        elif person.status in (
                const.STATUS_DD_U, const.STATUS_DD_NU, const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD,
                const.STATUS_EMERITUS_DM, const.STATUS_REMOVED_DM):
            log.warn("%s: commit %s has a new DM, but it corresponds to person %s which has status %s",
                     self.logtag, commit, self.person_link(person), person.status)
            return False
        else:
            if person.status == const.STATUS_DC_GA:
                person.status = const.STATUS_DM_GA
            else:
                person.status = const.STATUS_DM
            person.status_changed = info["status_changed"]

            if info.get("rt", None):
                audit_notes = "Set status to {}, RT #{}".format(const.ALL_STATUS_DESCS[person.status], info["rt"])
            else:
                audit_notes = "Set status to {}, RT unknown".format(const.ALL_STATUS_DESCS[person.status])

            person.save(
                audit_author=info["audit_author"],
                audit_notes=audit_notes)
            log.info("%s: %s: %s", self.logtag, self.person_link(person), audit_notes)
            return True

    def do_add_dd(self, commit, role, info):
        try:
            fpr_person = bmodels.Person.objects.get(fpr=info["fpr"])
        except bmodels.Person.DoesNotExist:
            fpr_person = None
        if info["uid"]:
            try:
                uid_person = bmodels.Person.objects.get(uid=info["uid"])
            except bmodels.Person.DoesNotExist:
                uid_person = None
        else:
            uid_person = None

        # If it is all new, keyring has a DD that DAM does not know about:
        # yell.
        if fpr_person is None and uid_person is None:
            log.warn("%s: commit %s has new DD %s %s that we do not know about",
                     self.logtag, commit, info["uid"], info["fpr"])
            return False

        # Otherwise, see if we are unambiguously referring to a record that we
        # can work with
        if fpr_person and uid_person and fpr_person.pk != uid_person.pk:
            log.warn("%s: commit %s has a new DD with uid and fingerprints corresponding to two different users: uid %s is %s and fpr %s is %s",
                     self.logtag, commit, info["uid"], self.person_link(uid_person), info["fpr"], self.person_link(fpr_person))
            return False

        person = uid_person if uid_person else fpr_person

        if person.fpr != info["fpr"]:
            # Keyring-maint added a different key: sync with them
            if info.get("rt", None):
                audit_notes = "Set fingerprint to {}, RT #{}".format(info["fpr"], info["rt"])
            else:
                audit_notes = "Set fingerprint to {}, RT unknown".format(info["fpr"])
            person.fpr = info["fpr"]
            person.save(audit_author=info["audit_author"], audit_notes=audit_notes)
            log.info("%s: %s: %s", self.logtag, self.person_link(person), audit_notes)
            # Do not return yet, we still need to check the status

        role_status_map = {
            "DD": const.STATUS_DD_U,
            "DN": const.STATUS_DD_NU,
        }

        if person.status == role_status_map[role]:
            # Status already matches
            log.info("%s: %s is already %s: skipping duplicate entry", self.logtag, self.person_link(person), const.ALL_STATUS_DESCS[person.status])
            return True
        else:
            found = False
            for p in [x for x in person.active_processes if x.applying_for == role_status_map[role]]:
                if info.get("rt", None):
                    logtext = "Added to %s keyring, RT #{}".format(role, info["rt"])
                else:
                    logtext = "Added to %s keyring, RT unknown".format(role)
                if not bmodels.Log.objects.filter(process=p, changed_by=info["audit_author"], logdate=info["ts"], logtext=logtext).exists():
                    l = bmodels.Log.for_process(p, changed_by=info["audit_author"], logdate=info["ts"], logtext=logtext)
                    l.save()
                log.info("%s: %s has an open process to become %s, keyring added them as %s",
                         self.logtag, self.person_link(person), const.ALL_STATUS_DESCS[p.applying_for], role)
                found = True
            if found:
                return True
            else:
                # f3d1c1ee92bba3ebe05f584b7efea0cfd6e4ebe4 is an example commit
                # that triggers this
                log.warn("%s: %s: keyring added them as %s in commit %s, but we have no relevant active process for this change",
                         self.logtag, self.person_link(person), role, commit)
                return False

    def do_remove(self, state, operation):
        commit = state.get("commit", None)
        author = self._get_author(state)
        if author is None:
            log.warn("%s: author not found for commit %s", self.logtag, commit)
            return False

        role = operation.get("Role", None)
        if role is None:
            log.warn("%s: role not found for commit %s", self.logtag, commit)
            return False

        if role == "DD":
            uid = operation.get("Username", None)
            if uid is None:
                log.warn("%s: Username not found for commit %s", self.logtag, commit)
                return False

            fpr = operation.get("Key", None)
            if fpr is None:
                log.warn("%s: Key not found for commit %s", self.logtag, commit)
                return False

            try:
                uid_person = bmodels.Person.objects.get(uid=uid)
            except bmodels.Person.DoesNotExist:
                uid_person = None

            try:
                fpr_person = bmodels.Person.objects.get(fpr=fpr)
            except bmodels.Person.DoesNotExist:
                fpr_person = None

            if uid_person and fpr_person and uid_person.pk != fpr_person.pk:
                # Example case: e958b577c9ff22648baa6553a123ba553ae21e0b which
                # has uid 'joey' instead of 'joeyh'. A full fingerprint is
                # harder to mistype while still generating a conflict with
                # another existing one.
                log.warn("%s: commit %s references two records in the database: by uid %s: %s, and by fingerprint %s: %s: Assuming a typo in the uid",
                         self.logtag, commit, fpr, self.person_link(fpr_person), uid, self.person_link(uid_person))
                person = fpr_person
            else:
                person = uid_person if uid_person else fpr_person

            if not person:
                log.warn("%s: commit %s references a person that is not known to the database", self.logtag, commit)

            if person.status in (const.STATUS_DD_U, const.STATUS_DD_NU):
                rt = operation.get("RT-Ticket", None)
                if rt:
                    audit_notes = "Moved to emeritus keyring, RT #{}".format(rt)
                else:
                    audit_notes = "Moved to emeritus keyring, RT unknown"

                person.status = const.STATUS_EMERITUS_DD
                person.save(audit_author=author, audit_notes=audit_notes)
                log.info("%s: %s: %s", self.logtag, self.person_link(person), audit_notes)
                return True
            elif person.status == const.STATUS_EMERITUS_DD:
                # Already moved to DD
                log.info("%s: %s is already emeritus: skipping key removal", self.logtag, self.person_link(person))
                return True
        else:
            log.warn("%s: Unhandled remove action in commit %s", self.logtag, commit)
            return False

    def do_replace(self, state, operation):
        commit = state.get("commit", None)
        author = self._get_author(state)
        if author is None:
            log.warn("%s: author not found for commit %s", self.logtag, commit)
            return False

        role = operation.get("Role", None)
        if role is None:
            log.warn("%s: role not found for commit %s", self.logtag, commit)
            return False

        old_key = operation.get("Old-key", None)
        if old_key is None:
            log.warn("%s: Old-key not found for commit %s", self.logtag, commit)
            return False
        new_key = operation.get("New-key", None)
        if new_key is None:
            log.warn("%s: New-key not found for commit %s", self.logtag, commit)
            return False

        try:
            old_person = bmodels.Person.objects.get(fpr=old_key)
        except bmodels.Person.DoesNotExist:
            old_person = None

        try:
            new_person = bmodels.Person.objects.get(fpr=new_key)
        except bmodels.Person.DoesNotExist:
            new_person = None

        rt = operation.get("RT-Ticket", None)

        if old_person is None and new_person is None:
            log.warn("%s: Unhandled replace in commit %s", self.logtag, commit)
            return False
#            # No before or after match with our records
#            fpr1, ktype1 = self.hk.keyrings.resolve_keyid(key1)
#            fpr2, ktype2 = self.hk.keyrings.resolve_keyid(key2)
#            if fpr1 is not None:
#                if fpr2 is not None:
#                    # Before and after keyrings known
#                    if ktype1 != ktype2:
#                        # Keyring moved
#                        self._ann_fpr(ts, rt, fpr1,
#                                      "keyring logs report that this key has been replaced with {}, and moved from the {} to the {} keyring".format(fpr2, ktype1, ktype2),
#                                      keyring_status=ktype2,
#                                      keyring_fpr=fpr2,
#                                      shasum=shasum, **info)
#                    else:
#                        # Same keyring
#                        self._ann_fpr(ts, rt, fpr1,
#                                      "keyring logs report that this key has been replaced with {} in the {} keyring".format(fpr2, ktype2),
#                                      keyring_status=ktype2,
#                                      keyring_fpr=fpr2,
#                                      shasum=shasum, **info)
#                else:
#                    # Only 'before' keyring known
#                    self._ann_fpr(ts, rt, fpr1,
#                                  "keyring logs report that this key has been replaced with unkonwn key {}".format(key2),
#                                  keyring_status=ktype1,
#                                  shasum=shasum, **info)
#            else:
#                if fpr2 is not None:
#                    # Only 'after' keyring known
#                    self._ann_fpr(ts, rt, fpr2,
#                                  "keyring logs report that this key has replaced unknown key {} in the {} keyring".format(key1, ktype2),
#                                  keyring_status=ktype2,
#                                  shasum=shasum, **info)
#                else:
#                    # Neither before nor after are known
#                    pass
#                    # print("! Replaced %s with %s (none of which are in the database!) %s" % (key1, key2, self.rturl(rt)))
        elif old_person is None and new_person is not None:
            # Already replaced
            log.info("%s: %s already has the new key: skipping key replace", self.logtag, self.person_link(new_person))
            return True
        elif old_person is not None and new_person is None:
            old_person.fpr = new_key
            if rt is not None:
                audit_notes = "GPG key changed, RT #{}".format(rt)
            else:
                audit_notes = "GPG key changed, RT unknown".format(rt)
            old_person.save(
                audit_author=author,
                audit_notes=audit_notes)
#            fpr, ktype = self.hk.keyrings.resolve_keyid(key2)
#            if fpr is None:
#                self._ann_person(ts, rt, p1, "key changed to unknown key {}".format(key2), shasum=shasum, **info)
#                # print("! %s replaced key %s with %s but could not find %s in keyrings %s" % (p.lookup_key, key1, key2, key2, self.rturl(rt)))
#            else:
#                # Keyring-maint is authoritative on key changes
#                p1.fpr = fpr
#                p1.save()
#                log.info("%s: %s key replaced with %s (RT #%s, shasum %s)", self.IDENTIFIER, self.hk.link(p1), fpr, rt, shasum)
            log.info("%s: %s: %s", self.logtag, self.person_link(old_person), audit_notes)
            return True
        else:
            log.warn("%s: commit %s reports a key change from %s to %s, but the keys belong to two different people (%s and %s)",
                     self.logtag, commit, old_key, new_key, self.person_link(old_person), self.person_link(new_person))
            return False

            #    self.out.write("# Commit " + state['commit'] + "\n")
            #    if role_is_dd(operation['role']):
            #        self.out.write("rt edit ticket/" + operation['rt-ticket'] +
            #                " set queue=Keyring\n" +
            #                "rt correspond -s resolved -m " +
            #                "'Your key has been replaced in the active keyring and LDAP updated with the new fingerprint.' " +
            #                operation['rt-ticket'] + "\n")
            #    else:
            #        self.out.write("rt edit ticket/" + operation['rt-ticket'] +
            #                " set queue=Keyring\n" +
            #                "rt correspond -s resolved -m "+
            #                "'Your key has been replaced in the active DM keyring.' " +
            #                operation['rt-ticket'] + "\n")

#    def person_for_key_id(self, kid):
#        """
#        Given a key id (short, long or full fingerprint) return the
#        corresponding Person object, or None if none did match.
#        """
#        try:
#            return bmodels.Person.objects.get(fpr__endswith=kid)
#        except bmodels.Person.DoesNotExist:
#            return None
#
#    def rturl(self, num):
#        """
#        Build an RT URL for an RT ticket
#        """
#        return "https://rt.debian.org/" + num
#
#    def _ann_fpr(self, d, rt, fpr, log, **kw):
#        """
#        Annotate a fingerprint inconsistency:
#            d: datetime object
#            rt: rt ticket number
#            fpr: key fingerprint
#            log: text description of the inconsistency
#            **kw: passed as extra annotation information
#        """
#        if rt is not None:
#            self.hk.inconsistencies.annotate_fingerprint(self, fpr,
#                                                    "{}, RT #{}".format(log, rt),
#                                                    keyring_rt=rt,
#                                                    keyring_log_date=d.strftime("%Y%m%d %H%M%S"),
#                                                    **kw)
#        else:
#            self.hk.inconsistencies.annotate_fingerprint(self, fpr, log,
#                                                    keyring_log_date=d.strftime("%Y%m%d %H%M%S"),
#                                                    **kw)
#
#    def _ann_person(self, d, rt, person, log, **kw):
#        """
#        Annotate a Person inconsistency:
#            d: datetime object
#            rt: rt ticket number
#            person: Person object to annotate
#            log: text description of the inconsistency
#            **kw: passed as extra annotation information
#        """
#        if rt is not None:
#            self.hk.inconsistencies.annotate_person(self, person,
#                                                    "{}, RT #{}".format(log, rt),
#                                                    keyring_rt=rt,
#                                                    keyring_log_date=d.strftime("%Y%m%d %H%M%S"),
#                                                    **kw)
#        else:
#            self.hk.inconsistencies.annotate_person(self, person, log,
#                                                    keyring_log_date=d.strftime("%Y%m%d %H%M%S"),
#                                                    **kw)
#
#
#    def do_move_to_emeritus(self, shasum, ts, info):
#        # { "Action": "FIXME-move", "Key": x.group("key"), "Target": "emeritus", "Subject": x.group("subj"), "RT-Ticket": x.group("rt") }
#        rt = info.get("RT-Ticket", None)
#        key = info.get("Key", None)
#        p = self.person_for_key_id(key)
#        if p is None:
#            fpr, ktype = self.hk.keyrings.resolve_keyid(key)
#            self._ann_fpr(ts, rt, fpr, "keyring logs report a new emeritus DD, with no known record in our database", keyring_status=ktype,
#                          shasum=shasum, **info)
#            #print("! New Emeritus DD %s %s (no account before??)" % (key, self.rturl(rt)))
#        elif p.status == const.STATUS_EMERITUS_DD:
#            # print("# %s goes from %s to emeritus DD (already known in the database) %s" % (p.lookup_key, p.status, self.rturl(rt)))
#            pass # Already emeritus
#        else:
#            self._ann_person(ts, rt, p, "keyring logs report change from {} to {}".format(p.status, const.STATUS_EMERITUS_DD),
#                             keyring_status=const.STATUS_EMERITUS_DD,
#                             fix_cmdline="./manage.py change_status {} {} --date='{}' --message='imported from keyring changelog, RT {}'".format(
#                                 p.lookup_key, const.STATUS_EMERITUS_DD, ts.strftime("%Y-%m-%d %H:%M:%S"), rt),
#                             shasum=shasum, **info)
#
#    def do_move_to_removed(self, shasum, ts, info):
#        # { "Action": "FIXME-move", "Key": x.group("key"), "Target": "removed", "Subject": x.group("subj"), "RT-Ticket": x.group("rt") },
#        rt = info.get("RT-Ticket", None)
#        key = info.get("Key", None)
#        p = self.person_for_key_id(key)
#        if p is None:
#            fpr, ktype = self.hk.keyrings.resolve_keyid(key)
#            self._ann_fpr(ts, rt, fpr, "keyring logs report a new removed DD, with no known record in our database", keyring_status=ktype,
#                          shasum=shasum, **info)
#            #print("! New removed key %s %s (no account before??)" % (key, self.rturl(rt)))
#        else:
#            #print("! %s key %s moved to removed keyring %s" % (p.lookup_key, key, self.rturl(rt)))
#            self._ann_person(ts, rt, p, "keyring logs report change from {} to removed".format(p.status, const.STATUS_REMOVED_DD), keyring_status=const.STATUS_REMOVED_DD,
#                             shasum=shasum, **info)
#
#    #@keyring_log_matcher(r"^\s*\*\s+(?P<line>.*0x[0-9A-F]+.+)", fallback=True)
#    #def do_fallback(self, d, line):
#    #    # We get a line that contains at least one key id
#    #    keys = re.findall(r"0x(?P<key>[0-9A-F]+)", line)
#    #    rtmo = re.search(r"RT #(?P<rt>\d+)", line)
#    #    if rtmo:
#    #        rt = int(rtmo.group("rt"))
#    #    else:
#    #        rt = None
#
#    #    # Log the line in all relevant bits found
#    #    for key in keys:
#    #        p = self.person_for_key_id(key)
#    #        if p is not None:
#    #            self._ann_person(d, rt, p, "relevant but unparsed log entry: \"{}\"".format(line))
#    #            continue
#
#    #        fpr, ktype = self.hk.keyrings.resolve_keyid(key)
#    #        if fpr is not None:
#    #            self._ann_fpr(d, rt, fpr, "relevant but unparsed log entry: \"{}\"".format(line))

