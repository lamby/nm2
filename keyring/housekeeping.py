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
from backend.housekeeping import MakeLink
import backend.models as bmodels
from backend import const
from . import models as kmodels
from .keyring_maint_import import KeyringMaintImport
import os
import os.path
import time
import shutil
import subprocess
import datetime
import pipes
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
    DEPENDS = [Keyrings, MakeLink]

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
                    log.warn("%s: %s has status %s in the database, but the key is in %s keyring",
                             self.IDENTIFIER, self.hk.link(p), const.ALL_STATUS_DESCS[p.status], status)
                    self.count += 1
                    found = True
                    break
            if not found and p.status != const.STATUS_REMOVED_DD:
                log.warn("%s: %s has status %s in the database, but the key is not in any keyring",
                         self.IDENTIFIER, self.hk.link(p), const.ALL_STATUS_DESCS[p.status])
                self.count += 1

        # Spot fingerprints not in our DB
        for status, keyring in keyring_by_status.iteritems():
            # TODO: not quite sure how to handle the removed_dd keyring, until I
            #       know what exactly is in there
            if status == const.STATUS_REMOVED_DD: continue
            for fpr in keyring:
                if fpr not in people_by_fpr:
                    log.warn("%s: key %s is in %s keyring, but not in our db",
                             self.IDENTIFIER, fpr, status)
                    self.count += 1

    def log_stats(self):
        log.warn("%s: %d mismatches between keyring and nm.debian.org databases",
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
            "email": ["noodles@earth.li"],
        },
        {
            "uid": "gwolf",
            "fpr": "AB41C1C68AFD668CA045EBF8673A03E4C1DB921F",
            "email": ["gwolf@debian.org", "gwolf@gwolf.org"],
        },
        {
            "uid": "dkg",
            "fpr": "0EE5BE979282D80B9F7540F1CCD2ED94D21739E9",
            "email": ["dkg@openflows.com", "dkg@fifthhorseman.net"],
        },
    ]

    NAME = "keyring_maint"

    def run_main(self, stage):
        # Get the Person entries for keyring-maint people, indexed by the email
        # that they use in git commits.
        self.persons = {}
        for entry in self.KEYRING_MAINT_MEMBERS:
            for email in entry["email"]:
                self.persons[email] = bmodels.Person.objects.get(uid=entry["uid"])

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
    DEPENDS = [MakeLink, KeyringMaint, KeyringGit]

    def run_main(self, stage):
        """
        Parse changes from changelog entries after the given date (non inclusive).
        """
        importer = KeyringMaintImport(self.IDENTIFIER, self.hk.keyring_maint.persons, self.hk.link)
        gk = self.hk.keyring_git.keyring
        parser = gk.get_changelog_parser()
        actions = list(parser.parse_git("keyring_maint_import..remotes/origin/master"))
        for state, operation in reversed(actions):
            sig_status = state.get("sig_status", None)
            # %G?: show "G" for a Good signature, "B" for a Bad signature, "U" for a good, untrusted signature and "N" for no signature
            if sig_status not in "GU":
                log.info("%s: Skipping commit %s: sig_status: %s, author: %s",
                         self.IDENTIFIER, state.get("commit", "(unknown)"), sig_status, state.get("author_email", "(unknown)"))
                continue

            if operation['action'] == 'add':
                processed = importer.do_add(state, operation)
            elif operation['action'] == 'remove':
                processed = importer.do_remove(state, operation)
            elif operation['action'] == 'replace':
                processed = importer.do_replace(state, operation)
            else:
                log.warn("%s: Unknown action %s in commit %s", self.IDENTIFIER, operation["action"], state["commit"])
                processed = False

            if processed:
                # Update our bookmark
                gk.run_git("update-ref", "refs/heads/keyring_maint_import", state["commit"])
                log.info("%s: Updating ref keyring_maint_import to commit %s", self.IDENTIFIER, state["commit"])
            else:
                break

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
