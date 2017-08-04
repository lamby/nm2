"""
Core models of the New Member site
"""
from django.utils.translation import ugettext_lazy as _
from django.utils.timezone import utc, now
from django.db import models
from django.conf import settings
from django.utils.timezone import now
from django.core.urlresolvers import reverse
from django.contrib.auth.models import BaseUserManager, PermissionsMixin
from django.forms.models import model_to_dict
from . import const
from .fields import *
from .utils import cached_property
from backend.notifications import maybe_notify_applicant_on_progress
import datetime
import urllib.request, urllib.parse, urllib.error
import os.path
import re
import json
from django.db.models.signals import post_save


PROCESS_MAILBOX_DIR = getattr(settings, "PROCESS_MAILBOX_DIR_OLD", "/srv/nm.debian.org/mbox/applicants/")
DM_IMPORT_DATE = getattr(settings, "DM_IMPORT_DATE", None)


class Permissions(set):
    """
    Set of strings, each string represent a permission
    """
    pass


class VisitorPermissions(Permissions):
    """
    Permissions of a visitor regardless of context
    """
    def __init__(self, visitor):
        self.visitor = visitor


class PersonVisitorPermissions(VisitorPermissions):
    """
    Store NM-specific permissions
    """
    fddam_states = frozenset((const.PROGRESS_AM_OK, const.PROGRESS_FD_HOLD,
        const.PROGRESS_FD_OK, const.PROGRESS_DAM_HOLD, const.PROGRESS_DAM_OK))
    pre_dd_statuses = frozenset((const.STATUS_DC, const.STATUS_DC_GA,
                                    const.STATUS_DM, const.STATUS_DM_GA,
                                    const.STATUS_EMERITUS_DD,
                                    const.STATUS_REMOVED_DD))
    dm_or_dd = frozenset((const.STATUS_DM, const.STATUS_DM_GA, const.STATUS_DD_U, const.STATUS_DD_NU))
    dd = frozenset((const.STATUS_DD_U, const.STATUS_DD_NU))

    def __init__(self, person, visitor):
        super(PersonVisitorPermissions, self).__init__(visitor)
        # Person being visited
        self.person = person.person
        # Processes of self.person
        #self.processes = list(self.person.processes.all())

        # If the person is already in LDAP, then nobody can edit their LDAP
        # info, since this database then becomes a read-only mirror of LDAP
        self.person_has_ldap_record = self.person.status not in (const.STATUS_DC, const.STATUS_DM)

        # Possible new statuses that the person can have
        self.person_possible_new_statuses = self.person.possible_new_statuses

        # True if there are active processes currently frozen for review
        self.person_has_frozen_processes = False
        old_frozen_progesses = frozenset((
            const.PROGRESS_AM_OK,
            const.PROGRESS_FD_HOLD,
            const.PROGRESS_FD_OK,
            const.PROGRESS_DAM_HOLD,
            const.PROGRESS_DAM_OK,
            const.PROGRESS_DONE,
            const.PROGRESS_CANCELLED,
        ))
        import process.models as pmodels
        if pmodels.Process.objects.filter(person=self.person, frozen_by__isnull=False, closed__isnull=True).exists():
            self.person_has_frozen_processes = True
        elif Process.objects.filter(person=self.person, is_active=True, progress__in=old_frozen_progesses).exists():
            self.person_has_frozen_processes = True

        if self.visitor is None:
            pass
        elif self.visitor.is_admin:
            self._compute_admin_perms()
        elif self.visitor == self.person:
            self._compute_own_perms()
        elif self.visitor.is_am:
            self._compute_active_am_perms()
        elif self.visitor.is_dd:
            self._compute_dd_perms()

    def _compute_admin_perms(self):
        self.update(("edit_email", "edit_bio", "update_keycheck", "view_person_audit_log"))
        if self.person_possible_new_statuses: self.add("request_new_status")
        if not self.person_has_ldap_record: self.add("edit_ldap")
        self.add("fd_comments")

    def _compute_own_perms(self):
        self.update(("edit_email", "update_keycheck"))
        if not self.person_has_frozen_processes:
            if not self.person_has_ldap_record and not self.person.pending:
                self.add("edit_ldap")
            self.add("edit_bio")
        if self.person.pending: return
        self.add("view_person_audit_log")
        if self.person_possible_new_statuses: self.add("request_new_status")

    def _compute_active_am_perms(self):
        self.update(("update_keycheck", "view_person_audit_log"))
        if not self.person_has_frozen_processes:
            self.add("edit_bio")
            if not self.person_has_ldap_record: self.add("edit_ldap")

    def _compute_dd_perms(self):
        self.update(("update_keycheck", "view_person_audit_log"))

    # TODO: advocate view audit log


class ProcessVisitorPermissions(PersonVisitorPermissions):
    """
    Permissions for visiting old-style Processes
    """
    def __init__(self, process, visitor):
        super(ProcessVisitorPermissions, self).__init__(process.person, visitor)
        self.process = process

        if self.visitor is None:
            pass
        elif self.visitor.is_admin:
            self.add("view_mbox")
        elif self.visitor == self.person:
            self.add("view_mbox")
        elif self.visitor.is_am:
            self.add("view_mbox")
        elif self.process.advocates.filter(pk=self.visitor.pk).exists():
            self.add("view_mbox")


