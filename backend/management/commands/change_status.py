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
        parser.add_argument("--author", action="store", default=getpass.getuser(), help="author of the change")
        parser.add_argument("--execute", action="store_true", help="execute the change")

    def handle(self, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        status = opts["status"]
        author = bmodels.Person.lookup(opts["author"])
        if author is None:
            raise RuntimeError("Author {} not found".format(opts["author"]))
        person = bmodels.Person.lookup(opts["person"])
        if person is None:
            raise RuntimeError("Person {} not found".format(opts["person"]))
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
            audit_time=date,
            person=person,
            status=status,
            rt=ops["rt"],
        )
        print(op.to_json())

        if opts["execute"]:
            with transaction.atomic():
                op.execute()
