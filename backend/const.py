from collections import namedtuple

Status = namedtuple("Status", ("code", "tag", "sdesc", "ldesc"))
Progress = namedtuple("Progress", ("code", "tag", "sdesc", "ldesc"))

g = globals()

# Status of a person in Debian
ALL_STATUS = (
    Status("STATUS_DC",            "dc",      "DC",              "Debian Contributor"),
    Status("STATUS_DC_GA",         "dc_ga",   "DC+account",      "Debian Contributor, with guest account"),
    Status("STATUS_DM",            "dm",      "DM",              "Debian Maintainer"),
    Status("STATUS_DM_GA",         "dm_ga",   "DM+account",      "Debian Maintainer, with guest account"),
    Status("STATUS_DD_U",          "dd_u",    "DD, upl.",        "Debian Developer, uploading"),
    Status("STATUS_DD_NU",         "dd_nu",   "DD, non-upl.",    "Debian Developer, non-uploading"),
    Status("STATUS_EMERITUS_DD",   "dd_e",    "DD, emeritus",    "Debian Developer, emeritus"),
    Status("STATUS_REMOVED_DD",    "dd_r",    "DD, removed",     "Debian Developer, removed"),
)
ALL_STATUS_DESCS = dict((x.tag, x.ldesc) for x in ALL_STATUS)
ALL_STATUS_BYTAG = dict((x.tag, x) for x in ALL_STATUS)
for s in ALL_STATUS:
    g[s.code] = s.tag

SEQ_STATUS = dict(((y.tag, x) for x, y in enumerate(ALL_STATUS)))

# Progress of a person in a process
ALL_PROGRESS = (
    Progress("PROGRESS_APP_NEW",   "app_new",   "Applied",     "Applicant asked to enter the process"),
    Progress("PROGRESS_APP_RCVD",  "app_rcvd",  "Validated",   "Applicant replied to initial mail"),
    Progress("PROGRESS_APP_HOLD",  "app_hold",  "App hold",    "On hold before entering the queue"),
    Progress("PROGRESS_ADV_RCVD",  "adv_rcvd",  "Adv ok",      "Received enough advocacies"),
    Progress("PROGRESS_POLL_SENT", "poll_sent", "Poll sent",   "Activity poll sent"),
    Progress("PROGRESS_APP_OK",    "app_ok",    "App ok",      "Advocacies have been approved"),
    Progress("PROGRESS_AM_RCVD",   "am_rcvd",   "AM assigned", "Waiting for AM to confirm"),
    Progress("PROGRESS_AM",        "am",        "AM",          "Interacting with an AM"),
    Progress("PROGRESS_AM_HOLD",   "am_hold",   "AM hold",     "AM hold"),
    Progress("PROGRESS_AM_OK",     "am_ok",     "AM ok",       "AM approved"),
    Progress("PROGRESS_FD_HOLD",   "fd_hold",   "FD hold",     "FD hold"),
    Progress("PROGRESS_FD_OK",     "fd_ok",     "FD ok",       "FD approved"),
    Progress("PROGRESS_DAM_HOLD",  "dam_hold",  "DAM hold",    "DAM hold"),
    Progress("PROGRESS_DAM_OK",    "dam_ok",    "DAM ok",      "DAM approved"),
    Progress("PROGRESS_DONE",      "done",      "Done",        "Completed"),
    Progress("PROGRESS_CANCELLED", "cancelled", "Cancelled",    "Cancelled"),
)
ALL_PROGRESS_DESCS = dict((x.tag, x.ldesc) for x in ALL_PROGRESS)
ALL_PROGRESS_BYTAG = dict((x.tag, x) for x in ALL_PROGRESS)
for p in ALL_PROGRESS:
    g[p.code] = p.tag

SEQ_PROGRESS = dict(((y.tag, x) for x, y in enumerate(ALL_PROGRESS)))
