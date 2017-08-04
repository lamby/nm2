from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from backend.housekeeping import MakeLink
import django_housekeeping as hk
import backend.models as bmodels
from backend import const
import debiancontributors as dc
import requests
import datetime
import os
import logging

log = logging.getLogger(__name__)

DC_AUTH_TOKEN = getattr(settings, "DC_AUTH_TOKEN", None)
DC_SUBMIT_URL = getattr(settings, "DC_SUBMIT_URL", None)
DC_GIT_REPO_NM = getattr(settings, "DC_GIT_REPO_NM", "/srv/nm.debian.org/nm2/.git")
DC_GIT_REPO_DC = getattr(settings, "DC_GIT_REPO_DC", "/srv/contributors.debian.org/dc/.git")

STAGES = ["main", "reports", "stats"]


class SubmitContributors(hk.Task):
    """
    Compute contributions and submit them to contributors.debian.org
    """
    DEPENDS = [MakeLink]

    def run_reports(self, stage):
        from django.db.models import Min, Max

        if DC_AUTH_TOKEN is None:
            if settings.DEBUG:
                log.warning("DC_AUTH_TOKEN is not configured, we cannot submit to contributors.debian.org")
                log.warning("Stopping processing here, this would result in an exception in production.")
                return
            else:
                raise ImproperlyConfigured("DC_AUTH_TOKEN is not configured, we cannot submit to contributors.debian.org")

        datamine = dc.DataMine(configstr="""
source: nm.debian.org

contribution: dc-devel
method: gitlogs
dirs: {git_repo_dc}

contribution: nm-devel
method: gitlogs
dirs: {git_repo_nm}
""".format(git_repo_dc=DC_GIT_REPO_DC, git_repo_nm=DC_GIT_REPO_NM))
        datamine.scan()
        submission = datamine.submission

        for am in bmodels.AM.objects.all():
            res = bmodels.Log.objects.filter(changed_by=am.person, process__manager=am).aggregate(
                since=Min("logdate"),
                until=Max("logdate"))
            if res["since"] is None or res["until"] is None:
                continue
            submission.add_contribution_data(
                dc.Identifier(type="login", id=am.person.uid, desc=am.person.fullname),
                type="am", begin=res["since"].date(), end=res["until"].date(),
                url=self.hk.link(am))

        for am in bmodels.AM.objects.filter(is_fd=True):
            res = bmodels.Log.objects.filter(changed_by=am.person).exclude(process__manager=am).aggregate(
                since=Min("logdate"),
                until=Max("logdate"))
            if res["since"] is None or res["until"] is None:
                continue
            submission.add_contribution_data(
                dc.Identifier(type="login", id=am.person.uid, desc=am.person.fullname),
                type="fd", begin=res["since"].date(), end=res["until"].date(),
                url=self.hk.link(am))

        submission.set_auth_token(DC_AUTH_TOKEN)
        if DC_SUBMIT_URL:
            submission.baseurl = DC_SUBMIT_URL

        res, info = submission.post()
        if not res:
            log.error("%s: submission failed: %r", self.IDENTIFIER, info)


class UpdateLastVote(hk.Task):
    """
    Update fingerprint.last_vote dates
    """
    DEPENDS = [MakeLink]

    def _fetch_url(self, url):
        bundle="/etc/ssl/ca-debian/ca-certificates.crt"
        if os.path.exists(bundle):
            return requests.get(url, verify=bundle)
        else:
            return requests.get(url)

    def run_main(self, stage):
        res = self._fetch_url("https://contributors.debian.org/mia/last-significant.json")
        by_type = res.json()
        votes = by_type["vote.debian.org/vote"]

        by_uid = {}
        for person in bmodels.Person.objects.filter(status__in=(const.STATUS_DD_U, const.STATUS_DD_NU)):
            by_uid[person.uid] = person

        for uid, date in votes.items():
            date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
            person = by_uid.get(uid)
            if person is None: continue
            if person.last_vote == date: continue
            # Skip audit since we are only updating statistics data
            person.last_vote = date
            person.save(audit_skip=True)
