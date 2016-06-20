# nm.debian.org website housekeeping
# pymode:lint_ignore=E501
#
# Copyright (C) 2012--2014  Enrico Zini <enrico@debian.org>
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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.timezone import now
from django.conf import settings
import django_housekeeping as hk
from django.db import connection, transaction
from django.contrib.sites.models import Site
from . import models as bmodels
from . import utils, const
import gzip
import datetime
import json
import os.path
import logging

log = logging.getLogger(__name__)

BACKUP_DIR = getattr(settings, "BACKUP_DIR", None)

STAGES = ["backup", "main", "stats"]

class Housekeeper(hk.Task):
    NAME = "housekeeper"

    def __init__(self, *args, **kw):
        super(Housekeeper, self).__init__(*args, **kw)
        # Ensure that there is a __housekeeping__ user
        try:
            self.user = bmodels.Person.objects.get(username="__housekeeping__")
        except bmodels.Person.DoesNotExist:
            self.user = bmodels.Person.objects.create_user(
                username="__housekeeping__",
                is_staff=False,
                cn="Housekeeping",
                sn="Robot",
                email="nm@debian.org",
                bio="I am the robot that runs the automated tasks in the site",
                uid=None,
                status=const.STATUS_DC,
                audit_skip=True)


class MakeLink(hk.Task):
    NAME = "link"

    def __init__(self, *args, **kw):
        super(MakeLink, self).__init__(*args, **kw)
        self.site = Site.objects.get_current()

    def __call__(self, obj):
        if self.site.domain == "localhost":
            return "http://localhost:8000" + obj.get_absolute_url()
        else:
            return "https://%s%s" % (self.site.domain, obj.get_absolute_url())


class BackupDB(hk.Task):
    """
    Backup of the whole database
    """
    def run_backup(self, stage):
        if self.hk.outdir is None:
            log.info("HOUSEKEEPING_ROOT is not set: skipping backups")
            return

        people = list(bmodels.export_db(full=True))

        class Serializer(json.JSONEncoder):
            def default(self, o):
                if hasattr(o, "strftime"):
                    return o.strftime("%Y-%m-%d %H:%M:%S")
                return json.JSONEncoder.default(self, o)

        # Base filename for the backup
        basedir = self.hk.outdir.path()
        fname = os.path.join(basedir, "db-full.json.gz")
        log.info("%s: backing up to %s", self.IDENTIFIER, fname)
        if self.hk.dry_run:
            return

        # Write the backup file
        with utils.atomic_writer(fname, 0640) as fd:
            try:
                gzfd = gzip.GzipFile(filename=fname[:-3], mode="w", compresslevel=9, fileobj=fd)
                json.dump(people, gzfd, cls=Serializer, indent=2)
            finally:
                gzfd.close()


class ComputeAMCTTE(hk.Task):
    """
    Compute AM Committee membership
    """
    @transaction.atomic
    def run_main(self, stage):
        # Set all to False
        bmodels.AM.objects.update(is_am_ctte=False)

        cutoff = now()
        cutoff = cutoff - datetime.timedelta(days=30 * 6)

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
        log.info("%s: %d CTTE members", self.IDENTIFIER, bmodels.AM.objects.filter(is_am_ctte=True).count())


class ComputeProcessActiveFlag(hk.Task):
    """
    Compute Process.is_active from Process.progress
    """
    @transaction.atomic
    def run_main(self, stage):
        cursor = connection.cursor()
        cursor.execute("""
            UPDATE process SET is_active=(progress NOT IN (%s, %s))
        """, (const.PROGRESS_DONE, const.PROGRESS_CANCELLED))
        log.info("%s: %d/%d active processes",
                 self.IDENTIFIER,
                 bmodels.Process.objects.filter(is_active=True).count(),
                 cursor.rowcount)


class PersonExpires(hk.Task):
    """
    Expire old Person records
    """
    DEPENDS = [MakeLink, Housekeeper]

    @transaction.atomic
    def run_main(self, stage):
        """
        Generate a sequence of Person objects that have expired
        """
        today = datetime.date.today()
        for p in bmodels.Person.objects.filter(expires__lt=today):
            if p.status != const.STATUS_DC:
                log.info("%s: removing expiration date for %s who has become %s",
                         self.IDENTIFIER, self.hk.link(p), p.status)
                p.expires = None
                p.save(audit_author=self.hk.housekeeper.user, audit_notes="user became {}: removing expiration date".format(const.ALL_STATUS_DESCS[p.status]))
            elif p.processes.exists():
                log.info("%s: removing expiration date for %s who now has process history",
                         self.IDENTIFIER, self.hk.link(p))
                p.expires = None
                p.save(audit_author=self.hk.housekeeper.user, audit_notes="process detected: removing expiration date")
            else:
                log.info("%s: deleting expired Person %s", self.IDENTIFIER, p)
                p.delete()


class CheckOneProcessPerPerson(hk.Task):
    """
    Check that one does not have more than one open process at the current time
    """
    DEPENDS = [MakeLink]

    def run_main(self, stage):
        from django.db.models import Count
        for p in bmodels.Person.objects.filter(processes__is_active=True) \
                .annotate(num_processes=Count("processes")) \
                .filter(num_processes__gt=1):
            log.warn("%s: %s has %d open processes", self.IDENTIFIER, self.hk.link(p), p.num_processes)


class CheckAMMustHaveUID(hk.Task):
    """
    Check that AMs have a Debian login
    """
    def run_main(self, stage):
        for am in bmodels.AM.objects.filter(person__uid=None):
            log.warning("%s: AM %d (person %d %s) has no uid", self.IDENTIFIER, am.id, am.person.id, am.person.email)


