# nm.debian.org website maintenance
#
# Copyright (C) 2015  Victor Seva <linuxmaniac@torreviejawireless.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from django.core.management.base import BaseCommand, CommandError
import django.db
from django.conf import settings
import optparse
import sys
import logging
from backend import models as bmodels
from backend import const
import email.utils
import mailbox
import time
import json
import os
import pprint

log = logging.getLogger(__name__)

pp = pprint.PrettyPrinter(indent=2)

class Interaction(object):
    data = {'emails': {}, 'process': {}}
    unsort_data = []

    @classmethod
    def _add_email(cls, data, date_diff):
        if data['From'] not in cls.data['emails']:
            cls.data['emails'][data['From']] = {
                'num_mails': 1,
                'date_first': data['date'],
                'date_last': data['date'],
                'date_last_orig': data['date_orig'],
                'date_first_orig': data['date_orig'],
                'response_time': []
            }
        else:
            d = cls.data['emails'][data['From']]
            d['num_mails'] = d['num_mails'] + 1
            d['date_last'] = data['date']
            d['date_last_orig'] = data['date_orig']
            if date_diff is not None:
                d['response_time'].append(date_diff)

    @classmethod
    def _add(cls, data):
        if data['process'] not in cls.data['process']:
            cls.data['process'][data['process']] = {
                'num_mails': 1,
                'date_first': data['date'],
                'date_last': data['date'],
                'date_last_orig': data['date_orig'],
                'date_first_orig': data['date_orig'],
                'response_time': []
            }
            date_diff = None
            log.debug("%s skiped. First mail" % data['date_orig'])
            cls._add_email(data, date_diff)
        else:
            d = cls.data['process'][data['process']]
            d['num_mails'] = d['num_mails'] + 1
            date_diff = data['date'] - d['date_last']
            log.debug("%s - %s -> %s" % (data['date_orig'],
                d['date_last_orig'], date_diff))
            d['date_last'] = data['date']
            d['date_last_orig'] = data['date_orig']
            if(date_diff>0):
                d['response_time'].append(date_diff)
                cls._add_email(data, date_diff)
            else:
                log.warn("date_diff: %s skiped!!" % date_diff)

    def add(self, process_key, msg):
        d = { 'process': process_key }
        d['date'] = time.mktime(email.utils.parsedate(msg["Date"]))
        d['date_orig'] = msg["Date"]
        t, d['From'] = email.utils.parseaddr(msg["From"].lower())
        if "@" not in d['From']:
            d['From'] = d['From'] + "@debian.org"
        self.unsort_data.append(d)

    def generate_stats(self, process_key):
        #log.debug("unsort: %s" % pp.pformat(self.unsort_data))
        self.sort_data = sorted(self.unsort_data,
            key=lambda x: x['date'], reverse=False)
        #log.debug("sort: %s" % pp.pformat(self.sort_data))
        self.unsort_data = []
        for d in self.sort_data:
            self._add(d)

    def export(self, filename):
        with open(filename, 'w') as outfile:
            json.dump(self.data, outfile)

class Command(BaseCommand):
    help = 'Generate stats for Process'
    option_list = BaseCommand.option_list + (
        optparse.make_option("--quiet", action="store_true", dest="quiet",
                             default=None, help="Disable progress reporting"),
        optparse.make_option("--debug", action="store_true", dest="debug",
                             default=None, help="Enable debug"),
    )

    def handle(self, *args, **opts):
        FORMAT = "%(asctime)-15s %(levelname)s %(message)s"
        if opts["quiet"]:
            logging.basicConfig(
                level=logging.WARNING, stream=sys.stderr, format=FORMAT)
        else:
            if opts["debug"]:
                level = logging.DEBUG
            else:
                level = loggin.INFO
            logging.basicConfig(
                level=level, stream=sys.stderr, format=FORMAT)

        managed_process = \
            bmodels.Process.objects.filter(manager__isnull=False)
        interactions = Interaction()

        for progress in managed_process:
            key = progress.lookup_key
            mailbox_file = progress.mailbox_file
            log.debug("%s[%s] -> %s" % (unicode(progress), key, mailbox_file))
            if mailbox_file:
                for msg in mailbox.mbox(mailbox_file, create=False):
                    interactions.add(key, msg)
                interactions.generate_stats(key)
                log.info("%s processed", mailbox_file)
            else:
                log.warn("skiped, no mailbox file defined")

        interactions.export(os.path.join(settings.DATA_DIR, 'mbox_stats.json'))
