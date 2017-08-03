from django.conf import settings
from django.core.mail import send_mail, EmailMessage
from django.template.loader import render_to_string
import email
import email.utils
try:
    from email.Iterators import typed_subpart_iterator
except ImportError:
    from email.iterators import typed_subpart_iterator
import mailbox
from . import const
import logging

log = logging.getLogger(__name__)

EMAIL_PRIVATE_ANNOUNCES = getattr(settings, "EMAIL_PRIVATE_ANNOUNCES", "nm@debian.org")

def get_charset(message, default="ascii"):
    """Get the message charset"""

    if message.get_content_charset():
        return message.get_content_charset()

    if message.get_charset():
        return message.get_charset()

    return default

def get_body(message):
    """Get the body of the email message"""
    if message.is_multipart():
        #get the plain text version only
        text_parts = [part
                      for part in typed_subpart_iterator(message,
                                                         'text',
                                                         'plain')]
        body = []
        for part in text_parts:
            charset = get_charset(part, get_charset(message))
            body.append(str(part.get_payload(decode=True),
                                charset,
                                "replace"))
        return "\n".join(body).strip()
    else: # if it is not multipart, the payload will be a string
          # representing the message body
        body = str(message.get_payload(decode=True),
                       get_charset(message),
                       "replace")
        return body.strip()

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
    m = email.message_from_string(text)
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

def decode_header(val):
    res = []
    for buf, charset in email.header.decode_header(val):
        if charset is None:
            if isinstance(buf, bytes):
                res.append(buf.decode("utf-8", errors="replace"))
            else:
                res.append(buf)
        elif charset == "unknown-8bit":
            res.append(buf.decode("utf-8", errors="replace"))
        else:
            res.append(buf.decode(charset, errors="replace"))
    return " ".join(res)

def get_mbox_as_dicts(filename):
    try:  ## we are reading, have not to flush with close
        for message in mailbox.mbox(filename, create=False):
            msg_dict = {'Body': get_body(message)}
            for hkey, hval in list(message.items()):
                msg_dict[hkey] = decode_header(hval)
            yield msg_dict
    except mailbox.NoSuchMailboxError:
        return
