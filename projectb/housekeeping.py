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
    Show entries that do not match between projectb DM list and our DB
    """
    DEPENDS = [MakeLink]

    def _list_projectb_dms(self):
        cur = pmodels.cursor()
        cur.execute("""
        SELECT f.fingerprint
          FROM fingerprint AS f
          JOIN keyrings k ON f.keyring = k.id
         WHERE k.name LIKE '%/debian-maintainers.gpg'
        """)
        for fpr, in cur:
            yield fpr

    def run_main(self, stage):
        for fpr in self._list_projectb_dms():
            try:
                f = bmodels.Fingerprint.objects.get(fpr=fpr)
            except bmodels.Fingerprint.DoesNotExist:
                log.warn("%s: %s exists in projectb but not in our DB",
                         self.IDENTIFIER, fpr)
                continue

            if f.person.status not in (const.STATUS_DM, const.STATUS_DM_GA):
                log.warn("%s: %s DB status is %s but it appears to projectb to be a DM instead",
                         self.IDENTIFIER, self.hk.link(f.person), f.person.status)


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
