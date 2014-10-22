# coding: utf-8
# nm.debian.org keyring access functions
#
# Copyright (C) 2012--2013  Enrico Zini <enrico@debian.org>
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
"""
Code used to list entries in keyrings
"""

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.db import models
from django.conf import settings
from django.utils.timezone import utc
import os
import os.path
import subprocess
from collections import namedtuple
from backend.utils import StreamStdoutKeepStderr, require_dir
import time
import re
import datetime
import logging

log = logging.getLogger(__name__)

KEYRINGS = getattr(settings, "KEYRINGS", "/srv/keyring.debian.org/keyrings")
KEYRINGS_TMPDIR = getattr(settings, "KEYRINGS_TMPDIR", "/srv/keyring.debian.org/data/tmp_keyrings")
#KEYSERVER = getattr(settings, "KEYSERVER", "keys.gnupg.net")
KEYSERVER = getattr(settings, "KEYSERVER", "pgp.mit.edu")
KEYRING_MAINT_KEYRING = getattr(settings, "KEYRING_MAINT_KEYRING", "data/keyring-maint.gpg")
KEYRING_MAINT_GIT_REPO = getattr(settings, "KEYRING_MAINT_GIT_REPO", "data/keyring-maint.git")

#WithFingerprint = namedtuple("WithFingerprint", (
#    "type", "trust", "bits", "alg", "id", "created", "expiry",
#    "misc8", "ownertrust", "uid", "sigclass", "cap", "misc13",
#    "flag", "misc15"))

Uid = namedtuple("Uid", ("name", "email", "comment"))

class GPG(object):
    def __init__(self, homedir=None):
        self.homedir = homedir

    def _base_cmd(self):
        cmd = ["/usr/bin/gpg"]
        if self.homedir is not None:
            cmd.append("--homedir")
            cmd.append(self.homedir)
        cmd.extend(("-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb",
            "--trust-model", "always", "--with-colons", "--fixed-list-mode",
            "--with-fingerprint", "--no-permission-warning"))
        return cmd

    def cmd(self, *args):
        cmd = self._base_cmd()
        cmd.extend(args)
        return cmd

    def keyring_cmd(self, keyrings, *args):
        """
        Build a gpg invocation command using the given keyring, or sequence of
        keyring names
        """
        # If we only got one string, make it into a sequence
        if isinstance(keyrings, basestring):
            keyrings = (keyrings, )
        cmd = self._base_cmd()
        for k in keyrings:
            cmd.append("--keyring")
            cmd.append(os.path.join(KEYRINGS, k))
        cmd.extend(args)
        return cmd

    def has_key(self, keyrings, fpr):
        """
        Check if a fingerprint exists in a keyring
        """
        cmd = self.keyring_cmd(keyrings, "--list-keys", fpr)
        stdout, stderr, result = self.run_cmd(cmd)
        present = None
        if result == 0:
            return True
        elif result == 2:
            return False
        else:
            raise RuntimeError("gpg exited with status %d: %s" % (result, stderr.strip()))

    def fetch_key(self, fpr, dest_keyring):
        """
        Fetch the key with the given fingerprint into the given keyring
        """
        cmd = self.keyring_cmd(dest_keyring, "--keyserver", KEYSERVER, "--recv-keys", fpr)
        stdout, stderr, result = self.run_cmd(cmd)
        if result != 0:
            raise RuntimeError("gpg exited with status %d: %s" % (result, stderr.strip()))

    def run_cmd(self, cmd, input=None):
        """
        Run gpg with the given command, waiting for its completion, returning a triple
        (stdout, stderr, result)
        """
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate(input=input)
        result = proc.wait()
        return stdout, stderr, result

    def pipe_cmd(self, cmd):
        """
        Run gpg with the given command, returning a couple
        (proc, lines)
        where proc is the subprocess.Popen object, and lines is a
        backend.utils.StreamStdoutKeepStderr object connected to proc.
        """
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        proc.stdin.close()
        lines = StreamStdoutKeepStderr(proc)
        return proc, lines

def _check_keyring(keyring, fpr):
    """
    Check if a fingerprint exists in a keyring
    """
    gpg = GPG()
    return gpg.has_key(keyring, fpr)

def _list_keyring(keyring):
    """
    List all fingerprints in a keyring
    """
    gpg = GPG()
    cmd = gpg.keyring_cmd(keyring, "--list-keys")
    proc, lines = gpg.pipe_cmd(cmd)
    for line in lines:
        try:
            line = line.decode('utf8')
        except:
            try:
                line = line.decode('iso8859-1')
            except:
                line = line.decode('utf8', 'replace')
        if not line.startswith("fpr"): continue
        yield line.split(":")[9]
    result = proc.wait()
    if result != 0:
        raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))

