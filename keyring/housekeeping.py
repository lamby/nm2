# coding: utf-8
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
from django.conf import settings
from backend.housekeeping import MakeLink, Inconsistencies
import backend.models as bmodels
from backend import const
from . import models as kmodels
import os
import os.path
import time
import shutil
import subprocess
import datetime
import pipes
import re
import requests
import logging

log = logging.getLogger(__name__)

KEYRINGS_TMPDIR = getattr(settings, "KEYRINGS_TMPDIR", "/srv/keyring.debian.org/data/tmp_keyrings")

class Keyrings(hk.Task):
    """
    Load keyrings
    """
    NAME = "keyrings"

    KEYID_LEN = 16

    def run_main(self, stage):
        self.dm = frozenset(kmodels.list_dm())
        log.info("%s: Imported %d entries from dm keyring", self.IDENTIFIER, len(self.dm))
        self.dd_u = frozenset(kmodels.list_dd_u())
        log.info("%s: Imported %d entries ffom dd_u keyring", self.IDENTIFIER, len(self.dd_u))
        self.dd_nu = frozenset(kmodels.list_dd_nu())
        log.info("%s: Imported %d entries ffom dd_nu keyring", self.IDENTIFIER, len(self.dd_nu))
        self.emeritus_dd = frozenset(kmodels.list_emeritus_dd())
        log.info("%s: Imported %d entries ffom emeritus_dd keyring", self.IDENTIFIER, len(self.emeritus_dd))
        self.removed_dd = frozenset(kmodels.list_removed_dd())
        log.info("%s: Imported %d entries ffom removed_dd keyring", self.IDENTIFIER, len(self.removed_dd))

        # Keep an index mapping key IDs to fingerprints and keyring type
        self.by_fpr = {}
        self.by_keyid = {}
        duplicate_fprs = []
        duplicate_keyids = []
        for t in ("dm", "dd_u", "dd_nu", "emeritus_dd", "removed_dd"):
            for fpr in getattr(self, t):
                record = (fpr, t)

                # Index by fingerprint
                old_rec = self.by_fpr.get(fpr, None)
                if old_rec is not None:
                    log.warning("%s: duplicate fingerprint %s, found in %s and in %s", self.IDENTIFIER, fpr, old_rec[1], t)
                    duplicate_fprs.append(fpr)
                else:
                    self.by_fpr[fpr] = record

                # Index by key id
                keyid = fpr[-self.KEYID_LEN:]
                old_rec = self.by_keyid.get(keyid, None)
                if old_rec is not None:
                    log.warning("%s: duplicate key id %s, found in %s and in %s", self.IDENTIFIER, keyid, old_rec[1], t)
                    duplicate_keyids.append(keyid)
                else:
                    self.by_keyid[keyid] = record

        # Ignore duplicate fingerprints for lookup purposes
        for fpr in duplicate_fprs:
            del self.by_fpr[fpr]
        for keyid in duplicate_keyids:
            del self.by_keyid[keyid]

    def resolve_fpr(self, fpr):
        """
        Return the keyring type given a fingerprint, or None if the fingerprint
        is unknown
        """
        rec = self.by_fpr.get(fpr, None)
        if rec is None:
            return None
        return rec[1]

    def resolve_keyid(self, keyid):
        """
        Return the (fingerprint, keyring type) given a key id, or (None, None)
        if the key id is unknown
        """
        if len(keyid) > self.KEYID_LEN:
            type = self.resolve_fpr(keyid)
            if type is None:
                return None, None
            else:
                return keyid, type
        rec = self.by_keyid.get(keyid, None)
        if rec is None:
            return None, None
        return rec