class PersonManager(BaseUserManager):
    def create_user(self, email, **other_fields):
        if not email:
            raise ValueError('Users must have an email address')
        audit_author = other_fields.pop("audit_author", None)
        audit_notes = other_fields.pop("audit_notes", None)
        audit_skip = other_fields.pop("audit_skip", False)
        user = self.model(
            email=self.normalize_email(email),
            **other_fields
        )
        user.save(using=self._db, audit_author=audit_author, audit_notes=audit_notes, audit_skip=audit_skip)
        return user

    def create_superuser(self, email, **other_fields):
        other_fields["is_superuser"] = True
        return self.create_user(email, **other_fields)

    def get_or_none(self, *args, **kw):
        """
        Same as get(), but returns None instead of raising DoesNotExist if the
        object cannot be found
        """
        try:
            return self.get(*args, **kw)
        except self.model.DoesNotExist:
            return None

    def get_from_other_db(self, other_db_name, uid=None, email=None, fpr=None, username=None, format_person=lambda x:str(x)):
        """
        Get one Person entry matching the informations that another database
        has about a person.

        One or more of uid, email, fpr and username must be provided, and the
        function will ensure consistency in the results. That is, only one
        person will be returned, and it will raise an exception if the data
        provided match different Person entries in our database.

        other_db_name is the name of the database where the parameters come
        from, to use in generating exception messages.

        It returns None if nothing is matched.
        """
        candidates = []
        if uid is not None:
            p = self.get_or_none(uid=uid)
            if p is not None:
                candidates.append((p, "uid", uid))
        if email is not None:
            p = self.get_or_none(email=email)
            if p is not None:
                candidates.append((p, "email", email))
        if fpr is not None:
            p = self.get_or_none(fprs__fpr=fpr)
            if p is not None:
                candidates.append((p, "fingerprint", fpr))
        if username is not None:
            p = self.get_or_none(username=username)
            if p is not None:
                candidates.append((p, "SSO username", username))

        # No candidates, nothing was found
        if not candidates:
            return None

        candidate = candidates[0]

        # Check for conflicts in the database
        for person, match_type, match_value in candidates[1:]:
            if candidate[0].pk != person.pk:
                raise self.model.MultipleObjectsReturned(
                    "{} has {} {}, which corresponds to two different users in our db: {} (by {} {}) and {} (by {} {})".format(
                        other_db_name, match_type, match_value,
                        format_person(candidate[0]), candidate[1], candidate[2],
                        format_person(person), match_type, match_value))

        return candidate[0]