# def _parse_list_keys_line(line):
#     res = []
#     for i in line.split(":"):
#         if not i:
#             res.append(None)
#         else:
#             i = i.decode("string_escape")
#             try:
#                 i = i.decode("utf-8")
#             except UnicodeDecodeError:
#                 pass
#             res.append(i)
#     for i in range(len(res), 15):
#         res.append(None)
#     return WithFingerprint(*res)


# def _list_full_keyring(keyring):
#     keyring = os.path.join(KEYRINGS, keyring)
#
#     cmd = [
#         "gpg",
#         "-q", "--no-options", "--no-default-keyring", "--no-auto-check-trustdb", "--trust-model", "always",
#         "--keyring", keyring,
#         "--with-colons", "--with-fingerprint", "--list-keys",
#     ]
#     #print " ".join(cmd)
#     proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
#     proc.stdin.close()
#     lines = StreamStdoutKeepStderr(proc)
#     fprs = []
#     for line in lines:
#         yield _parse_list_keys_line(line)
#     result = proc.wait()
#     if result != 0:
#         raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))

# def uid_info(keyring):
#     re_uid = re.compile(r"^(?P<name>.+?)\s*(?:\((?P<comment>.+)\))?\s*(?:<(?P<email>.+)>)?$")
#
#     fpr = None
#     for l in _list_full_keyring(keyring):
#         if l.type == "pub":
#             fpr = None
#         elif l.type == "fpr":
#             fpr = l.uid
#         elif l.type == "uid":
#             # filter out revoked/expired uids
#             if 'r' in l.trust or 'e' in l.trust:
#                 continue
#             # Parse uid
#             mo = re_uid.match(l.uid)
#             u = Uid(mo.group("name"), mo.group("email"), mo.group("comment"))
#             if not mo:
#                 log.warning("Cannot parse uid %s for key %s in keyring %s" % (l.uid, fpr, keyring))
#             else:
#                 yield fpr, u

def is_dm(fpr):
    return _check_keyring("debian-maintainers.gpg", fpr)

def is_dd_u(fpr):
    return _check_keyring("debian-keyring.gpg", fpr)

def is_dd_nu(fpr):
    return _check_keyring("debian-nonupload.gpg", fpr)


def list_dm():
    return _list_keyring("debian-maintainers.gpg")

def list_dd_u():
    return _list_keyring("debian-keyring.gpg")

def list_dd_nu():
    return _list_keyring("debian-nonupload.gpg")

def list_emeritus_dd():
    return _list_keyring("emeritus-keyring.gpg")

def list_removed_dd():
    return _list_keyring("removed-keys.pgp")

class Key(object):
    """
    Collects data about a key, parsed from gpg --with-colons --fixed-list-mode
    """
    def __init__(self, fpr, pub):
        self.pub = pub
        self.fpr = fpr
        self.uids = {}
        self.subkeys = {}

    def get_uid(self, uid):
        uidfpr = uid[7]
        res = self.uids.get(uidfpr, None)
        if res is None:
            self.uids[uidfpr] = res = Uid(self, uid)
        return res

    def add_sub(self, sub):
        subfpr = tuple(sub[3:6])
        self.subkeys[subfpr] = sub

    def keycheck(self):
        return KeycheckKeyResult(self)

    @classmethod
    def read_from_gpg(cls, lines):
        """
        Run the given gpg command and read key and signature data from its output
        """
        keys = {}
        pub = None
        cur_key = None
        cur_uid = None
        for lineno, line in enumerate(lines, start=1):
            if line.startswith(b"pub:"):
                # Keep track of this pub record, to correlate with the following
                # fpr record
                pub = line.split(b":")
                cur_key = None
                cur_uid = None
            elif line.startswith(b"fpr:"):
                # Correlate fpr with the previous pub record, and start gathering
                # information for a new key
                if pub is None:
                    raise Exception("gpg:{}: found fpr line with no previous pub line".format(lineno))
                fpr = line.split(b":")[9]
                cur_key = keys.get(fpr, None)
                if cur_key is None:
                    keys[fpr] = cur_key = cls(fpr, pub)
                pub = None
                cur_uid = None
            elif line.startswith(b"uid:"):
                if cur_key is None:
                    raise Exception("gpg:{}: found uid line with no previous pub+fpr lines".format(lineno))
                cur_uid = cur_key.get_uid(line.split(b":"))
            elif line.startswith(b"sig:"):
                if cur_uid is None:
                    raise Exception("gpg:{}: found sig line with no previous uid line".format(lineno))
                cur_uid.add_sig(line.split(b":"))
            elif line.startswith(b"sub:"):
                if cur_key is None:
                    raise Exception("gpg:{}: found sub line with no previous pub+fpr lines".format(lineno))
                cur_key.add_sub(line.split(b":"))

        return keys.itervalues()

