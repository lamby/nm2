# coding: utf-8
"""
Code used to list entries in keyrings
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.db import models
from django.conf import settings
from django.utils.timezone import utc, now
import io
import os
import os.path
import subprocess
from collections import namedtuple
from backend.utils import StreamStdoutKeepStderr, require_dir
from backend.models import FingerprintField
import time
import re
import datetime
import shutil
import tempfile
from six.moves.urllib.parse import urlencode
import six
import json
import requests
from six.moves import shlex_quote
from contextlib import contextmanager
import logging

log = logging.getLogger(__name__)

KEYRINGS = getattr(settings, "KEYRINGS", "/srv/keyring.debian.org/keyrings")
KEYRINGS_TMPDIR = getattr(settings, "KEYRINGS_TMPDIR", "/srv/keyring.debian.org/data/tmp_keyrings")
#KEYSERVER = getattr(settings, "KEYSERVER", "keys.gnupg.net")
KEYSERVER = getattr(settings, "KEYSERVER", "pgp.mit.edu")
#KEYSERVER = getattr(settings, "KEYSERVER", "www.example.org")


@contextmanager
def tempdir_gpg():
    homedir = tempfile.mkdtemp(dir=KEYRINGS_TMPDIR)
    try:
        gpg = GPG(homedir=homedir, use_default_keyring=True)
        yield gpg
    finally:
        shutil.rmtree(homedir, ignore_errors=True)


class KeyManager(models.Manager):
    def download(self, fpr):
        """
        Download key material by fingerprint, returning its ASCII-armored version.

        It passes the result to GPG to validate at least that there is key
        material with the right fingerprint.
        """
        # See https://tools.ietf.org/html/draft-shaw-openpgp-hkp-00
        url = "http://{server}/pks/lookup?{query}".format(
            server=KEYSERVER,
            query=urlencode({
                "op": "get",
                "search": "0x" + fpr,
                "exact": "on",
                "options": "mr",
            }))
        #import traceback
        #traceback.print_stack()
        #print("Download from", url)
        res = requests.get(url)
        try:
            res.raise_for_status()
        except Exception as e:
            raise RuntimeError("GET {} failed: {}".format(url, e))
        text = res.text.splitlines()
        if not text: raise RuntimeError("empty response from key server")
        if text[0] != "-----BEGIN PGP PUBLIC KEY BLOCK-----": raise RuntimeError("downloaded key material has invalid begin line")
        if text[-1] != "-----END PGP PUBLIC KEY BLOCK-----": raise RuntimeError("downloaded key material has invalid end line")
        with tempdir_gpg() as gpg:
            gpg.run_checked(gpg.cmd("--import"), input=res.text)
            return gpg.run_checked(gpg.cmd("--export", "-a", fpr)).decode("utf-8", errors="replace")

    def test_preload(self, fpr):
        """
        Load a key material from test keys in test_data/

        This is used to prevent hitting the keyservers in unit tests when not
        explicitly testing key downloads.
        """
        keyfile = os.path.join("test_data", fpr + ".txt")
        with io.open(keyfile, "rt", encoding="utf-8") as fd:
            body = fd.read()
        self.get_or_create(fpr=fpr, defaults={"key": body, "key_updated": now()})

    def get_or_download(self, fpr, body=None):
        try:
            return self.get(fpr=fpr)
        except self.model.DoesNotExist:
            pass

        if body is None:
            body = self.download(fpr)

        return self.create(fpr=fpr, key=body, key_updated=now())


class Key(models.Model):
    fpr = FingerprintField(verbose_name="OpenPGP key fingerprint", max_length=40, unique=True)
    key = models.TextField(verbose_name="ASCII armored key material")
    key_updated = models.DateTimeField(verbose_name="Datetime when the key material was downloaded")
    check_sigs = models.TextField(verbose_name="gpg --check-sigs results", blank=True)
    check_sigs_updated = models.DateTimeField(verbose_name="Datetime when the check_sigs data was computed", null=True)

    objects = KeyManager()

    def key_is_fresh(self):
        return self.key_updated > now() - datetime.timedelta(minutes=5)

    def update_key(self):
        self.key = Key.objects.download(fpr=self.fpr)
        self.key_updated = now()
        self.save()

    def update_check_sigs(self):
        """
        This little (and maybe bad) function is used to check keys.

        It computes the key and all signatures made by existing Debian
        Developers.

        Then, it checks to make sure that the key has encryption and signature
        capabilities, and will continue to have them one month into the future.
        """
        # Based on keycheck.sh by
        # Joerg Jaspert <joerg@debian.org>,
        # Daniel Kahn Gillmor <dkg@fifthhorseman.net>,
        # and others.
        with tempdir_gpg() as gpg:
            gpg.run_checked(gpg.cmd("--import"), input=self.key)

            # Check key
            cmd = gpg.keyring_cmd(("debian-keyring.gpg", "debian-nonupload.gpg"), "--check-sigs", self.fpr)
            self.check_sigs = gpg.run_checked(cmd).decode("utf-8", errors="replace")
            self.check_sigs_updated = now()
        self.save()

    def encrypt(self, data):
        """
        Encrypt the given data with this key, returning the ascii-armored
        encrypted result.
        """
        with tempdir_gpg() as gpg:
            gpg.run_checked(gpg.cmd("--import"), input=self.key)
            cmd = gpg.cmd("--encrypt", "--armor", "--no-default-recipient", "--trust-model=always", "--recipient", self.fpr)
            return gpg.run_checked(cmd, input=data)

    def verify(self, data):
        if data.strip().startswith("-----BEGIN PGP SIGNED MESSAGE-----"):
            return self.verify_clearsigned(data)
        else:
            return self.verify_rfc3156(data)

    def verify_detached(self, data, signature):
        """
        Verify data using a detached signature
        """
        # See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=826405
        with tempdir_gpg() as gpg:
            gpg.run_checked(gpg.cmd("--import"), input=self.key)
            data_file = os.path.join(gpg.homedir, "data.txt")
            sig_file = os.path.join(gpg.homedir, "data.txt.asc")
            status_log = os.path.join(gpg.homedir, "status.log")
            logger_log = os.path.join(gpg.homedir, "logger.log")
            with io.open(data_file, "wb") as fd:
                fd.write(data)
            with io.open(sig_file, "wb") as fd:
                fd.write(signature)
            with io.open(status_log, "wb") as fd_status:
                with io.open(logger_log, "wb") as fd_logger:
                    cmd = gpg.cmd("--status-fd", str(fd_status.fileno()), "--logger-fd", str(fd_logger.fileno()), "--verify", sig_file, data_file)
                    stdout, stderr, result = gpg.run_cmd(cmd)

            if result != 0:
                errors = []
                with io.open(status_log, "rt", encoding="utf-8", errors="replace") as fd:
                    for line in fd:
                        if not line.startswith("[GNUPG:]"): continue
                        errors.append(line[8:])

                if errors:
                    errmsg = "; ".join(errors)
                else:
                    errmsg = stderr
                    with io.open(logger_log, "rt", encoding="utf-8", errors="replace") as fd:
                        errmsg += fd.read()

                raise RuntimeError("gpg exited with status {}: {}".format(result, errmsg))

            with io.open(status_log, "rt", encoding="utf-8", errors="replace") as fd:
                status = fd.read()

            if "VALIDSIG" not in status and "GOODSIG" not in status:
                raise RuntimeError("VALIDSIG or GOODSIG not found in gpg output")

            return data

    def verify_clearsigned(self, data):
        """
        Verify a signed text with this key, returning the signed payload
        """
        # See https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=826405
        with tempdir_gpg() as gpg:
            gpg.run_checked(gpg.cmd("--import"), input=self.key)
            data_file = os.path.join(gpg.homedir, "data.txt")
            status_log = os.path.join(gpg.homedir, "status.log")
            logger_log = os.path.join(gpg.homedir, "logger.log")
            with io.open(data_file, "wt", encoding="utf-8") as fd:
                fd.write(data)
            with io.open(status_log, "wb") as fd_status:
                with io.open(logger_log, "wb") as fd_logger:
                    cmd = gpg.cmd("--status-fd", str(fd_status.fileno()), "--logger-fd", str(fd_logger.fileno()), "--decrypt", data_file)
                    plaintext, stderr, result = gpg.run_cmd(cmd)

            if result != 0:
                errors = []
                with io.open(status_log, "rt", encoding="utf-8", errors="replace") as fd:
                    for line in fd:
                        if not line.startswith("[GNUPG:]"): continue
                        errors.append(line[8:])

                if errors:
                    errmsg = "; ".join(errors)
                else:
                    errmsg = stderr
                    with io.open(logger_log, "rt", encoding="utf-8", errors="replace") as fd:
                        errmsg += fd.read()

                raise RuntimeError("gpg exited with status {}: {}".format(result, errmsg))

            with io.open(status_log, "rt", encoding="utf-8", errors="replace") as fd:
                status = fd.read()

            if "VALIDSIG" not in status and "GOODSIG" not in status:
                raise RuntimeError("VALIDSIG or GOODSIG not found in gpg output")

            return plaintext.decode("utf-8", errors="replace")

    def verify_rfc3156(self, data):
        """
        Verify a RFC3156 signed emails.

        Returns the verified signed payload, which is usually a MIME-encoded
        message.
        """
        from .openpgp import RFC3156
        msg = RFC3156(data)
        if not msg.parsed: raise RuntimeError("OpenPGP MIME data not found")
        self.verify_detached(msg.text_data, msg.sig_data)

    def keycheck(self):
        if not self.check_sigs:
            self.update_check_sigs()

        # Check the key data and signatures
        keys = KeyData.read_from_gpg(self.check_sigs.splitlines())

        # There should only be keycheck data for the fingerprint we gave gpg
        keydata = keys.get(self.fpr, None)
        if keydata is None:
            raise RuntimeError("keycheck results not found for fingerprint " + self.fpr)

        return KeycheckKeyResult(keydata)


class GPG(object):
    """
    Run GnuPG commands and parse their output
    """

    def __init__(self, homedir=None, use_default_keyring=False):
        self.homedir = homedir
        self.use_default_keyring = use_default_keyring

    def _base_cmd(self):
        cmd = ["/usr/bin/gpg"]
        if self.homedir is not None:
            cmd.append("--homedir")
            cmd.append(self.homedir)
        cmd.extend(("-q", "--no-options", "--no-auto-check-trustdb",
            "--trust-model", "always", "--with-colons", "--fixed-list-mode",
            "--with-fingerprint", "--no-permission-warning", "--no-tty", "--batch", "--display-charset", "utf-8"))
        if not self.use_default_keyring:
            cmd.append("--no-default-keyring")
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
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout, stderr = proc.communicate(input=input)
        result = proc.wait()
        return stdout, stderr, result

    def run_checked(self, cmd, input=None):
        """
        Run gpg with the given command, waiting for its completion, returning stdout.

        In case gpg returns nonzero, raises a RuntimeError that includes stderr.
        """
        stdout, stderr, result = self.run_cmd(cmd, input)
        if result != 0:
            raise RuntimeError("{} exited with status {}: {}".format(
                " ".join(shlex_quote(x) for x in cmd),
                result,
                stderr.strip()
            ))
        return stdout

    def pipe_cmd(self, cmd):
        """
        Run gpg with the given command, returning a couple
        (proc, lines)
        where proc is the subprocess.Popen object, and lines is a
        backend.utils.StreamStdoutKeepStderr object connected to proc.
        """
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
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
            line = line.decode('utf-8')
        except:
            try:
                line = line.decode('iso8859-1')
            except:
                line = line.decode('utf-8', errors='replace')
        if not line.startswith("fpr"): continue
        yield line.split(":")[9]
    result = proc.wait()
    if result != 0:
        raise RuntimeError("gpg exited with status %d: %s" % (result, lines.stderr.getvalue().strip()))


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


class KeyData(object):
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
        sub = None
        cur_key = None
        cur_uid = None
        for lineno, line in enumerate(lines, start=1):
            if line.startswith("pub:"):
                # Keep track of this pub record, to correlate with the following
                # fpr record
                pub = line.split(":")
                sub = None
                cur_key = None
                cur_uid = None
            elif line.startswith("fpr:"):
                # Correlate fpr with the previous pub record, and start gathering
                # information for a new key
                if pub is None:
                    if sub is not None:
                        # Skip fingerprints for subkeys
                        continue
                    else:
                        raise Exception("gpg:{}: found fpr line with no previous pub line".format(lineno))
                fpr = line.split(":")[9]
                cur_key = keys.get(fpr, None)
                if cur_key is None:
                    keys[fpr] = cur_key = cls(fpr, pub)
                pub = None
                cur_uid = None
            elif line.startswith("uid:"):
                if cur_key is None:
                    raise Exception("gpg:{}: found uid line with no previous pub+fpr lines".format(lineno))
                cur_uid = cur_key.get_uid(line.split(":"))
            elif line.startswith("sig:"):
                if cur_uid is None:
                    raise Exception("gpg:{}: found sig line with no previous uid line".format(lineno))
                cur_uid.add_sig(line.split(":"))
            elif line.startswith("sub:"):
                if cur_key is None:
                    raise Exception("gpg:{}: found sub line with no previous pub+fpr lines".format(lineno))
                sub = line.split(":")
                cur_key.add_sub(sub)

        return keys


class Uid(object):
    """
    Collects data about a key uid, parsed from gpg --with-colons --fixed-list-mode
    """
    re_uid = re.compile(r"^(?P<name>.+?)\s*(?:\((?P<comment>.+)\))?\s*(?:<(?P<email>.+)>)?$")

    def __init__(self, key, uid):
        self.key = key
        self.uid = uid
        self.name = uid[9]
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
            self.errors.add("key_size_" + str(keysize))
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
