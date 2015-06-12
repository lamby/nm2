from __future__ import absolute_import
from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
from django.utils.log import getLogger
import email
import email.utils
import mailbox
from . import const

log = getLogger(__name__)

EMAIL_PRIVATE_ANNOUNCES = getattr(settings, "EMAIL_PRIVATE_ANNOUNCES", "nm@debian.org")

def parse_recipient_list(s):
    """
    Parse a string like "Foo <a@b.c>, bar@example.com"
    and return a list like ["Foo <a@b.c>", "bar@example.com"]
    """
    res = []
    for name, addr in email.utils.getaddresses([s]):
        res.append(email.utils.formataddr((name, addr)))
    return res

def template_to_email(template_name, context):
    """
    Render a template with its context, parse the result and build an
    EmailMessage from it.
    """
    context.setdefault("default_from", "nm@debian.org")
    context.setdefault("default_subject", "Notification from nm.debian.org")
    text = render_to_string(template_name, context).strip()
    m = email.message_from_string(text.encode('utf-8'))
    msg = EmailMessage()
    msg.from_email = m.get("From", context["default_from"])
    msg.to = parse_recipient_list(m.get("To", EMAIL_PRIVATE_ANNOUNCES))
    if "Cc" in m: msg.cc = parse_recipient_list(m.get("Cc"))
    if "Bcc" in m: msg.bcc = parse_recipient_list(m.get("Bcc"))
    rt = m.get("Reply-To", None)
    if rt is not None: msg.extra_headers["Reply-To"] = rt
    msg.subject = m.get("Subject", context["default_subject"])
    msg.body = m.get_payload()
    return msg

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

def send_nonce(template_name, person, nonce=None, encrypted_nonce=None):
    """
    Render an email template to send a nonce to a person,
    then send the resulting email.
    """
    if nonce is None:
        nonce = person.pending
    try:
        ctx = {
            "person": person,
            "nonce": nonce,
            "encrypted_nonce": encrypted_nonce,
            "reply_to": "todo@example.com",
            "default_subject": "Confirmation from nm.debian.org",
        }
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
        log.debug("failed to sent mail for person %s", person)


def get_mbox_as_dicts(filename):
    try:  ## we are reading, have not to flush with close
        for message in mailbox.mbox(filename, create=False):
            if(message.is_multipart()):
                yield dict(Body=message.get_payload(0), **dict(message))
            else:
                yield dict(Body=message.get_payload(), **dict(message))
    except mailbox.NoSuchMailboxError:
        return
