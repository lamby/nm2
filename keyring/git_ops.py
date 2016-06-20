# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from backend import const
import backend.models as bmodels
import backend.ops as bops
import process.models as pmodels
import process.ops as pops
import os
import requests
import re

class ParseError(Exception):
    def __init__(self, log_entry, *args, **kw):
        super(ParseError, self).__init__(*args, **kw)
        self.log_entry = log_entry


class OperationError(Exception):
    def __init__(self, log_entry, *args, **kw):
        super(OperationError, self).__init__(*args, **kw)
        self.log_entry = log_entry


class Operation(object):
    """
    Base class for operations detected from git logs
    """
    # Available actions
    actions = {}

    email_map = {
        "gwolf@gwolf.org": "gwolf",
        "noodles@earth.li": "noodles",
    }

    @classmethod
    def action(cls, _class):
        """
        Register an action class
        """
        cls.actions[_class.__name__.lower()] = _class
        return _class

    @classmethod
    def from_log_entry(cls, log_entry):
        action_name = log_entry.parsed["action"].lower()
        Action = cls.actions.get(action_name, None)
        if Action is None:
            raise ParseError(log_entry, "Action {} not supported", action_name)
        return Action.from_log_entry(log_entry)

    def __init__(self, log_entry):
        self.log_entry = log_entry
        author_email = log_entry.commit.author.email
        author_uid = self.email_map.get(author_email, None)
        if author_uid is None:
            search = { "email": author_email }
        else:
            search = { "uid": author_uid }
        try:
            self.author = bmodels.Person.objects.get(**search)
        except bmodels.Person.DoesNotExist:
            raise ParseError(log_entry, "author {} not found in nm.debian.org".format(log_entry.commit.author.email))

        self.role = log_entry.parsed.get("role", None)
        if self.role is None: raise ParseError(log_entry, "Role not found in commit message")

        self.rt = log_entry.parsed.get("rt-ticket", None)

    def _get_consistent_person(self, persons):
        """
        Given a dict mapping workds to Person objects, make sure that all the
        Person objects are the same, and return the one Person object.

        If persons is empty, return None.
        """
        # Check if we are unambiguously referring to a record that we
        # can update
        person = None
        for v in persons.values():
            if person is None:
                person = v
            elif person != v:
                msg = []
                for k, v in persons.items():
                    msg.append("{} by {}".format(k, v.lookup_key))
                raise OperationError(self.log_entry, "commit matches multiple people: {}".format(", ".join(msg)))

        return person


class RoleOperation(Operation):
    @classmethod
    def from_log_entry(cls, log_entry):
        role = log_entry.parsed.get("role", None)
        if role == "role": return None
        if role is None: raise ParseError(log_entry, "role not found in commit message")
        Op = cls.by_role.get(role, None)
        if Op is None:
            raise ParseError(log_entry, "unsupported role {} in commit message".format(role))
        return Op(log_entry)


@Operation.action
class Add(RoleOperation):
    by_role = {}

    def __init__(self, log_entry):
        super(Add, self).__init__(log_entry)
        for k in ("new-key", "key"):
            self.fpr = log_entry.parsed.get(k, None)
            if self.fpr is not None: break
        else:
            raise ParseError(log_entry, "commit message has no New-key or Key field")

        fn = log_entry.parsed.get("subject", None)
        if fn is None:
            raise ParseError(log_entry, "commit message has no Subject field")
        self.cn, self.mn, self.sn = self._split_subject(fn)

        self.email = None
        self.uid = None

    def _split_subject(self, subject):
        """
        Arbitrary split a full name into cn, mn, sn

        This is better than nothing, but not a lot better than that.
        """
        # See http://www.kalzumeus.com/2010/06/17/falsehoods-programmers-believe-about-names/
        fn = subject.decode('utf8').split()
        if len(fn) == 1:
            return fn[0], "", ""
        elif len(fn) == 2:
            return fn[0], "", fn[1]
        elif len(fn) == 3:
            return fn
        else:
            middle = len(fn) // 2
            return " ".join(fn[:middle]), "", " ".join(fn[middle:])

    def _get_person(self):
        """
        Return the Person affected by this entry, or None if none exists in the
        database yet
        """
        # Check for existing records in the database
        persons = {}

        if self.fpr:
            try:
                persons["fpr"] = bmodels.Person.objects.get(fprs__fpr=self.fpr)
            except bmodels.Person.DoesNotExist:
                pass

        if self.email:
            try:
                persons["email"] = bmodels.Person.objects.get(email=self.email)
            except bmodels.Person.DoesNotExist:
                pass

        if self.uid:
            try:
                persons["uid"] = bmodels.Person.objects.get(uid=self.uid)
            except bmodels.Person.DoesNotExist:
                pass

        # Check if we are unambiguously referring to a record that we
        # can update
        return self._get_consistent_person(persons)


