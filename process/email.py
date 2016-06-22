# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from backend import const
from backend.email import template_to_email
import backend.models as bmodels
from django.core.mail import send_mail, EmailMessage
from django.utils.timezone import now
from django.contrib.sites.models import Site
import email.message
from email.header import Header
import six
import logging

log = logging.getLogger(__name__)

def _to_header(value):
    from backend.models import Person
    if isinstance(value, six.string_types):
        return Header(value, "utf-8")
    elif isinstance(value, Person):
        return email.utils.formataddr((
            Header(value.fullname, "utf-8").encode(),
            Header(value.email, "utf-8").encode()
        ))
    else:
        return ", ".join(_to_header(x) for x in value)

def _to_django_addrlist(value):
    from backend.models import Person
    if isinstance(value, six.string_types):
        return [value]
    elif isinstance(value, Person):
        return [email.utils.formataddr((
            Header(value.fullname, "utf-8").encode(),
            Header(value.email, "utf-8").encode()
        ))]
    else:
        res = []
        for item in value:
            res.extend(_to_django_addrlist(item))
        return res


def build_python_message(from_email=None, to=None, cc=None, reply_to=None, subject=None, date=None, body="", factory=email.message.Message):
    """
    Build an email.message.Message, or equivalent object, from common
    arguments.

    If from_email, to, cc, bcc, reply_to can be strings or bmodels.Person objects.
    """
    # Generating mailboxes in python2 is surprisingly difficult and painful.
    # A lot of this code has been put together thanks to:
    # http://wordeology.com/computer/how-to-send-good-unicode-email-with-python.html
    import email.utils
    import time

    if from_email is None: from_email = "nm@debian.org"
    if subject is None: subject = "Notification from nm.debian.org"
    if date is None: date = now()

    msg = factory()
    msg["From"] = _to_header(from_email)
    msg["Subject"] = _to_header(subject)
    msg["Date"] = email.utils.formatdate(time.mktime(date.timetuple()))
    if to: msg["To"] = _to_header(to)
    if cc: msg["Cc"] = _to_header(cc)
    if reply_to: msg["Reply-To"] = _to_header(reply_to)
    msg.set_payload(body, "utf-8")
    return msg


def build_django_message(from_email=None, to=None, cc=None, reply_to=None, subject=None, date=None, body=""):
    """
    Build a Django EmailMessage from common arguments.

    If from_email, to, cc, bcc, reply_to can be strings or bmodels.Person objects.
    """
    # Generating mailboxes in python2 is surprisingly difficult and painful.
    # A lot of this code has been put together thanks to:
    # http://wordeology.com/computer/how-to-send-good-unicode-email-with-python.html
    import email.utils
    import time

    if from_email is None: from_email = "nm@debian.org"
    if subject is None: subject = "Notification from nm.debian.org"
    if date is None: date = now()

    kw = {}
    if to is not None: kw["to"] = _to_django_addrlist(to)
    if cc is not None: kw["cc"] = _to_django_addrlist(cc)
    if reply_to is not None: kw["reply_to"] = _to_django_addrlist(reply_to)

    msg = EmailMessage(
        from_email=_to_header(from_email),
        subject=subject,
        body=body,
        headers={
            "date": email.utils.formatdate(time.mktime(date.timetuple())),
        },
        **kw
    )
    return msg


def notify_new_process(process, request=None):
    """
    Render a notification email template for a newly uploaded statement, then
    send the resulting email.
    """
    if request is None:
        url = "https://{}{}".format(
            Site.objects.get_current().domain,
            process.get_absolute_url())
    else:
        url = request.build_absolute_uri(process.get_absolute_url())

    body = """Hello,

you have just started a new process to become {applying_for}.

The nm.debian.org page for managing this process is at {url}

That page lists several requirements that need to be fulfilled for this process
to complete. Some of those you can provide yourself: look at the page for a
list and some explanation.

I hope you have a smooth process, and if you need anything please mail
nm@debian.org."


Yours,
the nm.debian.org housekeeping robot
"""
    body = body.format(applying_for=const.ALL_STATUS_DESCS[process.applying_for], process=process, url=url)

    msg = build_django_message(
        email.utils.formataddr((
            Header("nm.debian.org", "utf-8").encode(),
            Header("nm@debian.org", "utf-8").encode()
        )),
        to=process.person,
        cc=process.archive_email,
        subject="New Member process, {}".format(const.ALL_STATUS_DESCS[process.applying_for]),
        body=body)
    msg.send()
    log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
            msg.from_email,
            ", ".join(msg.to),
            ", ".join(msg.cc),
            ", ".join(msg.bcc),
            msg.subject)