class Person(PermissionsMixin, models.Model):
    """
    A person (DM, DD, AM, applicant, FD member, DAM, anything)
    """
    class Meta:
        db_table = "person"

    objects = PersonManager()

    # Standard Django user fields
    username = models.CharField(max_length=255, unique=True, help_text=_("Debian SSO username"))
    last_login = models.DateTimeField(_('last login'), default=now)
    date_joined = models.DateTimeField(_('date joined'), default=now)
    is_staff = models.BooleanField(default=False)
    #is_active = True

    #  enrico> For people like Wookey, do you prefer we use only cn or only sn?
    #          "sn" is used currently, and "cn" has a dash, but rather than
    #          cargo-culting that in the new NM double check it with you
    # @sgran> cn would be more usual
    # @sgran> cn is the "whole name" and you can split it up into givenName + sn if you like
    #  phil> Except that in Debian LDAP it isn't.
    #  enrico> sgran: ok. should I use 'cn' for potential new cases then?
    # @sgran> phil: indeed
    # @sgran> but if we keep doing it the other way, we'll never be in a position to change
    # @sgran> enrico: please
    #  enrico> sgran: ack

    # Most user fields mirror Debian LDAP fields

    # First/Given name, or only name in case of only one name
    cn = models.CharField("first name", max_length=250, null=False)
    mn = models.CharField("middle name", max_length=250, null=False, blank=True, default="")
    sn = models.CharField("last name", max_length=250, null=False, blank=True, default="")
    email = models.EmailField("email address", null=False, unique=True)
    email_ldap = models.EmailField("LDAP forwarding email address", null=False, blank=True)
    bio = models.TextField("short biography", blank=True, null=False, default="",
                        help_text="Please enter here a short biographical information")
    # This is null for people who still have not picked one
    uid = CharNullField("Debian account name", max_length=32, null=True, unique=True, blank=True)

    # Membership status
    status = models.CharField("current status in the project", max_length=20, null=False,
                              choices=[(x.tag, x.ldesc) for x in const.ALL_STATUS])
    status_changed = models.DateTimeField("when the status last changed", null=False, default=now)
    fd_comment = models.TextField("Front Desk comments", null=False, blank=True, default="")
    # null=True because we currently do not have the info for old entries
    created = models.DateTimeField("Person record created", null=True, default=now)
    expires = models.DateField("Expiration date for the account", null=True, blank=True, default=None,
            help_text="This person will be deleted after this date if the status is still {} and"
                      " no Process has started".format(const.STATUS_DC))
    pending = models.CharField("Nonce used to confirm this pending record", max_length=255, unique=False, blank=True)
    last_vote = models.DateField(null=True, blank=True, help_text=_("date of the last vote done with this uid"))

    def get_full_name(self):
        return self.fullname

    def get_short_name(self):
        return self.cn

    def get_username(self):
        return self.username

    @property
    def is_anonymous(self):
        return False

    @property
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def set_password(self, raw_password):
        pass

    def check_password(self, raw_password):
        return False

    def set_unusable_password(self):
        pass

    def has_usable_password(self):
        return False

    @property
    def fingerprint(self):
        """
        Return the Fingerprint associated to this person, or None if there is
        none
        """
        # If there is more than one active fingerprint, return a random one.
        # This should not happen, and a nightly maintenance task will warn if
        # it happens.
        for f in self.fprs.filter(is_active=True):
            return f
        return None

    @property
    def fpr(self):
        """
        Return the current fingerprint for this Person
        """
        f = self.fingerprint
        if f is not None: return f.fpr
        return None

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ["cn", "email", "status"]

    @property
    def person(self):
        """
        Allow to call foo.person to get a Person record, regardless if foo is a Person or an AM
        """
        return self

    @cached_property
    def perms(self):
        """
        Get permission tags for this user
        """
        res = set()
        is_dd = self.status in (const.STATUS_DD_U, const.STATUS_DD_NU)

        if is_dd:
            res.add("dd")
            am = self.am_or_none
            if am:
                if am.is_am:
                    res.add("am")
                if am.is_admin:
                    res.add("am")
                    res.add("admin")
            else:
                res.add("am_candidate")

        return frozenset(res)

    @property
    def is_dd(self):
        return "dd" in self.perms

    @property
    def is_am(self):
        return "am" in self.perms

    @property
    def is_admin(self):
        return "admin" in self.perms

    def can_become_am(self):
        """
        Check if the person can become an AM
        """
        return "am_candidate" in self.perms

    @property
    def am_or_none(self):
        try:
            return self.am
        except AM.DoesNotExist:
            return None

    @property
    def changed_before_data_import(self):
        return DM_IMPORT_DATE is not None and self.status in (const.STATUS_DM, const.STATUS_DM_GA) and self.status_changed <= DM_IMPORT_DATE

    def permissions_of(self, visitor):
        """
        Compute which PersonVisitorPermissions the given person has over this person
        """
        return PersonVisitorPermissions(self, visitor)

    @property
    def fullname(self):
        if not self.mn:
            if not self.sn:
                return self.cn
            else:
                return "{} {}".format(self.cn, self.sn)
        else:
            if not self.sn:
                return "{} {}".format(self.cn, self.mn)
            else:
                return "{} {} {}".format(self.cn, self.mn, self.sn)

    @property
    def preferred_email(self):
        """
        Return uid@debian.org if the person is a DD, else return the email
        field.
        """
        if self.status in (const.STATUS_DD_U, const.STATUS_DD_NU):
            return "{}@debian.org".format(self.uid)
        else:
            return self.email

    def __unicode__(self):
        return "{} <{}>".format(self.fullname, self.email)

    def __repr__(self):
        return "{} <{}> [uid:{}, status:{}]".format(
                self.fullname.encode("unicode_escape"), self.email, self.uid, self.status)

    @models.permalink
    def get_absolute_url(self):
        return ("person", (), dict(key=self.lookup_key))

    def get_admin_url(self):
        return reverse("admin:backend_person_change", args=[self.pk])

    @property
    def a_link(self):
        from django.utils.safestring import mark_safe
        from django.utils.html import conditional_escape
        return mark_safe("<a href='{}'>{}</a>".format(
            conditional_escape(self.get_absolute_url()),
            conditional_escape(self.lookup_key)))

    def get_ddpo_url(self):
        return "http://qa.debian.org/developer.php?{}".format(urllib.parse.urlencode(dict(login=self.preferred_email)))

    def get_portfolio_url(self):
        parms = dict(
            email=self.preferred_email,
            name=self.fullname.encode("utf-8"),
            gpgfp="",
            username="",
            nonddemail=self.email,
            aliothusername="",
            wikihomepage="",
            forumsid=""
        )
        if self.fpr:
            parms["gpgfp"] = self.fpr
        if self.uid:
            parms["username"] = self.uid
        return "http://portfolio.debian.net/result?" + urllib.parse.urlencode(parms)

    def get_contributors_url(self):
        if self.is_dd:
            return "https://contributors.debian.org/contributor/{}@debian".format(self.uid)
        elif self.username.endswith("@users.alioth.debian.org"):
            return "https://contributors.debian.org/contributor/{}@alioth".format(self.username[:-24])
        else:
            return None

    _new_status_table = {
        const.STATUS_DC: [const.STATUS_DC_GA, const.STATUS_DM, const.STATUS_DD_U, const.STATUS_DD_NU],
        const.STATUS_DC_GA: [const.STATUS_DM_GA, const.STATUS_DD_U, const.STATUS_DD_NU],
        const.STATUS_DM: [const.STATUS_DM_GA, const.STATUS_DD_NU, const.STATUS_DD_U],
        const.STATUS_DM_GA: [const.STATUS_DD_NU, const.STATUS_DD_U],
        const.STATUS_DD_NU: [const.STATUS_DD_U],
        const.STATUS_EMERITUS_DD: [const.STATUS_DD_U, const.STATUS_DD_NU],
        const.STATUS_REMOVED_DD: [const.STATUS_DD_U, const.STATUS_DD_NU],
    }

    @property
    def possible_new_statuses(self):
        """
        Return a list of possible new statuses that can be requested for the
        person
        """
        if self.pending: return []
        statuses = list(self._new_status_table.get(self.status, []))
        # Remove statuses from active processes
        applying_for = []
        if statuses:
            for proc in Process.objects.filter(person=self, is_active=True):
                applying_for.append(proc.applying_for)

        if statuses:
            import process.models as pmodels
            for proc in pmodels.Process.objects.filter(person=self, closed__isnull=True):
                applying_for.append(proc.applying_for)

        if const.STATUS_DD_U in applying_for: applying_for.append(const.STATUS_DD_NU)
        if const.STATUS_DD_NU in applying_for: applying_for.append(const.STATUS_DD_U)

        for status in applying_for:
            try:
                statuses.remove(status)
            except ValueError:
                pass

        return statuses

    @property
    def active_processes(self):
        """
        Return a list of all the active Processes for this person, if any; else
        the empty list.
        """
        return list(Process.objects.filter(person=self, is_active=True).order_by("id"))

    def make_pending(self, days_valid=30):
        """
        Make this person a pending person.

        It does not automatically save the Person.
        """
        from django.utils.crypto import get_random_string
        self.pending = get_random_string(length=12,
                                         allowed_chars='abcdefghijklmnopqrstuvwxyz'
                                         'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        self.expires = now().date() + datetime.timedelta(days=days_valid)

    def save(self, *args, **kw):
        """
        Save, and add an entry to the Person audit log.

        Extra arguments that can be passed:

            audit_author: Person instance of the person doing the change
            audit_notes: free form text annotations for this change
            audit_skip: skip audit logging, used only for tests

        """
        # Extract our own arguments, so that they are not passed to django
        author = kw.pop("audit_author", None)
        notes = kw.pop("audit_notes", "")
        audit_skip = kw.pop("audit_skip", False)

        if audit_skip:
            changes = None
        else:
            # Get the previous version of the Person object, so that PersonAuditLog
            # can compute differences
            if self.pk:
                old_person = Person.objects.get(pk=self.pk)
            else:
                old_person = None

            changes = PersonAuditLog.diff(old_person, self)
            if changes and not author:
                raise RuntimeError("Cannot save a Person instance without providing Author information")

        # Perform the save; if we are creating a new person, this will also
        # fill in the id/pk field, so that PersonAuditLog can link to us
        super(Person, self).save(*args, **kw)

        # Finally, create the audit log entry
        if changes:
            PersonAuditLog.objects.create(person=self, author=author, notes=notes, changes=PersonAuditLog.serialize_changes(changes))

    @property
    def lookup_key(self):
        """
        Return a key that can be used to look up this person in the database
        using Person.lookup.

        Currently, this is the uid if available, else the email.
        """
        if self.uid:
            return self.uid
        elif self.email:
            return self.email
        else:
            return self.fpr

    @classmethod
    def lookup(cls, key):
        try:
            if "@" in key:
                return cls.objects.get(email=key)
            elif re.match(r"^[0-9A-Fa-f]{32,40}$", key):
                return cls.objects.get(fpr=key.upper())
            else:
                return cls.objects.get(uid=key)
        except cls.DoesNotExist:
            return None

    @classmethod
    def lookup_by_email(cls, addr):
        """
        Return the person corresponding to an email address, or None if no such
        person has been found.
        """
        try:
            return cls.objects.get(email=addr)
        except cls.DoesNotExist:
            pass
        if not addr.endswith("@debian.org"):
            return None
        try:
            return cls.objects.get(uid=addr[:-11])
        except cls.DoesNotExist:
            return None

    @classmethod
    def lookup_or_404(cls, key):
        from django.http import Http404
        res = cls.lookup(key)
        if res is not None:
            return res
        raise Http404


class FingerprintManager(BaseUserManager):
    def create(self, **fields):
        audit_author = fields.pop("audit_author", None)
        audit_notes = fields.pop("audit_notes", None)
        audit_skip = fields.pop("audit_skip", False)
        res = self.model(**fields)
        res.save(using=self._db, audit_author=audit_author, audit_notes=audit_notes, audit_skip=audit_skip)
        return res


class Fingerprint(models.Model):
    """
    A fingerprint for a person
    """
    class Meta:
        db_table = "fingerprints"

    objects = FingerprintManager()

    person = models.ForeignKey(Person, related_name="fprs")
    fpr = FingerprintField(verbose_name="OpenPGP key fingerprint", max_length=40, unique=True)
    is_active = models.BooleanField(default=False, help_text="whether this key is curently in use")
    last_upload = models.DateField(null=True, blank=True, help_text=_("date of the last ftp-master upload done with this key"))

    def __unicode__(self):
        return self.fpr

    def get_key(self):
        from keyring.models import Key
        return Key.objects.get_or_download(self.fpr)

    def save(self, *args, **kw):
        """
        Save, and add an entry to the Person audit log.

        Extra arguments that can be passed:

            audit_author: Person instance of the person doing the change
            audit_notes: free form text annotations for this change
            audit_skip: skip audit logging, used only for tests

        """
        # Extract our own arguments, so that they are not passed to django
        author = kw.pop("audit_author", None)
        notes = kw.pop("audit_notes", "")
        audit_skip = kw.pop("audit_skip", False)

        if audit_skip:
            changes = None
        else:
            # Get the previous version of the Fingerprint object, so that
            # PersonAuditLog can compute differences
            if self.pk:
                existing_fingerprint = Fingerprint.objects.get(pk=self.pk)
            else:
                existing_fingerprint = None

            changes = PersonAuditLog.diff_fingerprint(existing_fingerprint, self)
            if changes and not author:
                raise RuntimeError("Cannot save a Fingerprint instance without providing Author information")

        # Perform the save; if we are creating a new person, this will also
        # fill in the id/pk field, so that PersonAuditLog can link to us
        super(Fingerprint, self).save(*args, **kw)

        # Finally, create the audit log entry
        if changes:
            if existing_fingerprint is not None and existing_fingerprint.person.pk != self.person.pk:
                PersonAuditLog.objects.create(person=existing_fingerprint.person, author=author, notes=notes, changes=PersonAuditLog.serialize_changes(changes))
            PersonAuditLog.objects.create(person=self.person, author=author, notes=notes, changes=PersonAuditLog.serialize_changes(changes))

        # If we are saving an active fingerprint, make all others inactive
        if self.is_active:
            for fpr in Fingerprint.objects.filter(person=self.person, is_active=True).exclude(pk=self.pk):
                fpr.is_active = False
                fpr.save(audit_notes=notes, audit_author=author, audit_skip=audit_skip)


class PersonAuditLog(models.Model):
    person = models.ForeignKey(Person, related_name="audit_log")
    logdate = models.DateTimeField(null=False, auto_now_add=True)
    author = models.ForeignKey(Person, related_name="+", null=False)
    notes = models.TextField(null=False, default="")
    changes = models.TextField(null=False, default="{}")

    @classmethod
    def diff(cls, old_person, new_person):
        """
        Compute the changes between two different instances of a Person model
        """
        exclude = ["last_login", "date_joined", "groups", "user_permissions"]
        changes = {}
        if old_person is None:
            for k, nv in list(model_to_dict(new_person, exclude=exclude).items()):
                changes[k] = [None, nv]
        else:
            old = model_to_dict(old_person, exclude=exclude)
            new = model_to_dict(new_person, exclude=exclude)
            for k, nv in list(new.items()):
                ov = old.get(k, None)
                # Also ignore changes like None -> ""
                if ov != nv and (ov or nv):
                    changes[k] = [ov, nv]
        return changes

    @classmethod
    def diff_fingerprint(cls, existing_fpr, new_fpr):
        """
        Compute the changes between two different instances of a Fingerprint model
        """
        exclude = []
        changes = {}
        if existing_fpr is None:
            for k, nv in list(model_to_dict(new_fpr, exclude=exclude).items()):
                changes["fpr:{}:{}".format(new_fpr.fpr, k)] = [None, nv]
        else:
            old = model_to_dict(existing_fpr, exclude=exclude)
            new = model_to_dict(new_fpr, exclude=exclude)
            for k, nv in list(new.items()):
                ov = old.get(k, None)
                # Also ignore changes like None -> ""
                if ov != nv and (ov or nv):
                    changes["fpr:{}:{}".format(existing_fpr.fpr, k)] = [ov, nv]
        return changes

    @classmethod
    def serialize_changes(cls, changes):
        class Serializer(json.JSONEncoder):
            def default(self, o):
                if isinstance(o, datetime.datetime):
                    return o.strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(o, datetime.date):
                    return o.strftime("%Y-%m-%d")
                else:
                    return json.JSONEncoder.default(self, o)
        return json.dumps(changes, cls=Serializer)


class AM(models.Model):
    """
    Extra info for people who are or have been AMs, FD members, or DAMs
    """
    class Meta:
        db_table = "am"

    person = models.OneToOneField(Person, related_name="am")
    slots = models.IntegerField(null=False, default=1)
    is_am = models.BooleanField("Active AM", null=False, default=True)
    is_fd = models.BooleanField("FD member", null=False, default=False)
    is_dam = models.BooleanField("DAM", null=False, default=False)
    # Automatically computed as true if any applicant was approved in the last
    # 6 months
    is_am_ctte = models.BooleanField("NM CTTE member", null=False, default=False)
    # null=True because we currently do not have the info for old entries
    created = models.DateTimeField("AM record created", null=True, default=now)
    fd_comment = models.TextField("Front Desk comments", null=False, blank=True, default="")

    def __unicode__(self):
        return "%s %c%c%c" % (
            str(self.person),
            "a" if self.is_am else "-",
            "f" if self.is_fd else "-",
            "d" if self.is_dam else "-",
        )

    def __repr__(self):
        return "%s %c%c%c slots:%d" % (
            repr(self.person),
            "a" if self.is_am else "-",
            "f" if self.is_fd else "-",
            "d" if self.is_dam else "-",
            self.slots)

    @models.permalink
    def get_absolute_url(self):
        return ("person", (), dict(key=self.person.lookup_key))

    @property
    def is_admin(self):
        return self.is_fd or self.is_dam

    def applicant_stats(self):
        """
        Return 4 stats about the am (cur, max, hold, done).

        cur: number of active applicants
        max: number of slots
        hold: number of applicants on hold
        done: number of applicants successfully processed
        """
        cur = 0
        hold = 0
        done = 0
        for p in Process.objects.filter(manager=self):
            if p.progress == const.PROGRESS_DONE:
                done += 1
            elif p.progress == const.PROGRESS_AM_HOLD:
                hold += 1
            else:
                cur += 1
        return cur, self.slots, hold, done

    @classmethod
    def list_available(cls, free_only=False):
        """
        Get a list of active AMs with free slots, ordered by uid.

        Each AM is annotated with stats_active, stats_held and stats_free, with
        the number of NMs, held NMs and free slots.
        """
        from django.db import connection
        import process.models as pmodels

        ams = {}
        for am in AM.objects.all():
            am.proc_active = []
            am.proc_held = []
            ams[am] = am

        for p in Process.objects.filter(manager__isnull=False, is_active=True, progress__in=(const.PROGRESS_AM_RCVD, const.PROGRESS_AM, const.PROGRESS_AM_HOLD)).select_related("manager"):
            am = ams[p.manager]
            if p.progress == const.PROGRESS_AM_HOLD:
                am.proc_held.append(p)
            else:
                am.proc_active.append(p)

        for p in pmodels.AMAssignment.objects.filter(unassigned_by__isnull=True, process__frozen_by__isnull=True, process__approved_by__isnull=True, process__closed__isnull=True).select_related("am"):
            am = ams[p.am]
            if p.paused:
                am.proc_held.append(p)
            else:
                am.proc_active.append(p)

        res = []
        for am in list(ams.values()):
            am.stats_active = len(am.proc_active)
            am.stats_held = len(am.proc_held)
            am.stats_free = am.slots - am.stats_active

            if free_only and am.stats_free <= 0:
                continue

            res.append(am)
        res.sort(key=lambda x: (-x.stats_free, x.stats_active))
        return res

    @property
    def lookup_key(self):
        """
        Return a key that can be used to look up this manager in the database
        using AM.lookup.

        Currently, this is the lookup key of the person.
        """
        return self.person.lookup_key

    @classmethod
    def lookup(cls, key):
        p = Person.lookup(key)
        if p is None: return None
        return p.am_or_none

    @classmethod
    def lookup_or_404(cls, key):
        from django.http import Http404
        res = cls.lookup(key)
        if res is not None:
            return res
        raise Http404

class ProcessManager(models.Manager):
    def create_instant_process(self, person, new_status, steps):
        """
        Create a process for the given person to get new_status, with the given
        log entries. The 'process' field of the log entries in steps will be
        filled by this function.

        Return the newly created Process instance.
        """
        if not steps:
            raise ValueError("steps should not be empty")

        if not all(isinstance(s, Log) for s in steps):
            raise ValueError("all entries of steps must be instances of Log")

        # Create a process
        pr = Process(
            person=person,
            applying_as=person.status,
            applying_for=new_status,
            progress=steps[-1].progress,
            is_active=steps[-1].progress not in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED),
        )
        pr.save()

        # Save all log entries
        for l in steps:
            l.process = pr
            l.save()

        return pr