class AddDM(Add):
    def __init__(self, log_entry):
        """
        Dig all information from a commit body that we can use to create a new
        DM
        """
        super(AddDM, self).__init__(log_entry)

        details = log_entry.parsed.get("details", None)
        if details is not None:
            try:
                process_id = int(os.path.basename(details))
            except:
                raise ParseError(log_entry, "cannot extract process ID from {}".format(details))

            try:
                process = pmodels.Process.objects.get(pk=process_id)
            except pmodels.Process.DoesNotExist:
                raise ParseError(log_entry, "process {} not found in the site".format(details))

            self.email = process.person.email
        else:
            # To get the email, we need to go and scan the agreement post from the
            # list archives
            agreement_url = log_entry.parsed.get("agreement", None)
            if agreement_url is not None:
                r = self._fetch_url(agreement_url.strip())
                if r.status_code == 200:
                    mo = re.search(r'<link rev="made" href="mailto:([^"]+)">', r.text)
                    if mo:
                        self.email = mo.group(1)
            if self.email is None:
                raise ParseError(log_entry, "agreement not found in commit, or email not found in agreement url")

    def _fetch_url(self, url):
        bundle="/etc/ssl/ca-debian/ca-certificates.crt"
        if os.path.exists(bundle):
            return requests.get(url, verify=bundle)
        else:
            return requests.get(url)

    def ops(self):
        # Check for existing records in the database
        person = self._get_person()

        # If it is all new, create and we are done
        if person is None:
            if self.rt:
                audit_notes = "Created DM entry, RT #{}".format(self.rt)
            else:
                audit_notes = "Created DM entry, RT unknown"
            yield bops.CreateUser(
                # Dummy username used to avoid unique entry conflicts
                username="{}@example.org".format(self.fpr),
                cn=self.cn,
                mn=self.mn,
                sn=self.sn,
                email=self.email,
                status=const.STATUS_DM,
                status_changed=self.log_entry.dt,
                audit_author=self.author,
                audit_notes=audit_notes,

                fpr=self.fpr,
            )
            return


        if person.status in (const.STATUS_DM, const.STATUS_DM_GA):
            # Already a DM, nothing to do
            #log.info("%s: %s is already a DM: skipping duplicate entry", self.logtag, self.person_link(person))
            return

        if person.status in (
                const.STATUS_DD_U, const.STATUS_DD_NU, const.STATUS_EMERITUS_DD, const.STATUS_REMOVED_DD,
                const.STATUS_EMERITUS_DM, const.STATUS_REMOVED_DM):
            raise OperationError(self.log_entry, "commit is for a new DM, but it corresponds to {} who has status {}".format(person.lookup_key, person.status))

        if person.status == const.STATUS_DC_GA:
            status = const.STATUS_DM_GA
        else:
            status = const.STATUS_DM

        if self.rt:
            audit_notes = "Set status to {}, RT #{}".format(const.ALL_STATUS_DESCS[status], self.rt)
        else:
            audit_notes = "Set status to {}, RT unknown".format(const.ALL_STATUS_DESCS[status])

        yield bops.ChangeStatus(
            person=person,
            status=status,
            status_changed=self.log_entry.dt,
            audit_author=self.author,
            audit_notes=audit_notes)

        #log.info("%s: %s: %s", self.logtag, self.person_link(person), audit_notes)

    def __str__(self):
        return "Add DM"

Add.by_role["DM"] = AddDM