class Uid(object):
    """
    Collects data about a key uid, parsed from gpg --with-colons --fixed-list-mode
    """
    re_uid = re.compile(r"^(?P<name>.+?)\s*(?:\((?P<comment>.+)\))?\s*(?:<(?P<email>.+)>)?$")

    def __init__(self, key, uid):
        self.key = key
        self.uid = uid
        self.name = uid[9].decode("utf8", "replace")
        self.sigs = {}

    def add_sig(self, sig):
        # FIXME: missing a full fingerprint, we try to index with as much
        # identifying data as possible
        k = tuple(sig[3:6])
        self.sigs[k] = sig

    def split(self):
        mo = self.re_uid.match(self.name)
        if not mo: return None
        return {
                "name": mo.group("name"),
                "email": mo.group("email"),
                "comment": mo.group("comment"),
        }

class KeycheckKeyResult(object):
    """
    Perform consistency checks on a key, based on the old keycheck.sh
    """
    def __init__(self, key):
        self.key = key
        self.uids = []
        self.errors = set()
        self.capabilities = {}

        # Check key type from fingerprint length
        if len(key.fpr) == 32:
            self.errors.add("ver3")

        # pub:f:1024:17:C5AF774A58510B5A:2004-04-17:::-:Christoph Berg <cb@df7cb.de>::scESC:

        # Check key size
        keysize = int(key.pub[2])
        if keysize >= 4096:
            pass
        elif keysize >= 2048:
            self.errors.add("key_size_2048")
        else:
            self.errors.add("key_size_small")

        # Check key algorithm
        keyalgo = int(key.pub[3])
        if keyalgo == 1:
            pass
        elif keyalgo == 17:
            self.errors.add("key_algo_dsa")
        else:
            self.errors.add("key_algo_unknown")

        # Check key flags
        flags = key.pub[1]
        if "i" in flags: self.errors.update(("skip", "key_invalid"))
        if "d" in flags: self.errors.update(("skip", "key_disabled"))
        if "r" in flags: self.errors.update(("skip", "key_revoked"))
        if "t" in flags: self.errors.update(("skip", "key_expired"))

        # Check UIDs
        for uid in key.uids.itervalues():
            self.uids.append(KeycheckUidResult(self, uid))

        def int_expire(x):
            if x is None or x == "": return x
            return int(x)

        def max_expire(a, b):
            """
            Pick the maximum expiration indication between the two.
            a and b can be:
                None: nothing known (sorts lowest)
                number: an expiration timestamp
                "": no expiration (sorts highest)
            """
            if a is None: return int_expire(b)
            if b is None: return int_expire(a)
            if a == "": return int_expire(a)
            if b == "": return int_expire(b)
            return max(int(a), int(b))

        # Check capabilities
        for cap in "es":
            # Check in primary key
            if cap in key.pub[11]:
                self.capabilities[cap] = int_expire(key.pub[6])

            # Check in subkeys
            for sk in key.subkeys.itervalues():
                if cap in sk[11]:
                    oldcap = self.capabilities.get(cap, None)
                    self.capabilities[cap] = max_expire(oldcap, sk[6])

        cutoff = time.time() + 86400 * 90

        c = self.capabilities.get("e", None)
        if c is None:
            self.errors.add("key_encryption_missing")
        elif c is not "" and c < cutoff:
            self.errors.add("key_encryption_expires_soon")

        c = self.capabilities.get("s", None)
        if c is None:
            self.errors.add("key_signing_missing")
        elif c is not "" and c < cutoff:
            self.errors.add("key_signing_expires_soon")


