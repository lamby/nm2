# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin
import process.models as pmodels
from mock import patch
from .common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text)


class TestProcessStatementCreate(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessStatementCreate, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.amassignments.create("am", process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons["fd"], assigned_time=now())

        cls.visitor = cls.persons.dc
        cls.fingerprints.create("visitor", person=cls.visitor, fpr=test_fingerprint1, is_active=True, audit_skip=True)

    @classmethod
    def __add_extra_tests__(cls):
        for req_type in ("intent", "sc_dmup", "advocate", "am_ok"):
            cls._add_method(cls._test_create_forbidden, req_type, set())
            cls._add_method(cls._test_create_success, req_type, { "edit_statements" })

    def _test_create_success(self, req_type, visit_perms):
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            client = self.make_test_client(self.visitor)
            response = client.get(reverse("process_statement_create", args=[self.processes.app.pk, req_type]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(pmodels.Statement.objects.count(), 0)

            response = client.post(reverse("process_statement_create", args=[self.processes.app.pk, req_type]), data={"statement": test_fpr1_signed_valid_text})
            req = self.processes.app.requirements.get(type=req_type)
            self.assertRedirectMatches(response, req.get_absolute_url())
            self.assertEqual(pmodels.Statement.objects.count(), 1)
            st = pmodels.Statement.objects.get(requirement=req)
            self.assertEquals(st.requirement, req)
            self.assertEquals(st.fpr, self.fingerprints.visitor)
            self.assertEquals(st.statement, test_fpr1_signed_valid_text)
            self.assertEquals(st.uploaded_by, self.visitor)
            self.assertIsNotNone(st.uploaded_time)

    def _test_create_forbidden(self, req_type, visit_perms=set()):
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            client = self.make_test_client(self.visitor)
            response = client.get(reverse("process_statement_create", args=[self.processes.app.pk, req_type]))
            self.assertPermissionDenied(response)
            self.assertEqual(pmodels.Statement.objects.count(), 0)

            response = client.post(reverse("process_statement_create", args=[self.processes.app.pk, req_type]), data={"statement": test_fpr1_signed_valid_text})
            self.assertPermissionDenied(response)
            self.assertEqual(pmodels.Statement.objects.count(), 0)


class TestProcessStatementDelete(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessStatementDelete, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.amassignments.create("am", process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons["fd"], assigned_time=now())

        cls.visitor = cls.persons.dc
        cls.fingerprints.create("visitor", person=cls.visitor, fpr=test_fingerprint1, is_active=True, audit_skip=True)
        cls.statement_pks = {}
        for req_type in ("intent", "sc_dmup", "advocate", "am_ok"):
            req = cls.processes.app.requirements.get(type=req_type)
            cls.statements.create(req_type, requirement=req, fpr=cls.fingerprints.visitor, statement=test_fpr1_signed_valid_text, uploaded_by=cls.visitor, uploaded_time=now())

    @classmethod
    def __add_extra_tests__(cls):
        for req_type in ("intent", "sc_dmup", "advocate", "am_ok"):
            cls._add_method(cls._test_delete_forbidden, req_type, set())
            cls._add_method(cls._test_delete_success, req_type, { "edit_statements" })

    def _test_delete_success(self, req_type, visit_perms):
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            client = self.make_test_client(self.visitor)
            statement = self.statements[req_type]
            url = reverse("process_statement_delete", args=[self.processes.app.pk, req_type, statement.pk])
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(pmodels.Statement.objects.filter(pk=statement.pk).exists())

            response = client.post(url)
            req = self.processes.app.requirements.get(type=req_type)
            self.assertRedirectMatches(response, req.get_absolute_url())
            self.assertFalse(pmodels.Statement.objects.filter(pk=statement.pk).exists())

    def _test_delete_forbidden(self, req_type, visit_perms=set()):
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            client = self.make_test_client(self.visitor)
            statement = self.statements[req_type]
            url = reverse("process_statement_delete", args=[self.processes.app.pk, req_type, statement.pk])
            response = client.get(url)
            self.assertPermissionDenied(response)
            self.assertTrue(pmodels.Statement.objects.filter(pk=statement.pk).exists())

            response = client.post(url)
            self.assertPermissionDenied(response)
            self.assertTrue(pmodels.Statement.objects.filter(pk=statement.pk).exists())


class TestProcessStatementRaw(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestProcessStatementRaw, cls).setUpClass()
        cls.persons.create("app", status=const.STATUS_DC)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U, fd_comment="test")
        cls.persons.create("am", status=const.STATUS_DD_NU)
        cls.ams.create("am", person=cls.persons.am)
        cls.amassignments.create("am", process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons["fd"], assigned_time=now())

        cls.signer = cls.persons.dc
        cls.fingerprints.create("signer", person=cls.signer, fpr=test_fingerprint1, is_active=True, audit_skip=True)
        cls.statement_pks = {}
        for req_type in ("intent", "sc_dmup", "advocate", "am_ok"):
            req = cls.processes.app.requirements.get(type=req_type)
            cls.statements.create(req_type, requirement=req, fpr=cls.fingerprints.signer, statement=test_fpr1_signed_valid_text, uploaded_by=cls.signer, uploaded_time=now())

    @classmethod
    def __add_extra_tests__(cls):
        for visitor in (None, "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "app", "am", "activeam", "fd", "dam"):
            for req_type in ("intent", "sc_dmup", "advocate", "am_ok"):
                cls._add_method(cls._test_access, visitor, req_type)

    def _test_access(self, visitor, req_type):
        client = self.make_test_client(visitor)
        statement = self.statements[req_type]
        response = client.get(reverse("process_statement_raw", args=[self.processes.app.pk, req_type, statement.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, test_fpr1_signed_valid_text)

# TODO:  url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/create$', views.StatementCreate.as_view(), name="process_statement_create"),
# TODO:  url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/(?P<st>\d+)/delete$', views.StatementDelete.as_view(), name="process_statement_delete"),
# TODO:  url(r'^(?P<pk>\d+)/(?P<type>[^/]+)/statement/(?P<st>\d+)/raw$', views.StatementRaw.as_view(), name="process_statement_raw"),
