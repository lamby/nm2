# coding: utf-8




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

        # Keep an index mapping key IDs to fingerprints and keyring type
        self.by_fpr = {}
        self.by_keyid = {}
        duplicate_fprs = []
        duplicate_keyids = []
        for t in ("dm", "dd_u", "dd_nu", "emeritus_dd"):
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
        # Index Fingerprint objects by fingerprint
        fingerprints_by_fpr = {}
        for f in bmodels.Fingerprint.objects.select_related("person").all():
            if f.fpr.startswith("FIXME"): continue
            fingerprints_by_fpr[f.fpr] = f

        # Index keyring status by fingerprint
        keyring_by_status = {
            const.STATUS_DM: self.hk.keyrings.dm,
            const.STATUS_DD_U: self.hk.keyrings.dd_u,
            const.STATUS_DD_NU: self.hk.keyrings.dd_nu,
            const.STATUS_EMERITUS_DD: self.hk.keyrings.emeritus_dd,
        }
        keyring_by_fpr = {}
        for status, keyring in list(keyring_by_status.items()):
            for fpr in keyring:
                if fpr in keyring_by_fpr:
                    log.warn("%s: fingerprint %s is both in keyring %s and in keyring %s",
                             self.IDENTIFIER, fpr, status, keyring_by_fpr[fpr])
                else:
                    keyring_by_fpr[fpr] = status

        self.count = 0

        # Fingerprints that are not in any keyring
        no_keyring = set(fingerprints_by_fpr.keys()) - set(keyring_by_fpr.keys())
        for fpr in no_keyring:
            f = fingerprints_by_fpr[fpr]
            if not f.is_active: continue
            if f.person.status in (const.STATUS_REMOVED_DD, const.STATUS_DC, const.STATUS_DC_GA): continue
            log.warn("%s: %s has status %s in the database, but the key %s is not in any keyring",
                        self.IDENTIFIER, self.hk.link(f.person), const.ALL_STATUS_DESCS[f.person.status], fpr)
            self.count += 1

        # Fingerprints that are in some keyring
        both = set(fingerprints_by_fpr.keys()) & set(keyring_by_fpr.keys())
        for fpr in both:
            f = fingerprints_by_fpr[fpr]
            if not f.is_active: continue
            status = keyring_by_fpr[fpr]

            # Normalise dm/dm_ga
            pstatus = f.person.status
            if pstatus == const.STATUS_DM_GA: pstatus = const.STATUS_DM

            if pstatus != status:
                log.warn("%s: %s has status %s in the database, but the key is in %s keyring",
                            self.IDENTIFIER, self.hk.link(f.person), const.ALL_STATUS_DESCS[f.person.status], status)
                self.count += 1

        # Fingerprints that are not in the DB
        no_db = set(keyring_by_fpr.keys()) - set(fingerprints_by_fpr.keys())
        for fpr in no_db:
            status = keyring_by_fpr[fpr]
            if status == const.STATUS_REMOVED_DD: continue
            log.warn("%s: key %s is in %s keyring, but not in our db", self.IDENTIFIER, fpr, const.ALL_STATUS_DESCS[status])
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
    #    for keyring in "debian-keyring.gpg", "debian-maintainers.gpg", "debian-nonupload.gpg", "emeritus-keyring.gpg":
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
