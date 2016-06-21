# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.utils.timezone import now
import django_housekeeping as hk
import datetime
from backend.housekeeping import Housekeeper
from .maintenance import ping_stuck_processes

STAGES = ["main"]

class WarnProcessesStuckEarly(hk.Task):
    DEPENDS = [Housekeeper]

    def run_main(self, stage):
        stuck_cutoff = now() - datetime.timedelta(days=7)
        ping_stuck_processes(stuck_cutoff, self.hk.housekeeper.user)
