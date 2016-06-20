# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
import sys
import datetime
import logging
import keyring.models as kmodels
from keyring.git import GitKeyring
from keyring import git_ops
from backend.ops import Operation

log = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "run a JSON-encoded operation from standard input"

    def add_arguments(self, parser):
        parser.add_argument("--quiet", action="store_true", help="Disable progress reporting")

    def handle(self, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        with transaction.atomic():
            op = Operation.from_json(sys.stdin.read())
            op.execute()
