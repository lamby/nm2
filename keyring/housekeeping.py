# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import django_housekeeping as hk
from django.conf import settings
from django.utils.timezone import utc, now
from django.db import transaction
from backend.housekeeping import MakeLink
import backend.models as bmodels
from backend import const
from . import models as kmodels
from .git import GitKeyring
from . import git_ops
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
        log.info("%s: Imported %d entries from dd_u keyring", self.IDENTIFIER, len(self.dd_u))
        self.dd_nu = frozenset(kmodels.list_dd_nu())
        log.info("%s: Imported %d entries from dd_nu keyring", self.IDENTIFIER, len(self.dd_nu))
        self.emeritus_dd = frozenset(kmodels.list_emeritus_dd())
        log.info("%s: Imported %d entries from emeritus_dd keyring", self.IDENTIFIER, len(self.emeritus_dd))
        self.removed_dd = frozenset(kmodels.list_removed_dd())
        log.info("%s: Imported %d entries from removed_dd keyring", self.IDENTIFIER, len(self.removed_dd))

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

class CleanUserKeys(hk.Task):
    """
    Remove old user keyrings
    """
    def run_main(self, stage):
        threshold = now() - datetime.timedelta(days=15)

        for key in kmodels.Key.objects.all():
            try:
                fpr = bmodels.Fingerprint.objects.get(fpr=key.fpr)
            except bmodels.Fingerprint.DoesNotExist:
                fpr = None

            in_use = fpr is not None and fpr.is_active and (fpr.person.pending or fpr.person.active_processes)
            if in_use: continue

            if key.key_updated < threshold:
                log.info("%s: removing old key %s", self.IDENTIFIER, key.fpr)
                key.delete()


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
        KEYRING_MAINT_KEYRING = os.path.abspath(getattr(settings, "KEYRING_MAINT_KEYRING", "data/keyring-maint.gpg"))

        # Get the Person entries for keyring-maint people, indexed by the email
        # that they use in git commits.
        self.persons = {}
        for entry in self.KEYRING_MAINT_MEMBERS:
            for email in entry["email"]:
                self.persons[email] = bmodels.Person.objects.get(uid=entry["uid"])

        # Regenerate the keyring in a new directory
        tmpdir = KEYRING_MAINT_KEYRING + ".tmp"
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
        if os.path.exists(KEYRING_MAINT_KEYRING):
            shutil.rmtree(KEYRING_MAINT_KEYRING)

        # Move the new directory to the destination place
        os.rename(tmpdir, KEYRING_MAINT_KEYRING)


class KeyringGit(hk.Task):
    """
    Update the local keyring repository
    """
    NAME = "keyring_git"

    DEPENDS = [KeyringMaint]

    def run_main(self, stage):
        self.keyring = GitKeyring()
        self.keyring.git.fetch()


class CheckKeyringLogs(hk.Task):
    """
    Import changes from the signed parts of the keyring git log
    """
    DEPENDS = [MakeLink, KeyringMaint, KeyringGit]

    def run_main(self, stage):
        """
        Parse changes from changelog entries after the given date (non inclusive).
        """
        gk = self.hk.keyring_git.keyring
        actions = list(gk.read_log("keyring_maint_import..remotes/origin/master"))
        for entry in actions[::-1]:
            if entry.parsed is None: continue

            try:
                op = git_ops.Operation.from_log_entry(entry)
            except git_ops.ParseError as e:
                log.warn("%s: commit %s: parse error: %s", self.IDENTIFIER, entry.shasum, e)
                break

            if op is None: continue

            try:
                ops = list(op.ops())
            except git_ops.OperationError as e:
                log.warn("%s: commit %s: error computing changes to apply: %s", self.IDENTIFIER, entry.shasum, e)
                break

            for op in ops:
                with transaction.atomic():
                    op.execute()

            # Update our bookmark
            gk.git.update_ref("refs/heads/keyring_maint_import", entry.shasum)
            log.info("%s: Updating ref keyring_maint_import to commit %s", self.IDENTIFIER, entry.shasum)