class Process(models.Model):
    """
    A process through which a person gets a new status

    There can be multiple 'Process'es per Person, but only one of them can be
    active at any one time. This is checked during maintenance.
    """
    class Meta:
        db_table = "process"

    # Custom manager
    objects = ProcessManager()

    person = models.ForeignKey(Person, related_name="processes")
    # 1.3-only: person = models.ForeignKey(Person, related_name="processes", on_delete=models.CASCADE)

    applying_as = models.CharField("original status", max_length=20, null=False,
                                    choices=[x[1:3] for x in const.ALL_STATUS])
    applying_for = models.CharField("target status", max_length=20, null=False,
                                    choices=[x[1:3] for x in const.ALL_STATUS])
    progress = models.CharField(max_length=20, null=False,
                                choices=[x[1:3] for x in const.ALL_PROGRESS])

    # This is NULL until one gets a manager
    manager = models.ForeignKey(AM, related_name="processed", null=True, blank=True)
    # 1.3-only: manager = models.ForeignKey(AM, related_name="processed", null=True, on_delete=models.PROTECT)

    advocates = models.ManyToManyField(Person, related_name="advocated", blank=True,
                                limit_choices_to={ "status__in": (const.STATUS_DD_U, const.STATUS_DD_NU) })

    # True if progress NOT IN (PROGRESS_DONE, PROGRESS_CANCELLED)
    is_active = models.BooleanField(null=False, default=False)

    closed = models.DateTimeField(null=True, blank=True, help_text=_("Date the process was closed, or NULL if still open"))

    archive_key = models.CharField("mailbox archive key", max_length=128, null=False, unique=True)

    def save(self, *args, **kw):
        if not self.archive_key:
            ts = now().strftime("%Y%m%d%H%M%S")
            if self.person.uid:
                self.archive_key = "-".join((ts, self.applying_for, self.person.uid))
            else:
                self.archive_key = "-".join((ts, self.applying_for, self.person.email))
        super(Process, self).save(*args, **kw)

    def __unicode__(self):
        return "{} to become {} ({})".format(
            str(self.person),
            const.ALL_STATUS_DESCS.get(self.applying_for, self.applying_for),
            const.ALL_PROGRESS_DESCS.get(self.progress, self.progress),
        )

    def __repr__(self):
        return "{} {}->{}".format(
            self.person.lookup_key,
            self.person.status,
            self.applying_for)

    @models.permalink
    def get_absolute_url(self):
        return ("public_process", (), dict(key=self.lookup_key))

    def get_admin_url(self):
        return reverse("admin:backend_process_change", args=[self.pk])

    @property
    def a_link(self):
        from django.utils.safestring import mark_safe
        from django.utils.html import conditional_escape
        return mark_safe("<a href='{}'>→ {}</a>".format(
            conditional_escape(self.get_absolute_url()),
            conditional_escape(const.ALL_STATUS_DESCS[self.applying_for])))

    @property
    def lookup_key(self):
        """
        Return a key that can be used to look up this process in the database
        using Process.lookup.

        Currently, this is the email if the process is active, else the id.
        """
        # If the process is active, and we only have one process, use the
        # person's lookup key. In all other cases, use the process ID
        if self.is_active:
            if self.person.processes.filter(is_active=True).count() == 1:
                return self.person.lookup_key
            else:
                return str(self.id)
        else:
            return str(self.id)

    @classmethod
    def lookup(cls, key):
        # Key can either be a Process ID or a person's lookup key
        if key.isdigit():
            try:
                return cls.objects.get(id=int(key))
            except cls.DoesNotExist:
                return None
        else:
            # If a person's lookup key is used, and there is only one active
            # process, return that one. Else, return the most recent process.
            p = Person.lookup(key)
            if p is None:
                return None

            # If we reach here, either we have one process, or a new process
            # has been added # changed since the URL was generated. We have an
            # ambiguous situation, which we handle blissfully arbitrarily
            res = p.active_processes
            if res: return res[0]

            try:
                from django.db.models import Max
                return p.processes.annotate(last_change=Max("log__logdate")).order_by("-last_change")[0]
            except IndexError:
                return None

    @classmethod
    def lookup_or_404(cls, key):
        from django.http import Http404
        res = cls.lookup(key)
        if res is not None:
            return res
        raise Http404

    @property
    def mailbox_file(self):
        """
        The pathname of the archival mailbox, or None if it does not exist
        """
        fname = os.path.join(PROCESS_MAILBOX_DIR, self.archive_key) + ".mbox"
        if os.path.exists(fname):
            return fname
        return None

    @property
    def mailbox_mtime(self):
        """
        The mtime of the archival mailbox, or None if it does not exist
        """
        fname = self.mailbox_file
        if fname is None: return None
        return datetime.datetime.utcfromtimestamp(os.path.getmtime(fname)).replace(tzinfo=utc)

    @property
    def archive_email(self):
        if self.person.uid:
            key = self.person.uid
        else:
            key = self.person.email.replace("@", "=")
        return "archive-{}@nm.debian.org".format(key)

    def permissions_of(self, visitor):
        """
        Compute which ProcessVisitorPermissions \a visitor has over this process
        """
        return ProcessVisitorPermissions(self, visitor)

    class DurationStats(object):
        AM_STATUSES = frozenset((const.PROGRESS_AM_HOLD, const.PROGRESS_AM))

        def __init__(self):
            self.first = None
            self.last = None
            self.last_progress = None
            self.total_am_time = 0
            self.total_amhold_time = 0
            self.last_am_time = 0
            self.last_amhold_time = 0
            self.last_am_history = []
            self.last_log_text = None

        def process_last_am_history(self, end=None):
            """
            Compute AM duration stats.

            end is the datetime of the end of the AM stats period. If None, the
            current datetime is used.
            """
            if not self.last_am_history: return
            if end is None:
                end = now()

            time_for_progress = dict()
            period_start = None
            for l in self.last_am_history:
                if period_start is None:
                    period_start = l
                elif l.progress != period_start.progress:
                    days = (l.logdate - period_start.logdate).days
                    time_for_progress[period_start.progress] = \
                            time_for_progress.get(period_start.progress, 0) + days
                    period_start = l

            if period_start:
                days = (end - period_start.logdate).days
                time_for_progress[period_start.progress] = \
                        time_for_progress.get(period_start.progress, 0) + days

            self.last_am_time = time_for_progress.get(const.PROGRESS_AM, 0)
            self.last_amhold_time = time_for_progress.get(const.PROGRESS_AM_HOLD, 0)
            self.total_am_time += self.last_am_time
            self.total_amhold_time += self.last_amhold_time

            self.last_am_history = []

        def process_log(self, l):
            """
            Process a log entry. Log entries must be processed in cronological
            order.
            """
            if self.first is None: self.first = l

            if l.progress in self.AM_STATUSES:
                if self.last_progress not in self.AM_STATUSES:
                    self.last_am_time = 0
                    self.last_amhold_time = 0
                self.last_am_history.append(l)
            elif self.last_progress in self.AM_STATUSES:
                self.process_last_am_history(end=l.logdate)

            self.last = l
            self.last_progress = l.progress

        def stats(self):
            """
            Compute a dict with statistics
            """
            # Process pending AM history items: happens when the last log has
            # AM_STATUSES status
            self.process_last_am_history()
            if self.last is not None and self.first is not None:
                total_duration = (self.last.logdate-self.first.logdate).days
            else:
                total_duration = None

            return dict(
                # Date the process started
                log_first=self.first,
                # Date of the last log entry
                log_last=self.last,
                # Total duration in days
                total_duration=total_duration,
                # Days spent in AM
                total_am_time=self.total_am_time,
                # Days spent in AM_HOLD
                total_amhold_time=self.total_amhold_time,
                # Days spent in AM with the last AM
                last_am_time=self.last_am_time,
                # Days spent in AM_HOLD with the last AM
                last_amhold_time=self.last_amhold_time,
                # Last nonempty log text
                last_log_text=self.last_log_text,
            )

    def duration_stats(self):
        stats_maker = self.DurationStats()
        for l in self.log.order_by("logdate"):
            stats_maker.process_log(l)
        return stats_maker.stats()

    def annotate_with_duration_stats(self):
        s = self.duration_stats()
        for k, v in s.items():
            setattr(self, k, v)

    def finalize(self, logtext, tstamp=None, audit_author=None, audit_notes=None):
        """
        Bring the process to completion, by setting its progress to DONE,
        adding a log entry and updating the person status.
        """
        if self.progress != const.PROGRESS_DAM_OK:
            raise ValueError("cannot finalise progress {}: status is {} instead of {}".format(
                str(self), self.progress, const.PROGRESS_DAM_OK))

        if tstamp is None:
            tstamp = now()

        self.progress = const.PROGRESS_DONE
        self.person.status = self.applying_for
        self.person.status_changed = tstamp
        l = Log(
            changed_by=None,
            process=self,
            progress=self.progress,
            logdate=tstamp,
            logtext=logtext
        )
        l.save()
        self.save()
        self.person.save(audit_author=audit_author, audit_notes=audit_notes)


