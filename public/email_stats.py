#!/usr/bin/python
# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import mailbox
import email
import os
import time
from collections import Counter, defaultdict

class Event(object):
    """
    Store timespans in which the only sender seen in a mailbox was 'addr'
    """
    def __init__(self, addr, ts):
        self.addr = addr
        self.begin = ts
        self.until = ts

    def print(self, file=None):
        if self.begin != self.until:
            print("{}: {}-{}".format(self.addr, self.begin, self.until), file=file)
        else:
            print("{}: {}".format(self.addr, self.begin), file=file)

class Timeline(object):
    """
    Store consecutive events
    """
    def __init__(self):
        self.events = []

    def add(self, ts, addr):
        if not self.events or self.events[-1].addr != addr:
            self.events.append(Event(addr, ts))
        else:
            self.events[-1].until = ts

    def gap_lengths(self, ts_now=None):
        if ts_now is None: ts_now = time.time()
        for idx, evt in enumerate(self.events):
            if idx < len(self.events) - 1:
                ts_next = self.events[idx + 1].begin
            else:
                ts_next = ts_now
            yield evt.addr, ts_next - evt.until

    def print(self, file=None):
        for e in self.events:
            e.print(file=file)

def read_mbox(pathname):
    """
    Parse a mailbox and return a sequence of:
    (timestamp, sender email address, sender real name)
    """
    mbox = mailbox.mbox(pathname)
    for msg in mbox:
        realname, addr = email.utils.parseaddr(msg["From"])
        ts = email.utils.mktime_tz(email.utils.parsedate_tz(msg["Date"]))
        yield ts, addr, realname

def aggregate(parsed_mbox):
    """
    Given (timestamp, address, realname) tuples, generate the same tuples
    replacing address with the most common address among those used by people
    with the same realname
    """
    # Convert into a list so we can iterate it twice
    parsed_mbox = list(parsed_mbox)

    # Map realnames to set of email addresses with their occurrence count
    by_realname = defaultdict(Counter)
    for ts, addr, realname in parsed_mbox:
        if realname.endswith(" via nm"): realname = realname[:-7]
        by_realname[realname][addr] += 1

    # Compute the most common address for a realname
    aliases = {}
    for c in by_realname.itervalues():
        ranked = c.most_common()
        for addr, count in ranked:
            aliases[addr] = ranked[0][0]

    for ts, addr, relname in parsed_mbox:
        yield ts, aliases[addr], relname

def filter_top2(parsed_mbox):
    """
    Given (timestamp, address, realname) tuples, generate only those of the two
    most common addresses
    """
    # Convert into a list so we can iterate it twice
    parsed_mbox = list(parsed_mbox)

    # Count how many time addresses appear
    addr_count = Counter()
    for ts, addr, realname in parsed_mbox:
        addr_count[addr] += 1

    whitelist = { x[0] for x in addr_count.most_common(2) }
    for ts, addr, realname in parsed_mbox:
        if addr not in whitelist: continue
        yield ts, addr, realname

def mailbox_get_gaps(pathname):
    """
    Compute waiting gaps for a mailbox
    """
    timeline = Timeline()
    for ts, addr, realname in sorted(filter_top2(aggregate(read_mbox(pathname)))):
        timeline.add(ts, addr)
    return timeline.gap_lengths()

#for f in os.listdir("."):
#    if not f.endswith(".mbox"): continue
#    print(" *", f)
#    #for ts, addr, realname in aggregate(read_mbox(f)):
#    #    print(ts, addr, realname)
#    timeline = Timeline()
#    for ts, addr, realname in sorted(filter_top2(aggregate(read_mbox(f)))):
#        timeline.add(ts, addr)
#    byaddr = {}
#    for addr, length in timeline.gap_lengths():
#        byaddr.setdefault(addr, []).append(length)
#        print(addr, length)
#    for addr, lengths in byaddr.iteritems():
#        print("Avg wtime for {}: {}".format(addr, sum(lengths)/len(lengths)))
#
#    #timeline.print()
