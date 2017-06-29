# coding: utf-8




from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin, ExpectedSets, TestSet, PageElements
import process.models as pmodels
from mock import patch
import tempfile
import mailbox

class TestStats(PersonFixtureMixin, TestCase):
    def test_get(self):
        client = self.make_test_client(None)
        response = client.get(reverse("public_stats"))
        self.assertEqual(response.status_code, 200)
        response = client.get(reverse("public_stats"), data={"json": True, "days": 30})
        self.assertEqual(response.status_code, 200)
        response = client.get(reverse("public_stats_latest"), data={"json": True, "days": 30})
        self.assertEqual(response.status_code, 200)
        response = client.get(reverse("public_stats_graph"), data={"json": True, "days": 30})
        self.assertEqual(response.status_code, 200)
