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

    def __init__(self):
        self.KEYRING_MAINT_KEYRING = getattr(settings, "KEYRING_MAINT_KEYRING", "data/keyring-maint.gpg")
        self.KEYRING_MAINT_GIT_REPO = getattr(settings, "KEYRING_MAINT_GIT_REPO", "data/keyring-maint.git")
        self.repo = git.Repo(self.KEYRING_MAINT_GIT_REPO)
        self.git = git.cmd.Git(self.KEYRING_MAINT_GIT_REPO)
        self.git.update_environment(GNUPGHOME=self.KEYRING_MAINT_KEYRING)

    def get_valid_shasums(self, *args):
        """
        Run git log on the keyring dir and return the valid shasums that it found.

        Extra git log options passed as *args will be appended to the command line
        """
        for line in self.git.log("--pretty=format:%H:%ct:%G?", "origin/master", *args).split("\n"):
            shasum, ts, validated = line.split(":")
            # "G" for a Good signature, "B" for a Bad signature, "U" for a good, untrusted signature and "N" for no signature
            if validated in "GU":
                yield shasum, datetime.datetime.fromtimestamp(int(ts), utc)

    def get_commit_message(self, shasum):
        """
        Return the commit message for the given shasum
        """
        body = self.git.show("--pretty=format:%B", shasum)
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
                    yield name, "\n".join(cur)
                    name = None
                    cur = []
                name, content = self.re_field_split.split(line, 1)
                cur.append(content)
            else:
                cur.append(line.lstrip())

        if name:
            yield name, "\n".join(cur)

    def get_changelog_parser(self):
        """
        Create and return an instance of the keyring-maint changelog parser
        """
        from . import gitchangelog
        return gitchangelog.Parser(repo=self.KEYRING_MAINT_GIT_REPO, gnupghome=self.KEYRING_MAINT_KEYRING)
