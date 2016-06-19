# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.conf import settings
from django.utils.timezone import utc, now
import subprocess
import datetime
import os
import re
import git


class LogEntry(object):
    re_update_changelog = re.compile(r"^\s*Update changelog\s*$", re.I)
    re_import_changes = re.compile(r"Import changes sent to keyring.debian.org HKP interface", re.I)
    re_field_split = re.compile(r":\s*")
    re_summaries = [
        {
            "re": re.compile(r"Add new (?P<role>[A-Z]+) key 0x(?P<key>[0-9A-F]+) \((?P<subj>[^)]+)\)\s+\(RT #(?P<rt>\d+)\)"),
            "proc": lambda x: { "Action": "add", "Role": x.group("role"), "New-key": x.group("key"), "Subject": x.group("subj"), "RT-Ticket": x.group("rt") },
        },
        {
            "re": re.compile(r"Replace 0x(?P<old>[0-9A-F]+) with 0x(?P<new>[0-9A-F]+) \((?P<subj>[^)]+)\) \(RT #(?P<rt>\d+)\)"),
            "proc": lambda x: { "Action": "replace", "Old-key": x.group("old"), "New-key": x.group("new"), "Subject": x.group("subj"), "RT-Ticket": x.group("rt") },
        },
        {
            "re": re.compile(r"Move 0x(?P<key>[0-9A-F]+) to [Ee]meritus \(?P<subj>[^)]+\)\s+\(RT #(?P<rt>\d+)"),
            "proc": lambda x: { "Action": "FIXME-move", "Key": x.group("key"), "Target": "emeritus", "Subject": x.group("subj"), "RT-Ticket": x.group("rt") },
        },
        {
            "re": re.compile(r"Move 0x(?P<key>[0-9A-F]+)\s+\(?P<subj>[^)]+\) to [Rr]emoved keyring\s+\(RT #(?P<rt>\d+)"),
            "proc": lambda x: { "Action": "FIXME-move", "Key": x.group("key"), "Target": "removed", "Subject": x.group("subj"), "RT-Ticket": x.group("rt") },
        },
    ]

    def __init__(self, gk, shasum, dt, keyid, validated):
        # Master GitKeyring object
        self.gk = gk
        # Commit shasum
        self.shasum = shasum
        # Datetime
        self.dt = dt
        # GPG Key ID
        self.keyid = keyid
        # Validated (%G? in git --pretty format)
        self.validated = validated
        # "G" for a Good signature, "B" for a Bad signature, "U" for a good, untrusted signature and "N" for no signature
        # "U" for good but untrusted is ok, because we are verifying against a
        #     curated keyring
        self.is_valid = self.validated in "GU"
        # gitpython Commit
        self.commit = gk.repo.commit(self.shasum)
        # Parsed dict, or None
        parsed = self._parse()
        if parsed:
            self.parsed = { k.lower(): v for k, v in parsed.items() }
        else:
            self.parsed = None

    def _parse(self):
        """
        Return the commit message for this log entry, parsed into a dict with
        all the details of the operation.
        """
        import email
        body = self.commit.message
        if "\n\n" not in body: return None
        subject, body = body.split("\n\n", 1)
        if self.re_update_changelog.match(subject): return None
        if self.re_import_changes.match(subject): return None
        if body.startswith("Action:"):
            operation = email.message_from_string(body.encode("utf-8"))
            return dict(operation.items())
        else:
            for match in self.re_summaries:
                mo = match["re"].match(subject)
                if mo: return match["proc"](mo)
            #print("UNKNOWN", repr(subject))
            return None


class GitKeyring(object):
    """
    Access the git repository of keyring-maint
    """
    # http://mikegerwitz.com/papers/git-horror-story

    def __init__(self):
        self.KEYRING_MAINT_KEYRING = os.path.abspath(getattr(settings, "KEYRING_MAINT_KEYRING", "data/keyring-maint.gpg"))
        self.KEYRING_MAINT_GIT_REPO = os.path.abspath(getattr(settings, "KEYRING_MAINT_GIT_REPO", "data/keyring-maint.git"))
        self.repo = git.Repo(self.KEYRING_MAINT_GIT_REPO)
        self.git = git.cmd.Git(self.KEYRING_MAINT_GIT_REPO)
        self.git.update_environment(GNUPGHOME=self.KEYRING_MAINT_KEYRING)
        self.verified_shasums = set()

    def read_log(self, *args):
        """
        Run git log on the keyring dir and return the valid shasums that it
        found, as LogEntry objects.

        Extra git log options passed as *args will be appended to the command
        line.
        """
        for line in self.git.log("--pretty=format:%H:%ct:%GK:%G?", "origin/master", *args).split("\n"):
            shasum, ts, keyid, validated = line.split(":")
            entry = LogEntry(self, shasum, datetime.datetime.fromtimestamp(int(ts), utc), keyid, validated)

            # If the commit is not signed, check if we have seen a signed
            # descendant
            if not entry.is_valid:
                entry.is_valid = entry.shasum in self.verified_shasums

            # If the commit can be trusted, take note of its shasum and those
            # of its ancestors
            if entry.is_valid:
                self.verified_shasums.add(entry.shasum)
                for parent in entry.commit.parents:
                    self.verified_shasums.add(parent.hexsha)

                yield entry
