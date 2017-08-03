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
import django_housekeeping as hk
from backend.housekeeping import MakeLink
import backend.models as bmodels
from backend import const
from . import models as pmodels
import logging

log = logging.getLogger(__name__)

STAGES = ["main"]

class CheckDMList(hk.Task):
    """
    Show entries that do not match between projectb DM list and out DB
    """
    DEPENDS = [MakeLink]

    def run_main(self, stage):
        # Code used to import DMs is at 64a3e35a5c55aa3ee122e6234ad24c74a57dd843
        # Now this is just a consistency check
        maints = pmodels.Maintainers()

        def check_status(p):
            if p.status not in (const.STATUS_DM, const.STATUS_DM_GA):
                log.info("%s: %s DB status is %s but it appears to projectb to be a DM instead",
                         self.IDENTIFIER, self.maint.link(p), p.status)

        for maint in maints.db.values():
            person = bmodels.Person.lookup(maint["fpr"])
            if person is not None:
                check_status(person)
                continue

            person = bmodels.Person.lookup(maint["email"])
            if person is not None:
                log.info("%s: %s matches by email %s with projectb but not by key fingerprint",
                         self.IDENTIFIER, self.maint.link(person), maint["email"])
                check_status(person)
                continue

            log.info("%s: %s/%s exists in projectb but not in our DB",
                     self.IDENTIFIER, maint["email"], maint["fpr"])


class UpdateLastUpload(hk.Task):
    """
    Update fingerprint.last_upload dates
    """
    DEPENDS = [MakeLink]

    def run_main(self, stage):
        by_fpr = {}

        with pmodels.cursor() as cur:
            cur.execute("""
SELECT MAX(s.install_date) as date, f.fingerprint
          FROM source s
          JOIN fingerprint f ON s.sig_fpr = f.id
       GROUP BY f.fingerprint
""")
            for date, fpr in cur:
                by_fpr[fpr] = date
            
        for fpr in bmodels.Fingerprint.objects.all():
            date = by_fpr.get(fpr.fpr)
            if date is None: continue
            if date == fpr.last_upload: continue
            fpr.last_upload = date
            # Skip audit since we are only updating statistics data
            fpr.save(audit_skip=True)
