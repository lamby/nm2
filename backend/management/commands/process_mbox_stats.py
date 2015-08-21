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
import datetime
import time
import json
import os

log = logging.getLogger(__name__)


def median(l):
    """
    Compute the median of a sequence of numbers
    """
    if not l: return None

    l = sorted(l)

    if len(l) == 1: return l[0]
    idx, is_odd = divmod(len(l) - 1, 2)

    if is_odd:
        return l[idx]
    else:
        return (l[idx] + l[idx + 1]) / 2.0


class Interaction(object):
    data = {'emails': {}, 'process': {}}
    unsort_data = []

    @classmethod
    def _add_data(cls, key, data_key, data, date_diff):
        if data[data_key] not in cls.data[key]:
            cls.data[key][data[data_key]] = {
                'num_mails': 1,
                'date_first': data['date'],
                'date_last': data['date'],
                'date_last_orig': data['date_orig'],
                'date_first_orig': data['date_orig'],
                'response_time': []
            }
        else:
            d = cls.data[key][data[data_key]]
            d['num_mails'] = d['num_mails'] + 1
            d['date_last'] = data['date']
            d['date_last_orig'] = data['date_orig']
            if date_diff is not None:
                d['response_time'].append(date_diff)

    @classmethod
    def _add(cls, data):
        if data['process'] not in cls.data['process']:
            date_diff = None
            cls._add_data('process', 'process', data, date_diff)
            log.debug("%s skiped. First mail" % data['date_orig'])
            cls._add_data('emails', 'From', data, date_diff)
        else:
            d = cls.data['process'][data['process']]
            date_diff = data['date'] - d['date_last']
            cls._add_data('process', 'process', data, date_diff)
            log.debug("%s - %s -> %s" % (data['date_orig'],
                                         d['date_last_orig'], date_diff))
            if(date_diff > 0):
                cls._add_data('emails', 'From', data, date_diff)
            else:
                log.warn("date_diff: %s skiped!!" % date_diff)

    def add(self, process_key, msg):
        d = {'process': process_key}
        d['date'] = time.mktime(email.utils.parsedate(msg["Date"]))
        d['date_orig'] = msg["Date"]
        t, d['From'] = email.utils.parseaddr(msg["From"].lower())
        if "@" not in d['From']:
            d['From'] = d['From'] + "@debian.org"
        self.unsort_data.append(d)

    @classmethod
    def _median(cls, process_key):
        if process_key is not None:
            if process_key in cls.data['process']:
                d = cls.data['process'][process_key]
                log.debug("response_time: %s" % d['response_time'])
                d['median'] = median(d['response_time'])
                log.debug("%s -> median: %s" % (process_key, d['median']))
        else:
            for k, d in cls.data['emails'].iteritems():
                if d['num_mails'] > 1:
                    d['median'] = median(d['response_time'])

    def generate_stats(self, process_key):
        self.sort_data = sorted(self.unsort_data,
                                key=lambda x: x['date'], reverse=False)
        self.unsort_data = []
        for d in self.sort_data:
            self._add(d)
        self._median(process_key)

    def generate_email_stats(self):
        self._median(None)

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
                level = logging.INFO
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
                log.warn("%s[%s] skiped, no mailbox file defined" %
                         (unicode(progress), key))

        interactions.generate_email_stats()
        interactions.export(os.path.join(settings.DATA_DIR, 'mbox_stats.json'))
