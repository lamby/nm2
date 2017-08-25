from django.utils.translation import ugettext as _
from django import http, forms
from django.conf import settings
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now
from django.views.generic import View, TemplateView
import backend.models as bmodels
from backend import const
from backend.mixins import VisitProcessMixin, VisitProcessTemplateView
import backend.email
import datetime
import os
import json


class Process(VisitProcessTemplateView):
    template_name = "legacy/process.html"

    def get_context_data(self, **kw):
        ctx = super(Process, self).get_context_data(**kw)

        # Process form ASAP, so we compute the rest with updated values
        am = self.visitor.am_or_none if self.visitor else None

        log = list(self.process.log.order_by("logdate", "progress"))
        if log:
            ctx["started"] = log[0].logdate
            ctx["last_change"] = log[-1].logdate
        else:
            ctx["started"] = datetime.datetime(1970, 1, 1, 0, 0, 0)
            ctx["last_change"] = datetime.datetime(1970, 1, 1, 0, 0, 0)

        if am:
            ctx["log"] = log
        else:
            # Summarise log for privacy
            distilled_log = []
            last_progress = None
            for l in log:
                if last_progress != l.progress:
                    distilled_log.append(dict(
                        progress=l.progress,
                        changed_by=l.changed_by,
                        logdate=l.logdate,
                    ))
                    last_progress = l.progress
            ctx["log"] = distilled_log

        # Mailbox statistics
        # TODO: move saving per-process stats into a JSON field in Process
        try:
            with open(os.path.join(settings.DATA_DIR, 'mbox_stats.json'), "rt") as infd:
                stats = json.load(infd)
        except OSError:
            stats = {}

        stats = stats.get("process", {})
        stats = stats.get(self.process.lookup_key, {})
        if stats:
            stats["date_first_py"] = datetime.datetime.fromtimestamp(stats["date_first"])
            stats["date_last_py"] = datetime.datetime.fromtimestamp(stats["date_last"])
            if "median" not in stats or stats["median"] is None:
                stats["median_py"] = None
            else:
                stats["median_py"] = datetime.timedelta(seconds=stats["median"])
                stats["median_hours"] = stats["median_py"].seconds // 3600
        ctx["mbox_stats"] = stats

        # Key information for active processes
        if self.process.is_active and self.process.person.fpr:
            from keyring.models import Key
            try:
                key = Key.objects.get_or_download(self.process.person.fpr)
            except RuntimeError as e:
                key = None
                key_error = str(e)
            if key is not None:
                keycheck = key.keycheck()
                uids = []
                for ku in keycheck.uids:
                    uids.append({
                        "name": ku.uid.name.replace("@", ", "),
                        "remarks": " ".join(sorted(ku.errors)) if ku.errors else "ok",
                        "sigs_ok": len(ku.sigs_ok),
                        "sigs_no_key": len(ku.sigs_no_key),
                        "sigs_bad": len(ku.sigs_bad)
                    })

                ctx["keycheck"] = {
                    "main": {
                        "remarks": " ".join(sorted(keycheck.errors)) if keycheck.errors else "ok",
                    },
                    "uids": uids,
                    "updated": key.check_sigs_updated,
                }
            else:
                ctx["keycheck"] = {
                    "main": {
                        "remarks": key_error
                    }
                }

        return ctx


class MailArchive(VisitProcessMixin, View):
    require_visit_perms = "view_mbox"

    def get(self, request, key, *args, **kw):
        fname = self.process.mailbox_file
        if fname is None:
            raise http.Http404

        user_fname = "%s.mbox" % (self.process.person.uid or self.process.person.email)

        res = http.HttpResponse(content_type="application/octet-stream")
        res["Content-Disposition"] = "attachment; filename=%s.gz" % user_fname

        # Compress the mailbox and pass it to the request
        from gzip import GzipFile
        import os.path
        import shutil
        # The last mtime argument seems to only be supported in python 2.7
        outfd = GzipFile(user_fname, "wb", 9, res) #, os.path.getmtime(fname))
        try:
            with open(fname, "rb") as infd:
                shutil.copyfileobj(infd, outfd)
        finally:
            outfd.close()
        return res


class DisplayMailArchive(VisitProcessMixin, TemplateView):
    template_name = "process/display-mail-archive.html"
    require_visit_perms = "view_mbox"

    def get_context_data(self, **kw):
        ctx = super(DisplayMailArchive, self).get_context_data(**kw)

        fname = self.process.mailbox_file
        if fname is None:
            raise http.Http404

        ctx["mails"] = backend.email.get_mbox_as_dicts(fname)
        ctx["class"] = "clickable"
        return ctx
