#!/usr/bin/python
# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import email
import re
import sys
import os
import subprocess
import argparse
import pipes
import logging

log = logging.getLogger(__name__)

def role_is_dd(role):
    """
    Check if a role is a DD role
    """
    return role.startswith("DD") or role.startswith("DN")


class DakOutput(object):
    """
    Output parsed record for dak
    """
    def __init__(self, pathname):
        self.out = open(pathname, 'w')
        self.out.write("Archive: ftp.debian.org\n")
        self.out.write("Uploader: Jonathan McDowell <noodles@earth.li>\n")
        self.out.write("Cc: keyring-maint@debian.org\n")

    def close(self):
        self.out.close()

    def write(self, state, operation):
        if operation['action'] == 'remove':
            if 'rt-ticket' in operation:
                if not role_is_dd(operation['role']):
                    self.out.write("\nAction: dm-remove\n" +
                            "Fingerprint: " + operation['key'] + "\n" +
                            "Reason: RT #" + operation['rt-ticket'] +
                            ", keyring commit " + state['commit'] + "\n")
        elif operation['action'] == 'replace':
            if not role_is_dd(operation['role']):
                self.out.write("\nAction: dm-migrate\n" +
                        "From: " + operation['old-key'] + "\n" +
                        "To: " + operation['new-key'] + "\n" +
                        "Reason: RT #" + operation['rt-ticket'] +
                        ", keyring commit " + state['commit'] + "\n")


class RTOutput(object):
    """
    Output parsed records for RT
    """
    def __init__(self, pathname):
        self.out = open(pathname, 'w')

    def close(self):
        self.out.close()

    def write(self, state, operation):
        if operation['action'] == 'add':
            if 'rt-ticket' in operation:
                self.out.write("# Commit " + state['commit'] + "\n")
                if role_is_dd(operation['role']):
                    self.out.write("rt edit ticket/" + operation['rt-ticket'] +
                            " set queue=DSA\n")
                elif operation['role'] == 'DM':
                    self.out.write("rt correspond -s resolved -m " +
                        "'This key has now been added to the active DM keyring.' " +
                        operation['rt-ticket'] + "\n")
                else:
                    self.out.write("rt correspond -s resolved -m " +
                        "'This key has now been added to the " +
                        operation['role'] + " keyring.' " +
                        operation['rt-ticket'] + "\n")
        elif operation['action'] == 'remove':
            if 'rt-ticket' in operation:
                self.out.write("# Commit " + state['commit'] + "\n")
                if role_is_dd(operation['role']):
                    self.out.write("rt edit ticket/" + operation['rt-ticket'] +
                            " set queue=DSA\n")
                else:
                    self.out.write("rt edit ticket/" + operation['rt-ticket'] +
                            " set queue=Keyring\n" +
                            "rt correspond -s resolved -m "+
                            "'This key has now been removed from the active DM keyring.' " +
                            operation['rt-ticket'] + "\n")
        elif operation['action'] == 'replace':
            self.out.write("# Commit " + state['commit'] + "\n")
            if role_is_dd(operation['role']):
                self.out.write("rt edit ticket/" + operation['rt-ticket'] +
                        " set queue=Keyring\n" +
                        "rt correspond -s resolved -m " +
                        "'Your key has been replaced in the active keyring and LDAP updated with the new fingerprint.' " +
                        operation['rt-ticket'] + "\n")
            else:
                self.out.write("rt edit ticket/" + operation['rt-ticket'] +
                        " set queue=Keyring\n" +
                        "rt correspond -s resolved -m "+
                        "'Your key has been replaced in the active DM keyring.' " +
                        operation['rt-ticket'] + "\n")


class LDAPOutput(object):
    """
    Output parsed records for LDAP
    """
    def __init__(self, pathname):
        self.out = open(pathname, 'w')

    def close(self):
        self.out.close()

    def write(self, state, operation):
        if operation['action'] == 'replace':
            if role_is_dd(operation['role']):
                self.out.write(operation['username'] + " " + operation['old-key'] + " ")
                self.out.write(operation['new-key'] + "\n")