def notify_new_statement(statement, request=None):
    """
    Render a notification email template for a newly uploaded statement, then
    send the resulting email.
    """
    process = statement.requirement.process

    if request is None:
        url = "https://{}{}".format(
            Site.objects.get_current().domain,
            process.get_absolute_url())
    else:
        url = request.build_absolute_uri(process.get_absolute_url())

    body = """{statement.statement}

{statement.uploaded_by.fullname} (via nm.debian.org)
"""
    body += "-- \n"
    body += "{url}\n"
    body = body.format(statement=statement, url=url)

    msg = build_django_message(
        statement.uploaded_by,
        to="debian-newmaint@lists.debian.org",
        cc=[process.person, "nm@debian.org", process.archive_email],
        subject="{}: {}".format(
            process.person.fullname,
            statement.requirement.type_desc),
        body=body)
    msg.send()
    log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
            msg.from_email,
            ", ".join(msg.to),
            ", ".join(msg.cc),
            ", ".join(msg.bcc),
            msg.subject)


def notify_am_assigned(assignment, request=None):
    """
    Render a notification email template for an AM assignment, then send the
    resulting email.
    """
    process = assignment.process

    if request is None:
        url = "https://{}{}".format(
            Site.objects.get_current().domain,
            process.get_absolute_url())
    else:
        url = request.build_absolute_uri(process.get_absolute_url())

    body = """Hello,

{process.person.fullname} meet {am.person.fullname}, your new application manager.
{am.person.fullname} meet {process.person.fullname}, your new applicant.

The next step is usually one of these:
- the application manager sends an email to the applicant starting a
conversation;
- the application manager has no time and goes to {url}/am_ok
to undo the assignment.

The nm.debian.org page for this process is at {url}

I hope you have a good time, and if you need anything please mail nm@debian.org.

{assignment.assigned_by.fullname} for Front Desk
"""

    body = body.format(process=process, am=assignment.am.person, assignment=assignment, url=url)

    msg = build_django_message(
        assignment.assigned_by,
        to=[process.person, assignment.am.person],
        cc=process.archive_email,
        subject="New Member process, {}".format(const.ALL_STATUS_DESCS[process.applying_for]),
        body=body)
    msg.send()
    log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
            msg.from_email,
            ", ".join(msg.to),
            ", ".join(msg.cc),
            ", ".join(msg.bcc),
            msg.subject)


def ping_process(pinger, process, message=None, request=None):
    """
    Render a notification email template for pinging a stuck process, then send
    the resulting email.
    """
    if request is None:
        url = "https://{}{}".format(
            Site.objects.get_current().domain,
            process.get_absolute_url())
    else:
        url = request.build_absolute_uri(process.get_absolute_url())

    format_args = {
        "process": process,
        "pinger": pinger,
        "url": url,
    }

    body = ["""Hello,

the process at {url} looks stuck.
""".format(**format_args)]

    if message: body.append(message)

    body.append("""
If you need help with anything, please mail nm@debian.org.

{pinger.fullname} for Front Desk
""".format(**format_args))

    to = [process.person]
    assignment = process.current_am_assignment
    if assignment:
        to.append(assignment.am.person)

    msg = build_django_message(
        pinger,
        to=to,
        cc=[process.archive_email, "nm@debian.org"],
        subject="Process stuck?",
        body="".join(body))
    msg.send()
    log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
            msg.from_email,
            ", ".join(msg.to),
            ", ".join(msg.cc),
            ", ".join(msg.bcc),
            msg.subject)


