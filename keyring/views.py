# coding: utf-8
# nm.debian.org keyring-related views
#
# Copyright (C) 2013  Enrico Zini <enrico@debian.org>
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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from . import models as kmodels
from backend import models as bmodels
from django import http
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.utils.timezone import utc, now
import json
import datetime
import time

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

def keycheck(request, fpr):
    """
    Web-based keycheck.sh implementation
    """
    if request.method != "GET":
        return http.HttpResponseForbidden("Only GET request is allowed here")

    try:
        key = kmodels.Key.objects.get_or_download(fpr)

        # Do not redownload more than once every 5 minutes
        if key.key_updated < now() - datetime.timedelta(minutes=5):
            key.update_key()

        key.update_check_sigs()

        res = {}
        kc = key.keycheck()
        uids = []
        k = {
            "fpr": kc.key.fpr,
            "errors": sorted(kc.errors),
            "uids": uids
        }
        res[kc.key.fpr] = k

        for ku in kc.uids:
            uids.append({
                "name": ku.uid.name,
                "errors": sorted(ku.errors),
                "sigs_ok": [x[9] for x in ku.sigs_ok],
                "sigs_no_key": len(ku.sigs_no_key),
                "sigs_bad": len(ku.sigs_bad)
            })

        try:
            bf = bmodels.Fingerprint.objects.get(fpr=fpr)
            k["person_id"] = bf.person_id
            k["person"] = bf.person.fullname
        except ObjectDoesNotExist:
            k["person_id"] = None
            k["person"] = None
        except MultipleObjectsReturned:
            # Should never happen because of unique constraints
            raise

        return json_response(k)
    except RuntimeError as e:
        return json_response({
            "error": unicode(e)
        }, status_code=500)