class KeycheckUidResult(object):
    """
    Perform consistency checks on a key uid, based on the old keycheck.sh
    """
    def __init__(self, key_result, uid):
        self.key_result = key_result
        self.uid = uid
        self.errors = set()

        # uid:q::::1241797807::73B85305F2B11D695B610022AF225CCBC6B3F6D9::Enrico Zini <enrico@enricozini.org>:

        # Check uid flags

        flags = uid.uid[1]
        if "i" in flags: self.errors.update(("skip", "uid_invalid"))
        if "d" in flags: self.errors.update(("skip", "uid_disabled"))
        if "r" in flags: self.errors.update(("skip", "uid_revoked"))
        if "t" in flags: self.errors.update(("skip", "uid_expired"))

        # Check signatures
        self.sigs_ok = []
        self.sigs_no_key = []
        self.sigs_bad = []
        for sig in uid.sigs.itervalues():
            # Skip self-signatures
            if self.key_result.key.fpr.endswith(sig[4]): continue
            # dkg says:
            # ! means "verified"
            # - means "not verified" (bad signature, signature from expired key)
            # ? means "signature from a key we don't have"
            if sig[1] == "?" or sig[1] == "-":
                self.sigs_no_key.append(sig)
            elif sig[1] == "!":
                self.sigs_ok.append(sig)
            else:
                self.sigs_bad.append(sig)

class UserKey(object):
    """
    Manage a temporary keyring use to work with the key of a user that is not
    in any of the main keyrings.
    """
    def __init__(self, fpr):
        """
        Create/access a temporary keyring dir for the given fingerprint.

        IMPORTANT: make sure that fpr is validated to a sequence of A-Fa-f0-9, as
        it will be passed to os.path.join unchecked
        """
        self.fpr = fpr
        self.pathname = os.path.join(KEYRINGS_TMPDIR, fpr)
        require_dir(self.pathname, mode=0770)
        self.gpg = GPG(homedir=self.pathname)
        self.keyring = os.path.join(self.pathname, "user.gpg")

    def has_key(self):
        """
        Check if we already have the key
        """
        return self.gpg.has_key(self.keyring, self.fpr)

    def refresh(self):
        """
        Fetch/refresh the key
        """
        self.gpg.fetch_key(self.fpr, self.keyring)

    def want_key(self):
        """
        Make sure that we have the key, no matter how old
        """
        if not self.has_key():
            self.refresh()

    def getmtime(self):
        """
        Return the modification time of the keyring. This can be used to check
        how fresh is the key.

        Returns 0 if the file is not there.
        """
        try:
            return os.path.getmtime(self.keyring)
        except OSError as e:
            import errno
            if e.errno == errno.ENOENT:
                return 0
            raise

    def encrypt(self, data):
        """
        Encrypt the given data with this key, returning the ascii-armored
        encrypted result.
        """
        cmd = self.gpg.keyring_cmd(self.keyring, "--encrypt", "--armor", "--no-default-recipient",
                "--trust-model=always", "--recipient", self.fpr)
        stdout, stderr, result = self.gpg.run_cmd(cmd, input=data)
        if result != 0:
            raise RuntimeError("gpg exited with status %d: %s" % (result, stderr.strip()))
        return stdout

    def keycheck(self):
        """
        This little (and maybe bad) function is used to check keys from NM's.

        First it downloads the key of the NM from a keyserver in the local nm.gpg
        file.

        Then it shows the key and all signatures made by existing Debian
        Developers.

        Finally, it checks to make sure that the key has encryption and
        signature capabilities, and will continue to have them one month
        into the future.
        """
        # Based on keycheck,sh by
        # Joerg Jaspert <joerg@debian.org>,
        # Daniel Kahn Gillmor <dkg@fifthhorseman.net>,
        # and others.

        # Check key
        cmd = self.gpg.keyring_cmd(("debian-keyring.gpg", "debian-nonupload.gpg"), "--keyring", self.keyring, "--check-sigs", self.fpr)
        proc, lines = self.gpg.pipe_cmd(cmd)
        for key in Key.read_from_gpg(lines):
            yield key.keycheck()

        result = proc.wait()
        if result != 0:
            raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))

