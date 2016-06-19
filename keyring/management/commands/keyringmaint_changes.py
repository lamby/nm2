# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.core.management.base import BaseCommand, CommandError
import optparse
import sys
import datetime
import logging
import keyring.models as kmodels
from keyring.git import GitKeyring

log = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "dump changes from keyring-maint"
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet", default=None, help="Disable progress reporting"),
        optparse.make_option("--since", action="store", dest="since", default=None, help="Initial date"),
        optparse.make_option("--until", action="store", dest="until", default=None, help="Final date"),
    )

    def handle(self, since=None, until=None, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            logging.basicConfig(level=logging.INFO, stream=sys.stderr, format=FORMAT)

        if until is None: until = datetime.date.today().strftime("%Y-%m-%d")
        if since is None: since = (datetime.datetime.strptime(until, "%Y-%m-%d") - datetime.timedelta(days=60)).strftime("%Y-%m-%d")

        gk = GitKeyring()
        for shasum, ts in gk.get_valid_shasums("--since", since, "--until", until):
            c = gk.get_commit_message(shasum)
            print(shasum, ts, repr(c))