class AddDD(Add):
    def __init__(self, log_entry):
        """
        Dig all information from a commit body that we can use to create a new
        DD
        """
        super(AddDD, self).__init__(log_entry)
        self.uid = log_entry.parsed.get("username", None)

    def __str__(self):
        return "Add DD"

    def ops(self):
        # Check for existing records in the database
        person = self._get_person()

        # If it is all new, keyring has a DD that DAM does not know about:
        # yell.
        if person is None:
            raise OperationError(self.log_entry, "commit has new DD {} {} that we do not know about".format(self.uid, self.fpr))

        if person.fpr != self.fpr:
            # Keyring-maint added a different key: sync with them
            if self.rt:
                audit_notes = "Set fingerprint to {}, RT #{}".format(self.fpr, self.rt)
            else:
                audit_notes = "Set fingerprint to {}, RT unknown".format(self.fpr)
            yield bops.ChangeFingerprint(
                person=person, fpr=self.fpr,
                audit_author=self.author, audit_notes=audit_notes)
            #person.save(audit_author=self.author, audit_notes=audit_notes)
            #log.info("%s: %s: %s", self.logtag, self.person_link(person), audit_notes)
            # Do not return yet, we still need to check the status

        role_status_map = {
            "DD": const.STATUS_DD_U,
            "DN": const.STATUS_DD_NU,
        }

        if person.status == role_status_map[self.role]:
            # Status already matches
            #log.info("%s: %s is already %s: skipping duplicate entry", self.logtag, self.person_link(person), const.ALL_STATUS_DESCS[person.status])
            return

        # Look for a process to close
        applying_for = role_status_map[self.role]

        found = False
        for p in person.active_processes:
            if p.applying_for != applying_for: continue
            if self.rt:
                logtext = "Added to {} keyring, RT #{}".format(self.role, self.rt)
            else:
                logtext = "Added to {} keyring, RT unknown".format(self.role)
            if not bmodels.Log.objects.filter(process=p, changed_by=self.author, logdate=self.log_entry.dt, logtext=logtext).exists():
                yield bops.CloseOldProcess(
                    process=p,
                    logtext=logtext,
                    logdate=self.log_entry.dt,
                    audit_author=self.author,
                    audit_notes=logtext,
                )
            #log.info("%s: %s has an open process to become %s, keyring added them as %s",
            #            self.logtag, self.person_link(person), const.ALL_STATUS_DESCS[p.applying_for], self.role)
            found = True

        for p in pmodels.Process.objects.filter(person=person, applying_for=applying_for, closed__isnull=True):
            if self.rt:
                logtext = "Added to {} keyring, RT #{}".format(self.role, self.rt)
            else:
                logtext = "Added to {} keyring, RT unknown".format(self.role)
            yield pops.CloseProcess(
                process=p,
                logtext=logtext,
                logdate=self.log_entry.dt,
                audit_author=self.author,
                audit_notes=logtext,
            )
            #log.info("%s: %s has an open process to become %s, keyring added them as %s",
            #            self.logtag, self.person_link(person), const.ALL_STATUS_DESCS[p.applying_for], self.role)
            found = True

        if not found:
            # f3d1c1ee92bba3ebe05f584b7efea0cfd6e4ebe4 is an example commit
            # that triggers this
            raise OperationError(self.log_entry, "commit adds {} as {}, but we have no active process for it".format(
                person.lookup_key, self.role))

Add.by_role["DD"] = AddDD
Add.by_role["DN"] = AddDD


@Operation.action
class Remove(RoleOperation):
    by_role = {}