class Log(models.Model):
    """
    A log entry about anything that happened during a process
    """
    class Meta:
        db_table = "log"

    changed_by = models.ForeignKey(Person, related_name="log_written", null=True)
    # 1.3-only: changed_by = models.ForeignKey(Person, related_name="log_written", on_delete=models.PROTECT, null=True)
    process = models.ForeignKey(Process, related_name="log")
    # 1.3-only: process = models.ForeignKey(Process, related_name="log", on_delete=models.CASCADE)

    # Copied from Process when the log entry is created
    progress = models.CharField(max_length=20, null=False,
                                choices=[(x.tag, x.ldesc) for x in const.ALL_PROGRESS])

    is_public = models.BooleanField(default=False, null=False)
    logdate = models.DateTimeField(null=False, default=now)
    logtext = models.TextField(null=False, blank=True, default="")

    def __unicode__(self):
        return "{}: {}".format(self.logdate, self.logtext)

    @property
    def previous(self):
        """
        Return the previous log entry for this process.

        This fails once every many years when the IDs wrap around, in which
        case it may say that there are no previous log entries. It is ok if you
        use it to send a mail notification, just do not use this method to
        control a nuclear power plant.
        """
        try:
            return Log.objects.filter(id__lt=self.id, process=self.process).order_by("-id")[0]
        except IndexError:
            return None

    @classmethod
    def for_process(cls, proc, **kw):
        kw.setdefault("process", proc)
        kw.setdefault("progress", proc.progress)
        return cls(**kw)


