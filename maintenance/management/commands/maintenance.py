# nm.debian.org website maintenance
#
# Copyright (C) 2012  Enrico Zini <enrico@debian.org>
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

from django.core.management.base import BaseCommand, CommandError
import django.db
from django.conf import settings
from django.db import connection, transaction
from django.contrib.sites.models import Site
import optparse
import sys
import datetime
import logging
import json
import os
import os.path
import gzip
import time
from backend import models as bmodels
from backend import const
from backend import utils
import keyring.models as kmodels
import dsa.models as dmodels
import projectb.models as pmodels

log = logging.getLogger(__name__)

BACKUP_DIR = getattr(settings, "BACKUP_DIR", None)

class Checker(object):
    def __init__(self, quick=False, **kw):
        self.site = Site.objects.get_current()
        if not quick:
            log.info("Importing dm keyring...")
            self.dm = frozenset(kmodels.list_dm())
            log.info("Importing dd_u keyring...")
            self.dd_u = frozenset(kmodels.list_dd_u())
            log.info("Importing dd_nu keyring...")
            self.dd_nu = frozenset(kmodels.list_dd_nu())
            log.info("Importing emeritus_dd keyring...")
            self.emeritus_dd = frozenset(kmodels.list_emeritus_dd())
            log.info("Importing removed_dd keyring...")
            self.removed_dd = frozenset(kmodels.list_removed_dd())

    def _link(self, obj):
        if self.site.domain == "localhost":
            return "http://localhost:8000" + obj.get_absolute_url()
        else:
            return "https://%s%s" % (self.site.domain, obj.get_absolute_url())

    def backup_db(self, **kw):
        if BACKUP_DIR is None:
            log.info("BACKUP_DIR is not set: skipping backups")
            return

        people = list(bmodels.export_db(full=True))

        class Serializer(json.JSONEncoder):
            def default(self, o):
                if hasattr(o, "strftime"):
                    return o.strftime("%Y-%m-%d %H:%M:%S")
                return json.JSONEncoder.default(self, o)

        # Base filename for the backup
        fname = os.path.join(BACKUP_DIR, datetime.datetime.utcnow().strftime("%Y%m%d-db-full.json.gz"))
        # Use a sequential number to avoid overwriting old backups when run manually
        while os.path.exists(fname):
            time.sleep(0.5)
            fname = os.path.join(BACKUP_DIR, datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S-db-full.json.gz"))
        log.info("backing up to %s", fname)
        # Write the backup file
        with utils.atomic_writer(fname, 0640) as fd:
            try:
                gzfd = gzip.GzipFile(filename=fname[:-3], mode="w", compresslevel=9, fileobj=fd)
                json.dump(people, gzfd, cls=Serializer, indent=2)
            finally:
                gzfd.close()


    @transaction.commit_on_success
    def compute_am_ctte(self, **kw):
        from django.db.models import Max
        # Set all to False
        bmodels.AM.objects.update(is_am_ctte=False)

        cutoff = datetime.datetime.utcnow()
        cutoff = cutoff - datetime.timedelta(days=30*6)

        # Set the active ones to True
        cursor = connection.cursor()
        cursor.execute("""
        SELECT am.id
          FROM am
          JOIN process p ON p.manager_id=am.id AND p.progress IN (%s, %s)
          JOIN log ON log.process_id=p.id AND log.logdate > %s
         WHERE am.is_am AND NOT am.is_fd AND NOT am.is_dam
         GROUP BY am.id
        """, (const.PROGRESS_DONE, const.PROGRESS_CANCELLED, cutoff))
        ids = [x[0] for x in cursor]

        bmodels.AM.objects.filter(id__in=ids).update(is_am_ctte=True)
        transaction.commit_unless_managed()
        log.info("%d CTTE members", bmodels.AM.objects.filter(is_am_ctte=True).count())


    @transaction.commit_on_success
    def compute_process_is_active(self, **kw):
        """
        Compute Process.is_active from Process.progress
        """
        cursor = connection.cursor()
        cursor.execute("""
        UPDATE process SET is_active=(progress NOT IN (%s, %s))
        """, (const.PROGRESS_DONE, const.PROGRESS_CANCELLED))
        transaction.commit_unless_managed()
        log.info("%d/%d active processes",
                 bmodels.Process.objects.filter(is_active=True).count(),
                 cursor.rowcount)

    @transaction.commit_on_success
    def compute_progress_finalisations_on_accounts_created(self, **kw):
        """
        Update pending dm_ga processes after the account is created
        """
        # Get a lits of accounts from DSA
        dm_ga_uids = set()
        dd_uids = set()
        for entry in dmodels.list_people():
            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None:
                dd_uids.add(entry.uid)
            else:
                dm_ga_uids.add(entry.uid)

        # Check if pending processes got an account
        for proc in bmodels.Process.objects.filter(is_active=True):
            if proc.progress != const.PROGRESS_DAM_OK: continue
            finalised_msg = None

            if proc.applying_for == const.STATUS_DM_GA and proc.person.uid in dm_ga_uids:
                finalised_msg = "guest LDAP account created by DSA"
            if proc.applying_for in (const.STATUS_DD_NU, const.STATUS_DD_U) and proc.person.uid in dd_uids:
                finalised_msg = "LDAP account created by DSA"

            if finalised_msg is not None:
                old_status = proc.person.status
                proc.finalize(finalised_msg)
                log.info(u"%s finalised: %s changes status %s->%s", self._link(proc), proc.person.uid, old_status, proc.person.status)

    @transaction.commit_on_success
    def compute_new_guest_accounts_from_dsa(self, **kw):
        """
        Create new Person entries for guest accounts created by DSA
        """
        for entry in dmodels.list_people():
            # Skip DDs
            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None: continue

            # Skip people we already know of
            if bmodels.Person.objects.filter(uid=entry.uid).exists(): continue

            # Skip people without fingerprints
            if entry.single("keyFingerPrint") is None: continue

            # Skip entries without emails (happens when running outside of the Debian network)
            if entry.single("emailForward") is None: continue

            # Check for fingerprint duplicates
            try:
                p = bmodels.Person.objects.get(fpr=entry.single("keyFingerPrint"))
                log.warning("%s has the same fingerprint as LDAP uid %s", self._link(p), entry.uid)
                continue
            except bmodels.Person.DoesNotExist:
                pass

            p = bmodels.Person(
                cn=entry.single("cn"),
                mn=entry.single("mn"),
                sn=entry.single("sn"),
                email=entry.single("emailForward"),
                uid=entry.uid,
                fpr=entry.single("keyFingerPrint"),
                status=const.STATUS_MM_GA,
            )
            p.save()
            log.info("%s (guest account only) imported from LDAP", self._link(p))

    #@transaction.commit_on_success
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

    def check_one_process_per_person(self, **kw):
        """
        Check that one does not have more than one open process at the current time
        """
        from django.db.models import Count
        for p in bmodels.Person.objects.filter(processes__is_active=True) \
                 .annotate(num_processes=Count("processes")) \
                 .filter(num_processes__gt=1):
            log.warning("%s has %d open processes", self._link(p), p.num_processes)
            for idx, proc in enumerate(p.processes.filter(is_active=True)):
                log.warning(" %d: %s (%s)", idx+1, self._link(proc), repr(proc))

    def check_am_must_have_uid(self, **kw):
        """
        Check that one does not have more than one open process at the current time
        """
        from django.db.models import Count
        for am in bmodels.AM.objects.filter(person__uid=None):
            log.warning("AM %d (person %d %s) has no uid", am.id, am.person.id, am.person.email)

    def check_status_progress_match(self, **kw):
        """
        Check that the last process with progress 'done' has the same
        'applying_for' as the person status
        """
        from django.db.models import Max
        for p in bmodels.Person.objects.all():
            try:
                last_proc = bmodels.Process.objects.filter(person=p, progress=const.PROGRESS_DONE).annotate(ended=Max("log__logdate")).order_by("-ended")[0]
            except IndexError:
                continue
            if p.status != last_proc.applying_for:
                log.warning("%s has status %s but the last completed process was applying for %s",
                            p.uid, p.status, last_proc.applying_for)

    def check_log_progress_match(self, **kw):
        """
        Check that the last process with progress 'done' has the same
        'applying_for' as the person status
        """
        from django.db.models import Max
        for p in bmodels.Process.objects.filter(is_active=True):
            try:
                last_log = p.log.order_by("-logdate")[0]
            except IndexError:
                log.warning("%s (%s) has no log entries", self._link(p), repr(p))
                continue
            if p.progress != last_log.progress:
                log.warning("%s (%s) has progress %s but the last log entry has progress %s",
                            self._link(p), repr(p), p.progress, last_log.progress)

    def check_enums(self, **kw):
        """
        Consistency check of enum values
        """
        statuses = [x.tag for x in const.ALL_STATUS]
        progresses = [x.tag for x in const.ALL_PROGRESS]

        for p in bmodels.Person.objects.exclude(status__in=statuses):
            log.warning("%s: invalid status %s", self._link(p), p.status)

        for p in bmodels.Process.objects.exclude(applying_for__in=statuses):
            log.warning("%s: invalid applying_for %s", self._link(p), p.applying_for)

        for p in bmodels.Process.objects.exclude(progress__in=progresses):
            log.warning("%s: invalid progress %s", self._link(p), p.progress)

        for l in bmodels.Log.objects.exclude(progress__in=progresses):
            log.warning("%s: log entry %d has invalid progress %s", self._link(l.process), l.id, l.progress)

    def check_corner_cases(self, **kw):
        """
        Check for known corner cases, to be fixed somehow eventually maybe in case
        they give trouble
        """
        c = bmodels.Person.objects.filter(processes__isnull=True).count()
        if c > 0:
            log.warning("%d Great Ancients found who have no Process entry", c)

        c = bmodels.Person.objects.filter(status_changed__isnull=True).count()
        if c > 0:
            log.warning("%d entries still have a NULL status_changed date", c)

    def check_keyring_consistency(self, quick=False, **kw):
        """
        Show entries that do not match between keyrings and our DB
        """
        if quick:
            log.info("Skipping check_keyring_consistency because --quick was used")
            return

        # Prefetch people and index them by fingerprint
        people_by_fpr = dict()
        for p in bmodels.Person.objects.all():
            if p.fpr is None: continue
            people_by_fpr[p.fpr] = p

        keyring_by_status = {
            const.STATUS_DM: self.dm,
            const.STATUS_DM_GA: self.dm,
            const.STATUS_DD_U: self.dd_u,
            const.STATUS_DD_NU: self.dd_nu,
            const.STATUS_EMERITUS_DD: self.emeritus_dd,
            const.STATUS_REMOVED_DD: self.removed_dd,
        }

        count = 0

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
                    log.warning("%s has status %s but is in %s keyring (fpr: %s)", self._link(p), p.status, status, fpr)
                    count += 1
                    found = True
                    break
            if not found and p.status != const.STATUS_REMOVED_DD:
                log.warning("%s has status %s but is not in any keyring (fpr: %s)", self._link(p), p.status, fpr)
                count += 1

        # Spot fingerprints not in our DB
        for status, keyring in keyring_by_status.iteritems():
            # TODO: not quite sure how to handle the removed_dd keyring, until I
            #       know what exactly is in there
            if status == const.STATUS_REMOVED_DD: continue
            for fpr in keyring:
                if fpr not in people_by_fpr:
                    log.warning("Fingerprint %s is in %s keyring but not in our db", fpr, status)
                    count += 1

        log.warning("%d mismatches between keyring and nm.debian.org databases", count)


    def check_ldap_consistency(self, quick=False, **kw):
        """
        Show entries that do not match between LDAP and our DB
        """
        # Prefetch people and index them by fingerprint
        people_by_uid = dict()
        for p in bmodels.Person.objects.all():
            if p.uid is None: continue
            people_by_uid[p.uid] = p

        for entry in dmodels.list_people():
            try:
                person = bmodels.Person.objects.get(uid=entry.uid)
            except bmodels.Person.DoesNotExist:
                log.warning("Person %s exists in LDAP but not in our db", entry.uid)
                continue

            if entry.single("gidNumber") == "800" and entry.single("keyFingerPrint") is not None:
                if person.status not in (const.STATUS_DD_U, const.STATUS_DD_NU):
                    log.warning("%s has gidNumber 800 and a key, but the db has state %s", self._link(person), person.status)

    def check_dmlist(self, quick=False, **kw):
        """
        Show entries that do not match between projectb DM list and out DB
        """
        # Code used to import DMs is at 64a3e35a5c55aa3ee122e6234ad24c74a57dd843
        # Now this is just a consistency check
        try:
            maints = pmodels.Maintainers()
        except Exception, e:
            log.info("Skipping check_dmlist: %s", e)
            return

        def check_status(p):
            if p.status not in (const.STATUS_DM, const.STATUS_DM_GA):
                log.info("%s DB status is %s but it appears to projectb to be a DM instead", self._link(p), p.status)

        for maint in maints.db.itervalues():
            person = bmodels.Person.lookup(maint["fpr"])
            if person is not None:
                check_status(person)
                continue

            person = bmodels.Person.lookup(maint["email"])
            if person is not None:
                log.info("%s matches by email %s with projectb but not by key fingerprint", self._link(person), maint["email"])
                check_status(person)
                continue

            log.info("%s/%s exists in projectb but not in our DB", maint["email"], maint["fpr"])


    def check_django_permissions(self, **kw):
        from django.contrib.auth.models import User
        from django.db.models import Q

        # Get the list of users that django thinks are powerful
        django_power_users = set()
        for u in User.objects.all():
            if u.is_staff or u.is_superuser:
                django_power_users.add(u.id)

        # Get the list of users that we think are powerful
        nm_power_users = set()
        for a in bmodels.AM.objects.filter(Q(is_fd=True) | Q(is_dam=True)):
            if a.person.user is None:
                log.warning("%s: no corresponding django user", self._link(a.person))
            else:
                nm_power_users.add(a.person.user.id)

        for id in (django_power_users - nm_power_users):
            log.warning("auth.models.User.id %d has powers that the NM site does not know about", id)
        for id in (nm_power_users - django_power_users):
            log.warning("auth.models.User.id %d has powers in NM that django does not know about", id)


    def run(self, **opts):
        """
        Run all checker functions
        """
        import inspect
        for prefix in ("backup", "compute", "check"):
            for name, meth in inspect.getmembers(self, predicate=inspect.ismethod):
                if not name.startswith(prefix + "_"): continue
                log.info("running %s", name)
                meth(**opts)


class Command(BaseCommand):
    help = 'Daily maintenance of the nm.debian.org database'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("--quick", action="store_true", help="Skip slow checks. Default: %default"),
    )

    def handle(self, *fnames, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        checker = Checker(**opts)
        checker.run(**opts)