class Changelog(object):
    re_date = re.compile("^\d+-\d+-\d+$")
    re_datetime = re.compile("^\d+-\d+-\d+ \d+:\d+:\d+$")
    re_empty = re.compile(r"^\s*$")
    re_author = re.compile(r"^\s+\[")

    def _parse_date(self, s):
        import rfc822
        if self.re_date.match(s):
            try:
                return datetime.datetime.strptime(s, "%Y-%m-%d")
            except ValueError:
                date = rfc822.parsedate(s)
        elif self.re_datetime.match(s):
            try:
                return datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                date = rfc822.parsedate(s)
        else:
            date = rfc822.parsedate(s)

        if date is None:
            return None
        return datetime.datetime(*date[:6])

    def _group_lines_by_indentation(self, lines):
        """
        Split a changelog entry into line groups based on indentation
        """
        def get_indent(s):
            """
            Count how many leading spaces there are in s
            """
            res = 0
            for c in s:
                if not c.isspace(): break
                res += 1
            return res

        group = []
        indent = None
        for l in lines:
            if self.re_empty.match(l):
                if group: yield group
                group = []
                indent = None
                continue

            if self.re_author.match(l):
                if group: yield group
                group = []
                indent = None
                continue

            i = get_indent(l)

            if indent is None:
                indent = i
            elif i <= indent:
                if group: yield group
                group = []
                indent = i

            group.append(l)

        if group:
            yield group

    def read(self, since=None):
        """
        Read and parse the keyring changelogs
        """
        from debian import changelog

        fname = os.path.join(KEYRINGS, "../changelog")
        if os.path.isfile(fname):
            with open(fname) as fd:
                changes = changelog.Changelog(file=fd)
        else:
            changes = []

        for c in changes:
            d = self._parse_date(c.date)
            if since is not None and d <= since: continue
            for lines in self._group_lines_by_indentation(c.changes()):
                yield d, lines


class GitKeyring(object):
    """
    Access the git repository of keyring-maint
    """
    # http://mikegerwitz.com/papers/git-horror-story
    re_update_changelog = re.compile(r"Update changelog", re.I)
    re_import_changes = re.compile(r"Import changes sent to keyring.debian.org HKP interface", re.I)
    re_field_split = re.compile(r":\s*")
    re_summaries = [
        {
            "re": re.compile(r"Add new (?P<role>[A-Z]+) key 0x(?P<key>[0-9A-F]+) \((?P<subj>[^)]+)\) \(RT #(?P<rt>\d+)\)"),
            "proc": lambda x: { "Action": "add", "Role": x.group("role"), "New-Key": x.group("key"), "Subject": x.group("subj"), "RT-Ticket": x.group("rt") },
        },
        {
            "re": re.compile(r"Replace 0x(?P<old>[0-9A-F]+) with 0x(?P<new>[0-9A-F]+) \((?P<subj>[^)]+)\) \(RT #(?P<rt>\d+)\)"),
            "proc": lambda x: { "Action": "replace", "Old-key": x.group("old"), "New-key": x.group("new"), "Subject": x.group("subj"), "RT-Ticket": x.group("rt") },
        },
    ]

    def run_git(self, *args):
        """
        Run git in the keyring git repo, with GNUPGHOME set to the
        keyring-maint keyring.

        Returns stdout if everything was fine, otherwise it throws an
        exception.
        """
        cmdline = ["git"]
        cmdline.extend(args)
        env = dict(os.environ)
        env["GNUPGHOME"] = KEYRING_MAINT_KEYRING
        proc = subprocess.Popen(cmdline, cwd=KEYRING_MAINT_GIT_REPO, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        res = proc.wait()
        if res != 0:
            raise RuntimeError("{} returned error code {}. Stderr: {}", cmdline, res, stderr)
        return stdout

    def get_valid_shasums(self, *args):
        """
        Run git log on the keyring dir and return the valid shasums that it found.

        Extra git log options passed as *args will be appended to the command line
        """
        for line in self.run_git("log", "--pretty=format:%H:%ct:%G?", *args).split("\n"):
            shasum, ts, validated = line.split(":")
            # "G" for a Good signature, "B" for a Bad signature, "U" for a good, untrusted signature and "N" for no signature
            if validated in "GU":
                yield shasum, datetime.datetime.fromtimestamp(int(ts), utc)

    def get_commit_message(self, shasum):
        """
        Return the commit message for the given shasum
        """
        body = self.run_git("show", "--pretty=format:%B", shasum).decode("utf-8")
        subject, body = body.split("\n\n", 1)
        if self.re_update_changelog.match(subject): return None
        if self.re_import_changes.match(subject): return None
        if body.startswith("Action:"):
            return { k: v for k, v in self.parse_action(body) }
        else:
            for match in self.re_summaries:
                mo = match["re"].match(subject)
                if mo: return match["proc"](mo)
            #print("UNKNOWN", repr(subject))
            return None

    def parse_action(self, body):
        """
        Parse an Action: * body
        """
        name = None
        cur = []
        for line in body.split("\n"):
            if not line: break
            if not line[0].isspace():
                if name:
                    yield name, cur
                    name = None
                    cur = []
                name, content = self.re_field_split.split(line, 1)
                cur.append(content)
            else:
                cur.append(line.lstrip())

        if name:
            yield name, cur
