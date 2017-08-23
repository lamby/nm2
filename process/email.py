from backend import const
from backend.email import template_to_email
from backend.shortcuts import build_absolute_uri
import backend.models as bmodels
from django.core.mail import send_mail, EmailMessage
from django.utils.timezone import now
from django.contrib.sites.models import Site
import email.message
from email.header import Header
import six
import logging

log = logging.getLogger(__name__)

def _to_header(values):
    from backend.models import Person
    addrs = []
    if not isinstance(values, list):
        values = [values]

    for value in values:
        if isinstance(value, str):
            addrs.append(('', value))
        elif isinstance(value, Person):
            addrs.append((value.fullname, value.email))
        else:
            addrs.append(value)

    return ", ".join(email.utils.formataddr(a) for a in addrs)

def _to_django_addr(value):
    from backend.models import Person
    if isinstance(value, six.string_types):
        return value
    elif isinstance(value, tuple):
        return email.utils.formataddr(value)
    elif isinstance(value, Person):
        return email.utils.formataddr((value.fullname, value.email))
    else:
        raise TypeError("argument is not a string or Person")

def _to_django_addrlist(value):
    from backend.models import Person
    if isinstance(value, six.string_types):
        return [value]
    elif isinstance(value, Person):
        return [email.utils.formataddr((value.fullname, value.email))]
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
    msg["Subject"] = Header(subject, "utf-8")
    msg["Date"] = email.utils.formatdate(time.mktime(date.timetuple()))
    if to: msg["To"] = _to_header(to)
    if cc: msg["Cc"] = _to_header(cc)
    if reply_to: msg["Reply-To"] = _to_header(reply_to)
    msg.set_payload(body, "utf-8")
    return msg


def build_django_message(from_email=None, to=None, cc=None, bcc=None, reply_to=None, subject=None, date=None, headers=None, body=""):
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
    if bcc is not None: kw["bcc"] = _to_django_addrlist(bcc)
    if reply_to is not None: kw["reply_to"] = _to_django_addrlist(reply_to)
    if headers is None: headers = {}
    headers.update(date=email.utils.formatdate(time.mktime(date.timetuple())))

    msg = EmailMessage(
        from_email=_to_django_addr(from_email),
        subject=subject,
        body=body,
        headers=headers,
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
        url = build_absolute_uri(process.get_absolute_url(), request)

    body = """Hello,

you have just started a new process to become {applying_for}.

The nm.debian.org page for managing this process is at {url}

That page lists several requirements that need to be fulfilled for this process
to complete. Some of those you can provide yourself: look at the page for a
list and some explanation.

I hope you have a smooth process, and if you need anything please mail
nm@debian.org.


Yours,
the nm.debian.org housekeeping robot
"""
    body = body.format(applying_for=const.ALL_STATUS_DESCS[process.applying_for], process=process, url=url)

    msg = build_django_message(
        from_email=("nm.debian.org", "nm@debian.org"),
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


def notify_new_statement(statement, request=None, cc_nm=True, notify_ml="newmaint", mia=None):
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
        url = build_absolute_uri(process.get_absolute_url(), request)

    body = """{statement.statement}

{statement.uploaded_by.fullname} (via nm.debian.org)

For details and to comment, visit {url}
"""
    body += "-- \n"
    body += "{url}\n"
    body = body.format(statement=statement, url=url)

    cc = [process.person, process.archive_email]
    if cc_nm:
        cc.append("nm@debian.org")

    headers = {}
    if mia is not None:
        headers["X-MIA-Summary"] = mia
        cc.append("mia-{}@qa.debian.org".format(process.person.uid))

    msg = build_django_message(
        statement.uploaded_by,
        to="debian-{}@lists.debian.org".format(notify_ml),
        cc=cc,
        subject="{}: {}".format(
            process.person.fullname,
            statement.requirement.type_desc),
        headers=headers,
        body=body)
    msg.send()
    log.debug("sent mail from %s to %s cc %s bcc %s subject %s",
            msg.from_email,
            ", ".join(msg.to),
            ", ".join(msg.cc),
            ", ".join(msg.bcc),
            msg.subject)


def notify_new_log_entry(entry, request=None, mia=None):
    """
    Render a notification email template for a newly uploaded process log
    entry, then send the resulting email.
    """
    process = entry.process

    url = build_absolute_uri(process.get_absolute_url(), request)

    body = """{entry.logtext}

{entry.changed_by.fullname} (via nm.debian.org)
"""
    body += "-- \n"
    body += "{url}\n"
    body = body.format(entry=entry, url=url)

    if entry.is_public:
        cc = [process.person, process.archive_email]
        subject = "{}: new public log entry".format(process.person.fullname)
    else:
        cc = []
        subject = "{}: new private log entry".format(process.person.fullname)

    headers = {}
    if mia is not None:
        headers["X-MIA-Summary"] = mia
        cc.append("mia-{}@qa.debian.org".format(process.person.uid))

    msg = build_django_message(
        entry.changed_by,
        to="nm@debian.org",
        cc=cc,
        subject=subject,
        headers=headers,
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
        url = build_absolute_uri(process.get_absolute_url(), request)

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


def notify_new_dd(process, request=None):
    """
    Render a notification email template to let leader@debian.org know of new
    DDs, then send the resulting email.
    """
    if request is None:
        url = "https://{}{}".format(
            Site.objects.get_current().domain,
            process.get_absolute_url())
    else:
        url = build_absolute_uri(process.get_absolute_url(), request)

    body = """Hello,

{process.person.fullname} <{process.person.uid}> has just become a {status}.

The nm.debian.org page for this process is at {url}

Debian New Member Front Desk
"""

    body = body.format(process=process, status=const.ALL_STATUS_DESCS[process.applying_for], url=url)

    msg = build_django_message(
        from_email=("nm.debian.org", "nm@debian.org"),
        to=["leader@debian.org"],
        subject="New {}: {} <{}>".format(const.ALL_STATUS_DESCS[process.applying_for], process.person.fullname, process.person.uid),
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
        url = build_absolute_uri(process.get_absolute_url(), request)

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
        subject="NM process stuck?",
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