#def send_notification(template_name, log_next, log_prev=None):
#    """
#    Render a notification email template for a transition from log_prev to log,
#    then send the resulting email.
#    """
#    try:
#        ctx = {
#            "process": log_next.process,
#            "log": log_next,
#            "log_prev": log_prev,
#            "default_subject": "Notification from nm.debian.org",
#        }
#        if log_next.changed_by is not None:
#            ctx["default_from"] = log_next.changed_by.preferred_email
#        msg = template_to_email(template_name, ctx)
#        msg.send()
#        log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
#                msg.from_email,
#                ", ".join(msg.to),
#                ", ".join(msg.cc),
#                ", ".join(msg.bcc),
#                msg.subject)
#    except:
#        # TODO: remove raise once it works
#        raise
#        log.debug("failed to sent mail for log %s", log_next)
#
#
#def maybe_notify_applicant_on_progress(log, previous_log):
#    """
#    Notify applicant via e-mail about progress of this process, if it is interesting.
#    """
#    if previous_log is None:
#        ## this is strange no previous log, do nothing
#        return
#
#    from_progress = previous_log.progress
#    to_progress = log.progress
#
#    ################################################################
#    # * When they get in the queue to get an AM assigned
#
#    #   This happens when Process.progress goes from [anything except app_ok]
#    #   to app_ok.
#
#    #   Use cases:
#    #    - FD may skip any step from initial contact to having things ready
#    #      for AM assignment
#    #    - an AM may get busy and hand an applicant back to FD. That would be
#    #      a transition from any of (am_rcvd, am, am_hold) to app_ok
#    ################################################################
#
#    if from_progress in (const.PROGRESS_APP_NEW,
#                         const.PROGRESS_APP_RCVD,
#                         const.PROGRESS_APP_HOLD,
#                         const.PROGRESS_ADV_RCVD,
#                         const.PROGRESS_POLL_SENT,
#                         const.PROGRESS_AM_RCVD,
#                         const.PROGRESS_AM,
#                         const.PROGRESS_AM_HOLD):
#
#        if to_progress == const.PROGRESS_APP_OK:
#            # mail applicant in the queue to get an AM assigned
#            send_notification(
#                "notification_mails/applicant_waiting_for_am.txt",
#                log, previous_log)
#            return
#
#    ################################################################
#    # * When an AM is assigned to an applicant
#
#    #   This happens when Process.progress goes from app_ok to am_rcvd
#    ################################################################
#
#    if from_progress == const.PROGRESS_APP_OK:
#        if to_progress == const.PROGRESS_AM_RCVD:
#            # mail applicant in the queue to get an AM assigned
#            send_notification(
#                "notification_mails/am_assigned_to_applicant.txt",
#                log, previous_log)
#            return
#
#
#
#    ################################################################
#    # * When an AM approves the applicant, mail debian-newmaint
#
#    # This happens only when Process.progress goes from one of (am_rcvd,
#    #                                                            am, am_hold) to am_ok.
#
#    # Use case: the AM can decide to approve an applicant whatever previous
#    # progress they were in.
#
#    # The email shouldn't however be triggered if, for example, FD just
#    # unholds an application but hasn't finished with their review: that
#    # would be a (fd_hold -> am_ok) change.
#    ################################################################
#
#    if from_progress in (const.PROGRESS_AM_RCVD,
#                         const.PROGRESS_AM,
#                         const.PROGRESS_AM_HOLD):
#
#        if to_progress == const.PROGRESS_AM_OK:
#            # mail debian-newmaint AM approved Applicant
#            # with https://lists.debian.org/debian-newmaint/2009/04/msg00026.html
#            send_notification("notification_mails/am_approved_applicant.txt",
#                              log, previous_log)
#            return
#
#    ################################################################
#    # * When they get approved by FD
#
#    #   This happens only when Process.progress goes from one of (am_ok,
#    #   fd_hold) to fd_ok.
#    ################################################################
#    if from_progress in (const.PROGRESS_AM_OK,
#                         const.PROGRESS_FD_HOLD):
#
#        if to_progress == const.PROGRESS_FD_OK:
#            # mail applicant in the queue to get an AM assigned
#            send_notification("notification_mails/fd_approved_applicant.txt",
#                              log, previous_log)
#            r
