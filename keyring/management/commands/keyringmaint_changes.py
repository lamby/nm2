# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError
import optparse
import sys
import logging
import keyring.models as kmodels

log = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "dump changes from keyring-maint"
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
    )

    def handle(self, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        gk = kmodels.GitKeyring()
        for shasum, ts in gk.get_valid_shasums("--since", "2016-01-01", "--until", "2016-06-19"):
            c = gk.get_commit_message(shasum)
            print(shasum, ts, repr(c))