class CheckKeyringConsistency(hk.Task):
    """
    Show entries that do not match between keyrings and our DB
    """
    DEPENDS = [Keyrings, MakeLink, Inconsistencies]

    def run_main(self, stage):
        # Prefetch people and index them by fingerprint
        people_by_fpr = dict()
        for p in bmodels.Person.objects.all():
            if p.fpr is None: continue
            if p.fpr.startswith("FIXME"): continue
            people_by_fpr[p.fpr] = p

        keyring_by_status = {
            const.STATUS_DM: self.hk.keyrings.dm,
            const.STATUS_DM_GA: self.hk.keyrings.dm,
            const.STATUS_DD_U: self.hk.keyrings.dd_u,
            const.STATUS_DD_NU: self.hk.keyrings.dd_nu,
            const.STATUS_EMERITUS_DD: self.hk.keyrings.emeritus_dd,
            const.STATUS_REMOVED_DD: self.hk.keyrings.removed_dd,
        }

        self.count = 0

        # Check the fingerprints on our DB
        for fpr, p in sorted(people_by_fpr.iteritems(), key=lambda x:x[1].uid):
            keyring = keyring_by_status.get(p.status)
            # Skip the statuses we currently can't check for
            if keyring is None: continue
            # Skip those that are ok
            if fpr in keyring: continue
            # Look for the key in other keyrings
            found = False
            for status, keyring in keyring_by_status.iteritems():
                if fpr in keyring:
                    self.hk.inconsistencies.log_person(self, p,
                                                                "has status {} but is in {} keyring".format(p.status, status),
                                                                keyring_status=status)
                    self.count += 1
                    found = True
                    break
            if not found and p.status != const.STATUS_REMOVED_DD:
                self.hk.inconsistencies.log_person(self, p,
                                                      "has status {} but is not in any keyring".format(p.status),
                                                      keyring_status=None)
                self.count += 1

        # Spot fingerprints not in our DB
        for status, keyring in keyring_by_status.iteritems():
            # TODO: not quite sure how to handle the removed_dd keyring, until I
            #       know what exactly is in there
            if status == const.STATUS_REMOVED_DD: continue
            for fpr in keyring:
                if fpr not in people_by_fpr:
                    self.hk.inconsistencies.log_fingerprint(self, fpr,
                                                               "is in {} keyring but not in our db".format(status),
                                                               keyring_status=status)
                    self.count += 1

    def log_stats(self):
        log.info("%s: %d mismatches between keyring and nm.debian.org databases",
                    self.IDENTIFIER, self.count)

    #@transaction.atomic
    #def compute_display_names_from_keyring(self, **kw):
    #    """
    #    Update Person.display_name with data from keyrings
    #    """
    #    # Current display names
    #    info = dict()
    #    for p in bmodels.Person.objects.all():
    #        if not p.fpr: continue
    #        info[p.fpr] = dict(
    #            cur=p.fullname,
    #            pri=None, # Primary uid
    #            deb=None, # Debian uid
    #        )
    #    log.info("%d entries with fingerprints", len(info))

    #    cur_fpr = None
    #    cur_info = None
    #    for keyring in "debian-keyring.gpg", "debian-maintainers.gpg", "debian-nonupload.gpg", "emeritus-keyring.gpg", "removed-keys.gpg":
    #        count = 0
    #        for fpr, u in kmodels.uid_info(keyring):
    #            if fpr != cur_fpr:
    #                cur_info = info.get(fpr, None)
    #                cur_fpr = fpr
    #                if cur_info is not None:
    #                    # Save primary uid
    #                    cur_info["pri"] = u.name

    #            if cur_info is not None and u.email is not None and u.email.endswith("@debian.org"):
    #                cur_info["deb"] = u.name
    #            count += 1
    #        log.info("%s: %d uids checked...", keyring, count)

    #    for fpr, i in info.iteritems():
    #        if not i["pri"] and not i["deb"]: continue
    #        if i["pri"]:
    #            cand = i["pri"]
    #        else:
    #            cand = i["deb"]
    #        if i["cur"] != cand:
    #            log.info("%s: %s %r != %r", keyring, fpr, i["cur"], cand)

class CleanUserKeyrings(hk.Task):
    """
    Remove old user keyrings
    """
    def run_main(self, stage):
        if not os.path.isdir(KEYRINGS_TMPDIR):
            return
        # Delete everything older than three days ago
        threshold = time.time() - 86400 * 3
        for fn in os.listdir(KEYRINGS_TMPDIR):
            if fn.startswith("."): continue
            pn = os.path.join(KEYRINGS_TMPDIR, fn)
            if not os.path.isdir(pn): continue
            if os.path.getmtime(pn) > threshold: continue

            log.info("%s: removing old user keyring %s", self.IDENTIFIER, pn)
            shutil.rmtree(pn)