class CheckStatusProgressMatch(hk.Task):
    """
    Check that the last process with progress 'done' has the same
    'applying_for' as the person status
    """
    DEPENDS = [MakeLink]

    def run_main(self, stage):
        from django.db.models import Max
        for p in bmodels.Person.objects.all():
            try:
                last_proc = bmodels.Process.objects.filter(person=p, progress=const.PROGRESS_DONE).annotate(ended=Max("log__logdate")).order_by("-ended")[0]
            except IndexError:
                continue
            if p.status != last_proc.applying_for:
                log.warn("%s: %s has status %s but the last completed process was applying for %s",
                         self.IDENTIFIER, self.hk.link(p), p.status, last_proc.applying_for)


class CheckLogProgressMatch(hk.Task):
    """
    Check that the last process with progress 'done' has the same
    'applying_for' as the person status
    """
    DEPENDS = [MakeLink]

    def run_main(self, stage):
        for p in bmodels.Process.objects.filter(is_active=True):
            try:
                last_log = p.log.order_by("-logdate")[0]
            except IndexError:
                log.warning("%s: %s (%s) has no log entries", self.IDENTIFIER, self.hk.link(p), repr(p))
                continue
            if p.progress != last_log.progress:
                log.warning("%s: %s (%s) has progress %s but the last log entry has progress %s",
                            self.IDENTIFIER, self.hk.link(p), repr(p), p.progress, last_log.progress)


class CheckEnums(hk.Task):
    """
    Consistency check of enum values
    """
    DEPENDS = [MakeLink]

    def run_main(self, stage):
        statuses = [x.tag for x in const.ALL_STATUS]
        progresses = [x.tag for x in const.ALL_PROGRESS]

        for p in bmodels.Person.objects.exclude(status__in=statuses):
            log.warning("%s: %s: invalid status %s", self.IDENTIFIER, self.hk.link(p), p.status)

        for p in bmodels.Process.objects.exclude(applying_for__in=statuses):
            log.warning("%s: %s: invalid applying_for %s", self.IDENTIFIER, self.hk.link(p), p.applying_for)

        for p in bmodels.Process.objects.exclude(progress__in=progresses):
            log.warning("%s: %s: invalid progress %s", self.IDENTIFIER, self.hk.link(p), p.progress)

        for l in bmodels.Log.objects.exclude(progress__in=progresses):
            log.warning("%s: %s: log entry %d has invalid progress %s",
                        self.IDENTIFIER, self.hk.link(l.process), l.id, l.progress)


class CheckCornerCases(hk.Task):
    """
    Check for known corner cases, to be fixed somehow eventually maybe in case
    they give trouble
    """
    def run_main(self, stage):
        c = bmodels.Person.objects.filter(processes__isnull=True).count()
        if c > 0:
            log.info("%s: %d Great Ancients found who have no Process entry", self.IDENTIFIER, c)

        c = bmodels.Person.objects.filter(status_changed__isnull=True).count()
        if c > 0:
            log.warning("%s: %d entries still have a NULL status_changed date", self.IDENTIFIER, c)


class CheckDjangoPermissions(hk.Task):
    """
    Check consistency between Django permissions and flags in the AM model
    """
    DEPENDS = [MakeLink]

    def run_main(self, stage):
        from django.db.models import Q

        # Get the list of users that django thinks are powerful
        person_power_users = set()
        for p in bmodels.Person.objects.all():
            if p.is_staff or p.is_superuser:
                person_power_users.add(p.id)

        # Get the list of users that we think are powerful
        am_power_users = set()
        for a in bmodels.AM.objects.filter(Q(is_fd=True) | Q(is_dam=True)):
            am_power_users.add(a.person.id)

        for id in (person_power_users - am_power_users):
            p = bmodels.Person.objects.get(pk=id)
            log.warning("%s: bmodels.Person.id %d (%s) has powers that bmodels.AM does not know about",
                        self.IDENTIFIER, id, p.lookup_key)
        for id in (am_power_users - person_power_users):
            p = bmodels.Person.objects.get(pk=id)
            log.warning("%s: bmodels.Person.id %d (%s) has powers in bmodels.AM that bmodels.Person does not know about",
                        self.IDENTIFIER, id, p.lookup_key)

class DDUsernames(hk.Task):
    """
    Make sure that people with a DD status have a DD SSO username
    """
    DEPENDS = [MakeLink, Housekeeper]

    @transaction.atomic
    def run_main(self, stage):
        dd_statuses = (const.STATUS_DD_U, const.STATUS_DD_NU,
                       const.STATUS_EMERITUS_DD, const.STATUS_EMERITUS_DM,
                       const.STATUS_REMOVED_DD, const.STATUS_REMOVED_DM)
        for p in bmodels.Person.objects.filter(status__in=dd_statuses):
            if p.uid is None:
                log.warning("%s: %s has status %s but uid is empty",
                            self.IDENTIFIER, self.hk.link(p), p.status)
                continue
            if p.username.endswith("@debian.org"): continue
            new_username = p.uid + "@debian.org"
            log.info("%s: %s has status %s but an alioth username: setting username to %s",
                        self.IDENTIFIER, self.hk.link(p), p.status, new_username)
            p.username = new_username
            p.save(audit_author=self.hk.housekeeper.user, audit_notes="updated SSO username to @debian.org version")

class CheckOneActiveKeyPerPerson(hk.Task):
    """
    Check that one does not have more than one open process at the current time
    """
    DEPENDS = [MakeLink]

    def run_main(self, stage):
        from django.db.models import Count
        for p in bmodels.Person.objects.filter(fprs__is_active=True) \
                .annotate(num_fprs=Count("fprs")) \
                .filter(num_fprs__gt=1):
            log.warn("%s: %s has %d active keys", self.IDENTIFIER, self.hk.link(p), p.num_fprs)
