# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import utc, now
from django.db import transaction
import dateutil.parser
import sys
import datetime
import logging
import backend.models as bmodels
import backend.ops as bops
import getpass

log = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "change the status of a person"

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true", help="Disable progress reporting")
        parser.add_argument("--date", help="Set date for status change")
        parser.add_argument("--rt", help="RT issue number")
        parser.add_argument("-m", "--message", help="Message to use in audit notes")
        parser.add_argument("person", help="status to set")
        parser.add_argument("status", help="status to set")
        parser.add_argument("--author", action="store", default=getpass.getuser(), help="Author")

    def handle(self, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        status = opts["status"]
        author = bmodels.Person.lookup(opts["author"])
        person = bmodels.Person.lookup(opts["person"])
        message = opts["message"]
        if not message:
            message = "Set status to {}".format(status)
        if opts["rt"]:
            message += " RT#{}".format(opts["rt"])
        if opts["date"]:
            date = dateutil.parser.parse(opts["date"])
        else:
            date = now()

        op = bops.ChangeStatus(
            audit_author=author,
            audit_notes=message,
            person=person,
            status=status,
            status_changed=date,
        )
        print(op.to_json())
