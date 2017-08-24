from django.utils.timezone import now
import datetime
from . import models as pmodels

def ping_stuck_processes(stuck_cutoff, audit_author, logdate=None):
    from .email import ping_process
    if logdate is None: logdate = now()

    for process in pmodels.Process.objects.in_early_stage():
        already_pinged = False
        for idx, entry in enumerate(process.log.order_by("logdate")):
            if entry.action == "ping":
                already_pinged = True
        if entry.logdate > stuck_cutoff: continue

        if not already_pinged:
            # Detect first instance of processes stuck early: X days from
            # last log, no previous ping message
            ping_process(audit_author, process, message="""
If nothing happens, the process will be automatically closed a week from now.
""")
            process.add_log(audit_author, "looks stuck, pinged", action="ping", logdate=logdate)
        else:
            # Detect second instance: X days from last log, no
            # intent/advocate/sc_dmup, a previous ping message
            ping_process(audit_author, process, message="""
A week has passed from the last ping with no action, I'll now close the
process. Feel free to reapply in the future.
""")
            process.add_log(audit_author, "closing for inactivity", action="proc_close", logdate=logdate)
            process.closed_by = audit_author
            process.closed_time = logdate
            process.save()