class KeyringMaint(hk.Task):
    """
    Update/regenerate the keyring with the keys of keyring-maint people
    """
    KEYRING_MAINT_MEMBERS = [
        {
            "uid": "noodles",
            "fpr": "0E3A94C3E83002DAB88CCA1694FA372B2DA8B985",
            "email": "noodles@earth.li",
        },
        {
            "uid": "gwolf",
            "fpr": "AB41C1C68AFD668CA045EBF8673A03E4C1DB921F",
            "email": "gwolf@debian.org",
        },
        {
            "uid": "dkg",
            "fpr": "0EE5BE979282D80B9F7540F1CCD2ED94D21739E9",
            "email": "dkg@openflows.com",
        },
    ]

    NAME = "keyring_maint"

    def run_main(self, stage):
        # Get the Person entries for keyring-maint people, indexed by the email
        # that they use in git commits.
        self.persons = {}
        for entry in self.KEYRING_MAINT_MEMBERS:
            self.persons[entry["email"]] = bmodels.Person.objects.get(uid=entry["uid"])

        # Regenerate the keyring in a new directory
        tmpdir = kmodels.KEYRING_MAINT_KEYRING + ".tmp"
        if os.path.exists(tmpdir): shutil.rmtree(tmpdir)
        os.mkdir(tmpdir)
        cmd = ["/usr/bin/gpg", "--homedir", tmpdir, "--keyserver", kmodels.KEYSERVER, "-q", "--no-default-keyring", "--no-auto-check-trustdb", "--no-permission-warning", "--recv"]
        for entry in self.KEYRING_MAINT_MEMBERS:
            cmd.append(entry["fpr"])
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        res = proc.wait()
        if res != 0:
            raise RuntimeError("{} returned error code {}. Stderr: {}", " ".join(pipes.quote(x) for x in cmd), res, stderr);

        # Remove the old directory
        if os.path.exists(kmodels.KEYRING_MAINT_KEYRING):
            shutil.rmtree(kmodels.KEYRING_MAINT_KEYRING)

        # Move the new directory to the destination place
        os.rename(tmpdir, kmodels.KEYRING_MAINT_KEYRING)

class KeyringGit(hk.Task):
    """
    Update the local keyring repository
    """
    NAME = "keyring_git"

    DEPENDS = [KeyringMaint]

    def run_main(self, stage):
        self.keyring = kmodels.GitKeyring()
        self.keyring.run_git("fetch")

class CheckKeyringLogs(hk.Task):
    """
    Show entries that do not match between keyrings and our DB
    """
