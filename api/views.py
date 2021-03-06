from django import http
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext as _
from django.forms.models import model_to_dict
from django.views.generic import View
from django.views.decorators.csrf import csrf_exempt
import backend.models as bmodels
from apikeys.mixins import APIVisitorMixin
from backend import const
import datetime
import json

class Serializer(json.JSONEncoder):
    def default(self, o):
        if hasattr(o, "strftime"):
            return o.strftime("%s")
            #return o.strftime("%Y-%m-%d %H:%M:%S")
        return json.JSONEncoder.default(self, o)

def json_response(val, status_code=200):
    res = http.HttpResponse(content_type="application/json")
    res.status_code = status_code
    json.dump(val, res, cls=Serializer, indent=1)
    return res

def person_to_json(p, **kw):
    res = model_to_dict(p, **kw)
    res["fullname"] = p.fullname
    res["url"] = p.get_absolute_url()
    res["fpr"] = p.fpr
    return res

class People(APIVisitorMixin, View):
    def get(self, request, *args, **kw):
        # Pick what to include in the result based on auth status
        fields = ["cn", "mn", "sn", "uid", "fpr", "status", "status_changed", "created"]
        if self.visitor and self.visitor.is_dd:
            fields.append("email")
            if self.visitor.is_admin:
                fields.append("fd_comment")

        try:
            res = []

            # Build query
            people = bmodels.Person.objects.all()

            for arg in "cn", "mn", "sn", "email", "uid":
                val = request.GET.get(arg, None)
                if val is None: continue
                if val.startswith("/") and val.endswith("/"):
                    args = { arg + "__regex": val.strip("/") }
                else:
                    args = { arg + "__iexact": val }
                people = people.filter(**args)

            val = request.GET.get("fpr", None)
            if val is not None:
                people = people.filter(fprs__fpr__endswith=val)

            val = request.GET.get("status", None)
            if val is not None: people = people.filter(status=val)

            if self.visitor and self.visitor.is_admin:
                val = request.GET.get("fd_comment", "")
                if val: people = people.filter(fd_comment__icontains=val)

            for p in people.order_by("cn", "sn"):
                res.append(person_to_json(p, fields=fields))

            return json_response(dict(r=res))
        except Exception as e:
            #import traceback
            #traceback.print_exc()
            return json_response(dict(e=str(e)), status_code=500)


class Status(APIVisitorMixin, View):
    def _serialize_people(self, people):
        res = {}
        for p in people:
            perms = p.perms
            rp = {
                "status": p.status,
            }
            if "am" in perms: rp["is_am"] = True
            res[p.username] = rp
        return json_response(dict(people=res))

    def get(self, request, *args, **kw):
        q_status = request.GET.get("status", None)
        q_person = request.GET.get("person", None)
        q_all = not any(bool(x) for x in (q_status, q_person))

        # Ensure that we got only one query
        if sum(bool(x) for x in (q_status, q_person)) > 1:
            return http.HttpResponseBadRequest("only one of status, person can be specified")

        # Enforce access restrictions
        if (q_status or q_all) and not self.visitor:
            raise PermissionDenied

        # Get a QuerySet with the people to return
        persons = bmodels.Person.objects.all()
        if q_status:
            persons = persons.filter(status__in=q_status.split(","))
        elif q_person:
            persons = persons.filter(username__in=q_person.split(","))
        elif q_all:
            pass
        else:
            return http.HttpResponseServerError("request cannot be understood")

        return self._serialize_people(persons)

    def post(self, request, *args, **kw):
        names = [str(x) for x in json.loads(request.body.decode("utf8"))]
        persons = bmodels.Person.objects.filter(username__in=names)
        return self._serialize_people(persons)

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super(Status, self).dispatch(*args, **kwargs)


class Whoami(APIVisitorMixin, View):
    """
    Return a JSON with information on the currently logged in user
    """
    def get(self, request, *args, **kw):
        if request.user.is_authenticated:
            data = model_to_dict(self.visitor, fields=["username", "cn", "mn", "sn", "email", "uid", "status", "status_changed"])
            data["fpr"] = self.visitor.fpr
        else:
            data = {}
        res = http.HttpResponse(content_type="application/json")
        json.dump(data, res, indent=1, cls=Serializer)
        return res