class Parser(object):
    def __init__(self, repo=".", gnupghome=None):
        self.seenrt = {}
        self.repo = repo
        self.gnupghome = gnupghome

    def run_git(self, *args):
        """
        Run git with self.repo as current directory, and if set, with GNUPGHOME
        set to self.gnupghome.

        Returns stdout (raw, as a byte string) if everything was fine,
        otherwise it throws an exception which includes the contents of stderr.
        """
        cmdline = ["git"]
        cmdline.extend(args)
        args = {
            "cwd": self.repo,
            "stdin": subprocess.PIPE,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "universal_newlines": True,
        }
        if self.gnupghome:
            env = dict(os.environ)
            env["GNUPGHOME"] = self.gnupghome
            args["env"] = env
        proc = subprocess.Popen(cmdline, **args)
        stdout, stderr = proc.communicate()
        res = proc.wait()
        if res != 0:
            raise RuntimeError("{} returned error code {}. Stderr: {}", " ".join(pipes.quote(x) for x in cmdline), res, stderr)
        return stdout.decode("utf-8")

    def do_operation(self, state):
        operation = email.message_from_string(state['message'].encode("utf-8"))

        if not 'action' in operation:
            #print("NOTE : " + state['commit'] + " (" + state['summary'] + ") has no action")
            return None

        if 'rt-ticket' in operation and operation['rt-ticket'] in self.seenrt:
            print("ERROR: RT " + operation['rt-ticket'] + " used in " +
                    self.seenrt[operation['rt-ticket']] + " and " +
                    state['commit'])
        else:
            self.seenrt[operation['rt-ticket']] = state['commit']

        if operation['action'] == 'add':
            if 'rt-ticket' in operation:
                if operation['role'] == 'DM':
                    bts = operation['BTS'].strip()
                    bts = re.sub(r'http://bugs.debian.org/(\d+)',
                        r'\1-done@bugs.debian.org', bts)
                    #print("NOTE : Mail " + bts + " (new DM).")
                return operation
            else:
                #print("TODO : Add with no RT ticket")
                return (None, "")
        elif operation['action'] == 'remove':
            if 'rt-ticket' in operation:
                return operation
            else:
                if 'username' in operation:
                    username = operation['username']
                elif 'key' in operation:
                    username = operation['key']
                elif 'old-key' in operation:
                    username = operation['old-key']
                elif 'subject' in operation:
                    username = operation['subject']
                #print("TODO : Removal for " + username + " without RT ticket.")
                return None
        elif operation['action'] == 'replace':
            if role_is_dd(operation['role']):
                if not 'username' in operation:
                    operation['Username'] = 'FIXME'
                return operation
            else:
                return operation
        else:
            print("Error: Unknown action " + operation['action'])
            return None

    def parse_fd(self, fd, extra_commit_data=None):
        """
        Parse a git log from a file descriptior, and generate a sequence of
        (state, operation) dictionaries.
        """
        state = {}

        def enrich_state(state):
            """
            Add fields from extra_commit_data to state, if extra_commit_data
            contains a record with the same shasum as state.
            """
            if not extra_commit_data: return
            extra = extra_commit_data.get(state["commit"], None)
            if not extra: return
            state.update(**extra)

        for line in fd:
            line = line.rstrip()

            # Catch the start of a commit
            m = re.match("commit (.*)$", line)
            if m:
                if 'message' in state:
                    enrich_state(state)
                    operation = self.do_operation(state)
                    if operation:
                        yield state, operation
                elif 'commit' in state:
                    if re.match("Import changes sent to keyring", state['summary']):
                        pass
                    elif re.match("Update changelog", state['summary']):
                        pass
                    else:
                        #print("NOTE : " + state['commit'] + " (" + state['summary'] + ") is not an action.")
                        pass
                state = {}
                state['commit'] = m.group(1)

            if not re.match("    ", line):
                continue

            line = line[4:]
            if not 'inaction' in state:
                if re.match("[a-zA-Z]*: ", line):
                    state['inaction'] = True
                    state['message'] = line + "\n"
                elif not 'summary' in state:
                    state['summary'] = line
            else:
                state['message'] += line + "\n"

        # Process the last commit, if applicable
        if 'message' in state:
            enrich_state(state)
            operation = self.do_operation(state)
            if operation:
                yield state, operation

    def parse_git(self, commit_range):
        """
        Run git to generate the log for commit_range in the given repository,
        then parse it. It generates the same as parse_fd, but 'state' records
        will also contain signature information.
        """
        # Get the signature information in this commit range
        out = self.run_git("log", "--pretty=format:%H %at %G? %GK %ae", commit_range, "--")
        records = []
        last_good_sig = None
        for line in out.splitlines():
            # %G?: show "G" for a Good signature, "B" for a Bad signature, "U"
            # for a good, untrusted signature and "N" for no signature
            shasum, ts, sig_status, key_id, author_email = line.strip().split(" ")
            if sig_status == "G" and last_good_sig is None:
                # Record the index of the last record found with a good
                # signature
                last_good_sig = len(records)
            records.append({
                "commit": shasum,
                "sig_status": sig_status,
                "key_id": key_id,
                "author_email": author_email,
                "ts": int(ts),
            })

        # Amend records setting has_signed_successor to all records before
        # last_good_sig
        if last_good_sig is not None:
            for i in range(last_good_sig + 1, len(records)):
                records[i]["has_signed_successor"] = True

        # Index records by shasum
        records = { rec["commit"]: rec for rec in records }

        # Process the actual log
        out = self.run_git("log", commit_range)
        for x in self.parse_fd(out.splitlines(), extra_commit_data=records):
            yield x


def keyring_maint_main():
    parser = argparse.ArgumentParser(description='Generate keyring-maint output from keyring logs.')
    parser.add_argument('commit_range', nargs='?', help='a git commit range. If missing, git log output is read from stdin')
    parser.add_argument('--ignore-unsigned', action="store_true", help='if set, ignore commits without a good signature and without a descendent with a good signature')
    args = parser.parse_args()

    parser = Parser()
    if args.commit_range:
        records = parser.parse_git(args.commit_range)
    else:
        records = parser.parse_fd(sys.stdin)


    dak = DakOutput("dak-update")
    rt = RTOutput("rt-update")
    ldap = LDAPOutput("ldap-update")

    opcount = 0
    for state, operation in records:
        if args.ignore_unsigned and state.get("sig_status", None) != "G" and not state.get("has_signed_successor", False):
            print("Skipping unsigned commit", state["commit"])
            continue
        dak.write(state, operation)
        rt.write(state, operation)
        ldap.write(state, operation)
        opcount += 1

    ldap.close()
    rt.close()
    dak.close()

    print("Processed " + str(opcount) + " operations.")


if __name__ == '__main__':
    keyring_maint_main()