#    DEPENDS = [MakeLink, Inconsistencies, Keyrings, KeyringGit]
    DEPENDS = [MakeLink, KeyringMaint, KeyringGit]

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
#    def do_add_dd(self, shasum, ts, info):
#        # { "Action": "add", "Role": x.group("role"), "New-Key": x.group("key"), "Subject": x.group("subj"), "RT-Ticket": x.group("rt") },
#        rt = info.get("RT-Ticket", None)
#        key = info.get("New-key", None)
#        p = self.person_for_key_id(key)
#        if p is None:
#            fpr, ktype = self.hk.keyrings.resolve_keyid(key)
#            self._ann_fpr(ts, rt, fpr, "keyring logs report a new DD, with no known record in our database", keyring_status=ktype,
#                          shasum=shasum, **info)
#            #print("! New DD %s %s (no account before??)" % (key, self.rturl(rt)))
#        elif p.status == const.STATUS_DD_U:
#            #print("# %s goes from %s to DD (already known in the database) %s" % (p.lookup_key, p.status, self.rturl(rt)))
#            pass # Already a DD
#        else:
#            self._ann_person(ts, rt, p, "keyring logs report change from {} to {}".format(p.status, const.STATUS_DD_U),
#                             keyring_status=const.STATUS_DD_U,
#                             fix_cmdline="./manage.py change_status {} {} --date='{}' --message='imported from keyring changelog, RT #{}'".format(
#                                 p.lookup_key, const.STATUS_DD_U, ts.strftime("%Y-%m-%d %H:%M:%S"), rt),
#                             shasum=shasum, **info)
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

    def _get_author(self, state):
        """
        Get the author person entry from a keyring maint commit state
        """
        email = state["author_email"]
        author = self.hk.keyring_maint.persons.get(email, None)
        return author

    def _get_dm_info(self, state, operation):
        """
        Dig all information from a commit body that we can use to create a new
        DM
        """
        commit = state.get("commit", None)
        ts = state.get("ts", None)
        if ts is None:
            log.warn("ts field not found in state for commit %s", commit)
            return None
        ts = datetime.datetime.utcfromtimestamp(ts)

        fpr = operation.get("New-key", None)
        if fpr is None:
            log.warn("New-key field not found in commit %s", commit)
            return None

        fn = operation.get("Subject", None)
        if fn is None:
            log.warn("Subject field not found in commit %s", commit)
            return None
        # Arbitrary split of full name into cn, mn, sn
        fn = fn.split()
        if len(fn) == 1:
            cn = fn[0]
            mn = ""
            sn = ""
        elif len(fn) == 2:
            cn = fn[0]
            mn = ""
            sn = fn[1]
        elif len(fn) == 3:
            cn, mn, sn = fn
        else:
            middle = len(fn) // 2
            cn = " ".join(fn[:middle])
            mn = ""
            sn = " ".join(fn[middle:])

        rt = operation.get("RT-Ticket", None)

        # To get the email, we need to go and scan the agreement post from the
        # list archives
        email = None
        agreement_url = operation.get("Agreement", None)
        if agreement_url is not None:
            r = requests.get(agreement_url.strip())
            if r.status_code == 200:
                mo = re.search(r'<link rev="made" href="mailto:([^"]+)">', r.text)
                if mo:
                    email = mo.group(1)

        if email is None:
            log.warn("Email not found in commit %s", commit)
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

    def do_add(self, state, operation):
        commit = state.get("commit", None)
        author = self._get_author(state)
        if author is None:
            log.warn("author not found for commit %s", commit)
            return False

        role = operation.get("Role", None)
        if role is None:
            log.warn("role not found for commit %s", commit)
            return False

        if role == "DM":
            info = self._get_dm_info(state, operation)
            info["audit_author"] = author
            return self.do_add_dm(commit, info)
        else:
            log.warn("Unhandled add action in commit %s", commit)

        #import json
        #print("ADD", json.dumps(dict(state), indent=1), json.dumps(dict(operation), indent=1))

    def do_add_dm(self, commit, info):
        # Check for existing records in the database
        try:
            fpr_person = bmodels.Person.objects.get(fpr=info["fpr"])
        except bmodels.Person.DoesNotExist:
            fpr_person = None
        try:
            email_person = bmodels.Person.objects.get(fpr=info["email"])
        except bmodels.Person.DoesNotExist:
            email_person = None

        # If it is all new, create and we are done
        if fpr_person is None and email_person is None:
            rt = info.pop("rt", None)
            if rt:
                info["audit_notes"] = "Created DM entry, RT #{}".format(rt)
            else:
                info["audit_notes"] = "Created DM entry, RT unknown"
            bmodels.Person.objects.create_user(**info)
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
            log.warn("commit %s has a new DM with email and fingerprints corresponding to two different users: email %s is %s and fpr %s is %s",
                     commit, info["email"], self.hk.link(email_person), info["fpr"], self.hk.link(fpr_person))
            return False

        if person.status in (const.STATUS_DM, const.STATUS_DM_GA):
            # Already a DM, nothing to do
            return True
        elif person.status in (
                const.STATUS_DD_U, const.STATUS_DD_NU, const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD,
                const.STATUS_EMERITUS_DM, const.STATUS_REMOVED_DM):
            log.warn("commit %s has a new DM, but it corresponds to person %s which has status %s",
                     commit, self.hk.link(person), person.status)
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
            return True

    def do_remove(self, state, operation):
        commit = state.get("commit", None)
        author = self._get_author(state)
        if author is None:
            log.warn("author not found for commit %s", commit)
            return False

        role = operation.get("Role", None)
        if role is None:
            log.warn("role not found for commit %s", commit)
            return False

        log.warn("Unhandled remove action in commit %s", commit)
        #import json
        #print("REMOVE", json.dumps(dict(state), indent=1), json.dumps(dict(operation), indent=1))
        #pass

    def do_replace(self, state, operation):
        commit = state.get("commit", None)
        author = self._get_author(state)
        if author is None:
            log.warn("author not found for commit %s", commit)
            return False

        role = operation.get("Role", None)
        if role is None:
            log.warn("role not found for commit %s", commit)
            return False

        old_key = operation.get("Old-key", None)
        if old_key is None:
            log.warn("Old-key not found for commit %s", commit)
            return False
        new_key = operation.get("New-key", None)
        if new_key is None:
            log.warn("New-key not found for commit %s", commit)
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
            log.warn("Unhandled replace in commit %s", commit)
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
            return True
        else:
            log.warn("commit %s reports a key change from %s to %s, but the keys belong to two different people (%s and %s)",
                     commit, old_key, new_key, self.hk.link(old_person), self.hk.link(new_person))
            return False

    def run_main(self, stage):
        """
        Parse changes from changelog entries after the given date (non inclusive).
        """
        gk = self.hk.keyring_git.keyring
        parser = gk.get_changelog_parser()
        start_shasum = "8c647266cc46c6ecd0155a0f341f7edac7d119ea"
        for state, operation in parser.parse_git(start_shasum + ".."):
            sig_status = state.get("sig_status", None)
            # %G?: show "G" for a Good signature, "B" for a Bad signature, "U" for a good, untrusted signature and "N" for no signature
            if sig_status not in "GU":
                log.info("Skipping commit %s: sig_status: %s, author: %s",
                         state.get("commit", "(unknown)"), sig_status, state.get("author_email", "(unknown)"))
                continue

            if operation['action'] == 'add':
                self.do_add(state, operation)
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
            elif operation['action'] == 'remove':
                self.do_remove(state, operation)
            #    if 'rt-ticket' in operation:
            #        self.out.write("# Commit " + state['commit'] + "\n")
            #        if role_is_dd(operation['role']):
            #            self.out.write("rt edit ticket/" + operation['rt-ticket'] +
            #                    " set queue=DSA\n")
            #        else:
            #            self.out.write("rt edit ticket/" + operation['rt-ticket'] +
            #                    " set queue=Keyring\n" +
            #                    "rt correspond -s resolved -m "+
            #                    "'This key has now been removed from the active DM keyring.' " +
            #                    operation['rt-ticket'] + "\n")
            elif operation['action'] == 'replace':
                self.do_replace(state, operation)
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
            else:
                print("UNKNOWN", repr(state), repr(operation))

        #start_date = datetime.datetime.utcnow() - datetime.timedelta(days=360)
        #gk = kmodels.GitKeyring()
        #gk.run_git("fetch")
        #for shasum, ts in gk.get_valid_shasums("--since", start_date.strftime("%Y-%m-%d")):
        #    c = gk.get_commit_message(shasum)
        #    if c is None: continue
        #    action = c.get("Action", None)
        #    if action is None:
        #        continue
        #    elif action == "add":
        #        role = c.get("Role", None)
        #        if role == "DM":
        #            self.do_add_dm(shasum, ts, c)
        #        elif role == "DD":
        #            self.do_add_dd(shasum, ts, c)
        #        else:
        #            log.warning("Unsupported role %s for %s action in %s", role, action, shasum)
        #    elif action == "replace":
        #        self.do_replace(shasum, ts, c)
        #    elif action == "FIXME-move":
        #        target = c.get("Target", None)
        #        if target == "emeritus":
        #            self.do_move_to_emeritus(shasum, ts, c)
        #        elif target == "removed":
        #            self.do_move_to_removed(shasum, ts, c)
        #        else:
        #            log.warning("Unsupported target %s for %s action in %s", target, action, shasum)
        #    else:
        #        log.warning("Unsupported action %s in %s", action, shasum)
