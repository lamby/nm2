# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from backend import const
from backend.email import template_to_email
from django.contrib.sites.models import Site
import logging

log = logging.getLogger(__name__)


def notify_new_statement(statement, request=None):
    """
    Render a notification email template for a newly uploaded statement, then
    send the resulting email.
    """
    try:
        if request is None:
            url = "https://{}{}".format(
                Site.objects.get_current().domain,
                statement.requirement.get_absolute_url())
        else:
            url = request.build_absolute_uri(statement.requirement.get_absolute_url())

        ctx = {
            "statement": statement,
            "process": statement.requirement.process,
            "default_subject": "Notification from nm.debian.org",
            "url": url,
        }
        ctx["default_from"] = statement.uploaded_by.preferred_email
        msg = template_to_email("notification_mails/new_statement.txt", ctx)
        msg.send()
        log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
                msg.from_email,
                ", ".join(msg.to),
                ", ".join(msg.cc),
                ", ".join(msg.bcc),
                msg.subject)
    except:
        # TODO: remove raise once it works
        raise
        log.debug("failed to sent mail for statement %s", statement)


def send_notification(template_name, log_next, log_prev=None):
    """
    Render a notification email template for a transition from log_prev to log,
    then send the resulting email.
    """
    try:
        ctx = {
            "process": log_next.process,
            "log": log_next,
            "log_prev": log_prev,
            "default_subject": "Notification from nm.debian.org",
        }
        if log_next.changed_by is not None:
            ctx["default_from"] = log_next.changed_by.preferred_email
        msg = template_to_email(template_name, ctx)
        msg.send()
        log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
                msg.from_email,
                ", ".join(msg.to),
                ", ".join(msg.cc),
                ", ".join(msg.bcc),
                msg.subject)
    except:
        # TODO: remove raise once it works
        raise
        log.debug("failed to sent mail for log %s", log_next)


def maybe_notify_applicant_on_progress(log, previous_log):
    """
    Notify applicant via e-mail about progress of this process, if it is interesting.
    """
    if previous_log is None:
        ## this is strange no previous log, do nothing
        return

    from_progress = previous_log.progress
    to_progress = log.progress

    ################################################################
    # * When they get in the queue to get an AM assigned

    #   This happens when Process.progress goes from [anything except app_ok]
    #   to app_ok.

    #   Use cases:
    #    - FD may skip any step from initial contact to having things ready
    #      for AM assignment
    #    - an AM may get busy and hand an applicant back to FD. That would be
    #      a transition from any of (am_rcvd, am, am_hold) to app_ok
    ################################################################

    if from_progress in (const.PROGRESS_APP_NEW,
                         const.PROGRESS_APP_RCVD,
                         const.PROGRESS_APP_HOLD,
                         const.PROGRESS_ADV_RCVD,
                         const.PROGRESS_POLL_SENT,
                         const.PROGRESS_AM_RCVD,
                         const.PROGRESS_AM,
                         const.PROGRESS_AM_HOLD):

        if to_progress == const.PROGRESS_APP_OK:
            # mail applicant in the queue to get an AM assigned
            send_notification(
                "notification_mails/applicant_waiting_for_am.txt",
                log, previous_log)
            return

    ################################################################
    # * When an AM is assigned to an applicant

    #   This happens when Process.progress goes from app_ok to am_rcvd
    ################################################################

    if from_progress == const.PROGRESS_APP_OK:
        if to_progress == const.PROGRESS_AM_RCVD:
            # mail applicant in the queue to get an AM assigned
            send_notification(
                "notification_mails/am_assigned_to_applicant.txt",
                log, previous_log)
            return



    ################################################################
    # * When an AM approves the applicant, mail debian-newmaint

    # This happens only when Process.progress goes from one of (am_rcvd,
    #                                                            am, am_hold) to am_ok.

    # Use case: the AM can decide to approve an applicant whatever previous
    # progress they were in.

    # The email shouldn't however be triggered if, for example, FD just
    # unholds an application but hasn't finished with their review: that
    # would be a (fd_hold -> am_ok) change.
    ################################################################

    if from_progress in (const.PROGRESS_AM_RCVD,
                         const.PROGRESS_AM,
                         const.PROGRESS_AM_HOLD):

        if to_progress == const.PROGRESS_AM_OK:
            # mail debian-newmaint AM approved Applicant
            # with https://lists.debian.org/debian-newmaint/2009/04/msg00026.html
            send_notification("notification_mails/am_approved_applicant.txt",
                              log, previous_log)
            return

    ################################################################
    # * When they get approved by FD

    #   This happens only when Process.progress goes from one of (am_ok,
    #   fd_hold) to fd_ok.
    ################################################################
    if from_progress in (const.PROGRESS_AM_OK,
                         const.PROGRESS_FD_HOLD):

        if to_progress == const.PROGRESS_FD_OK:
            # mail applicant in the queue to get an AM assigned
            send_notification("notification_mails/fd_approved_applicant.txt",
                              log, previous_log)
            r