def post_save_log(sender, **kw):
    log = kw.get('instance', None)
    if sender is not Log or not log or kw.get('raw', False):
        return
    if 'created' not in kw:
        # this is a django BUG
        return
    if kw.get('created'):
        # checks for progress transition
        previous_log = log.previous
        if previous_log is None or previous_log.progress == log.progress:
            return

        ### evaluate the progress transition to notify applicant
        ### remember we are during Process.save() method execution
        maybe_notify_applicant_on_progress(log, previous_log)

post_save.connect(post_save_log, sender=Log, dispatch_uid="Log_post_save_signal")


MOCK_FD_COMMENTS = [
    "Cannot get GPG signatures because of extremely sensitive teeth",
    "Only has internet connection on days which are prime numbers",
    "Is a werewolf: warn AM to ignore replies when moon is full",
    "Is a vampire: warn AM not to invite him/her into their home",
    "Is a daemon: if unresponsive, contact Enrico for details about summoning ritual",
]

MOCK_LOGTEXTS = [
    "ok", "hmm", "meh", "asdf", "moo", "...", "üñįç♥ḋə"
]

def export_db(full=False):
    """
    Export the whole databae into a json-serializable array.

    If full is False, then the output is stripped of privacy-sensitive
    information.
    """
    import random

    fd = list(Person.objects.filter(am__is_fd=True))

    # Use order_by so that dumps are easier to diff
    for idx, p in enumerate(Person.objects.all().order_by("uid", "email")):
        # Person details
        ep = dict(
            username=p.username,
            key=p.lookup_key,
            cn=p.cn,
            mn=p.mn,
            sn=p.sn,
            email=p.email,
            uid=p.uid,
            fpr=p.fpr,
            is_staff=p.is_staff,
            is_superuser=p.is_superuser,
            status=p.status,
            status_changed=p.status_changed,
            created=p.created,
            fd_comment=None,
            am=None,
            processes=[],
        )

        if full:
            ep["fd_comment"] = p.fd_comment
        else:
            if random.randint(1, 100) < 20:
                ep["fd_comment"] = random.choice(MOCK_FD_COMMENTS)

        # AM details
        am = p.am_or_none
        if am:
            ep["am"] = dict(
                slots=am.slots,
                is_am=am.is_am,
                is_fd=am.is_fd,
                is_dam=am.is_dam,
                is_am_ctte=am.is_am_ctte,
                created=am.created)

        # Process details
        for pr in p.processes.all().order_by("applying_for"):
            epr = dict(
                applying_as=pr.applying_as,
                applying_for=pr.applying_for,
                progress=pr.progress,
                is_active=pr.is_active,
                archive_key=pr.archive_key,
                manager=None,
                advocates=[],
                log=[],
            )
            ep["processes"].append(epr)

            # Also get a list of actors who can be used for mock logging later
            if pr.manager:
                epr["manager"] = pr.manager.lookup_key
                actors = [pr.manager.person] + fd
            else:
                actors = fd

            for a in pr.advocates.all():
                epr["advocates"].append(a.lookup_key)

            # Log details
            last_progress = None
            for l in pr.log.all().order_by("logdate"):
                if not full and last_progress == l.progress:
                    # Consolidate consecutive entries to match simplification
                    # done by public interface
                    continue

                el = dict(
                    changed_by=None,
                    progress=l.progress,
                    logdate=l.logdate,
                    logtext=None)

                if full:
                    if l.changed_by:
                        el["changed_by"] = l.changed_by.lookup_key
                    el["logtext"] = l.logtext
                else:
                    if l.changed_by:
                        el["changed_by"] = random.choice(actors).lookup_key
                    el["logtext"] = random.choice(MOCK_LOGTEXTS)

                epr["log"].append(el)

                last_progress = l.progress

        yield ep