class RemoveDD(Remove):
    def __init__(self, log_entry):
        super(RemoveDD, self).__init__(log_entry)
        self.uid = log_entry.parsed.get("username", None)
        self.fpr = log_entry.parsed.get("key", None)
        if self.fpr is None:
            raise ParseError(log_entry, "commit without Key field")

    def ops(self):
        persons = {}

        if self.uid:
            try:
                persons["uid"] = bmodels.Person.objects.get(uid=self.uid)
            except bmodels.Person.DoesNotExist:
                pass

        try:
            persons["fpr"] = bmodels.Person.objects.get(fprs__fpr=self.fpr)
        except bmodels.Person.DoesNotExist:
            pass

        person = self._get_consistent_person(persons)
        if not person:
            raise OperationError(self.log_entry, "commit references a person that is not known to the site")

        if person.status in (const.STATUS_DD_U, const.STATUS_DD_NU):
            if self.rt:
                audit_notes = "Moved to emeritus keyring, RT #{}".format(self.rt)
            else:
                audit_notes = "Moved to emeritus keyring, RT unknown"

            yield bops.ChangeStatus(
                person=person,
                status=const.STATUS_EMERITUS_DD,
                status_changed=self.log_entry.dt,
                audit_author=self.author,
                audit_notes=audit_notes)
            #log.info("%s: %s: %s", self.logtag, self.person_link(person), audit_notes)
            return

        if person.status == const.STATUS_EMERITUS_DD:
            # Already moved to DD
            #log.info("%s: %s is already emeritus: skipping key removal", self.logtag, self.person_link(person))
            return

    def __str__(self):
        return "Remove DD"

Remove.by_role["DD"] = RemoveDD


@Operation.action
class Replace(Operation):
    def __init__(self, log_entry):
        super(Replace, self).__init__(log_entry)
        self.old_key = log_entry.parsed.get("old-key", None)
        if self.old_key is None:
            raise ParseError(log_entry, "commit without Old-Key field")

        self.new_key = log_entry.parsed.get("new-key", None)
        if self.new_key is None:
            raise ParseError(log_entry, "commit without New-Key field")

        self.uid = log_entry.parsed.get("username", None)

    def __str__(self):
        return "Replace"

    @classmethod
    def from_log_entry(cls, log_entry):
        return cls(log_entry)

    def ops(self):
        uid_person = None
        if self.uid is not None:
            try:
                uid_person = bmodels.Person.objects.get(uid=self.uid)
            except bmodels.Person.DoesNotExist:
                pass

        try:
            old_person = bmodels.Person.objects.get(fprs__fpr=self.old_key, fprs__is_active=True)
        except bmodels.Person.DoesNotExist:
            old_person = None

        try:
            new_person = bmodels.Person.objects.get(fprs__fpr=self.new_key, fprs__is_active=True)
        except bmodels.Person.DoesNotExist:
            new_person = None

        if old_person is None and new_person is None and uid_person is None:
            raise OperationError(self.log_entry, "cannot find existing person for key replace")

        if uid_person is not None:
            if old_person is not None and uid_person != old_person:
                raise OperationError(self.log_entry, "commit matches person {} by uid {} and person {} by old fingerprint {}".format(
                    uid_person.lookup_key, uid_person.uid, old_person.lookup_key, old_person.fpr))
            if new_person is not None and uid_person != new_person:
                raise OperationError(self.log_entry, "commit matches person {} by uid {} and person {} by new fingerprint {}".format(
                    uid_person.lookup_key, uid_person.uid, new_person.lookup_key, new_person.fpr))

        # Now, if uid_person is set, it can either:
        #  - match old_person
        #  - match new_person
        #  - identify the old person when old_person is None and new_person is None

        if old_person is not None and new_person is not None:
            if old_person != new_person:
                raise OperationError(self.log_entry, "commit reports a key change from {} to {}, but the keys belong to two different people ({} and {})".format(
                    self.old_key, self.new_key, old_person.lookup_key, new_person.lookup_key))
            else:
                raise OperationError(self.log_entry, "commit reports a key change from {} to {}, but both fingerprints match person {}".format(
                    self.old_key, self.new_key, new_person.lookup_key))

        # Now either old_person is set or new_person is set, or both are unset
        # and uid_person is set

        if new_person is not None:
            # Already replaced
            #log.info("%s: %s already has the new key: skipping key replace", self.logtag, self.person_link(new_person))
            return

        # Perform replace
        person = old_person if old_person is not None else uid_person
        if self.rt:
            audit_notes = "GPG key changed, RT #{}".format(self.rt)
        else:
            audit_notes = "GPG key changed, RT unknown"
        #person.fprs.create(fpr=self.new_key, is_active=True, audit_author=self.author, audit_notes=audit_notes)
        yield bops.ChangeFingerprint(
            person=person, fpr=self.new_key,
            audit_author=self.author, audit_notes=audit_notes)
        #log.info("%s: %s: %s", self.logtag, self.person_link(person), audit_notes)
