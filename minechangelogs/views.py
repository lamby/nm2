from django.utils.translation import ugettext as _
from django import http, template, forms
from django.conf import settings
from django.views.generic.edit import FormView
from django.core.exceptions import PermissionDenied
import backend.models as bmodels
import minechangelogs.models as mmodels
from backend.mixins import VisitorMixin
import datetime


class MinechangelogsForm(forms.Form):
    query = forms.CharField(
        required=True,
        label=_("Query"),
        help_text=_("Enter one keyword per line. Changelog entries to be shown must match at least one keyword. You often need to tweak the keywords to improve the quality of results. Note that keyword matching is case-sensitive."),
        widget=forms.Textarea(attrs=dict(rows=5, cols=40))
    )
    download = forms.BooleanField(
        required=False,
        label=_("Download"),
        help_text=_("Activate this field to download the changelog instead of displaying it"),
    )


class MineChangelogs(VisitorMixin, FormView):
    template_name = "minechangelogs/minechangelogs.html"
    form_class = MinechangelogsForm

    def check_permissions(self):
        super(MineChangelogs, self).check_permissions()
        if self.visitor is None:
            raise PermissionDenied

    def load_objects(self):
        super(MineChangelogs, self).load_objects()
        self.key = self.kwargs.get("key", None)
        if self.key:
            self.person = bmodels.Person.lookup_or_404(self.key)
        else:
            self.person = None

    def get_initial(self):
        res = super(MineChangelogs, self).get_initial()
        if not self.person:
            return res

        query = [
            self.person.fullname,
            self.person.email,
        ]
        if self.person.cn and self.person.mn and self.person.sn:
            # some people don't use their middle names in changelogs
            query.append("{} {}".format(self.person.cn, self.person.sn))
        if self.person.uid:
            query.append(self.person.uid)
        return {"query": "\n".join(query)}

    def get_context_data(self, **kw):
        ctx = super(MineChangelogs, self).get_context_data(**kw)
        info = mmodels.info()
        info["max_ts"] = datetime.datetime.fromtimestamp(info["max_ts"])
        info["last_indexed"] = datetime.datetime.fromtimestamp(info["last_indexed"])
        ctx.update(
            info=info,
            person=self.person,
        )
        return ctx

    def form_valid(self, form):
        query = form.cleaned_data["query"]
        keywords = [x.strip() for x in query.split("\n")]
        entries = mmodels.query(keywords)
        if form.cleaned_data["download"]:
            def send_entries():
                for e in entries:
                    yield e
                    yield "\n\n"
            res = http.HttpResponse(send_entries(), content_type="text/plain")
            if self.person:
                res["Content-Disposition"] = 'attachment; filename=changelogs-%s.txt' % self.person.lookup_key
            else:
                res["Content-Disposition"] = 'attachment; filename=changelogs.txt'
            return res

        entries = list(entries)
        return self.render_to_response(self.get_context_data(
            form=form,
            entries=entries,
            keywords=keywords))
