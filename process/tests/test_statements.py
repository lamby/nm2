from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin
import process.models as pmodels
from unittest.mock import patch
from .common import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text,
                     test_fingerprint2, test_fpr2_signed_valid_text)


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
        url = reverse("process_statement_create", args=[self.processes.app.pk, req_type])
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            client = self.make_test_client(self.visitor)
            response = client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(pmodels.Statement.objects.count(), 0)

            # Post a signature done with the wrong key
            response = client.post(url, data={"statement": test_fpr2_signed_valid_text})
            self.assertEqual(response.status_code, 200)
            self.assertFormErrorMatches(response, "form", "statement", "NO_PUBKEY")
            self.assertEqual(pmodels.Statement.objects.count(), 0)

            # Post an invalid signature
            text = test_fpr1_signed_valid_text.replace("I agree", "I do not agree")
            response = client.post(url, data={"statement": text})
            self.assertEqual(response.status_code, 200)
            self.assertFormErrorMatches(response, "form", "statement", "BADSIG")
            self.assertEqual(pmodels.Statement.objects.count(), 0)

            # Post a valid signature
            response = client.post(url, data={"statement": test_fpr1_signed_valid_text})
            req = self.processes.app.requirements.get(type=req_type)
            self.assertRedirectMatches(response, req.get_absolute_url())
            self.assertEqual(pmodels.Statement.objects.count(), 1)
            st = pmodels.Statement.objects.get(requirement=req)
            self.assertEqual(st.requirement, req)
            self.assertEqual(st.fpr, self.fingerprints.visitor)
            self.assertEqual(st.statement, test_fpr1_signed_valid_text)
            self.assertEqual(st.uploaded_by, self.visitor)
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

    def test_encoding(self):
        # Test with Ondřej Nový's key which has non-ascii characters
        bmodels.Fingerprint.objects.create(person=self.persons.app, fpr="3D983C52EB85980C46A56090357312559D1E064B", is_active=True, audit_skip=True)
        statement = """
-----BEGIN PGP SIGNED MESSAGE-----
Hash: SHA512

Changed message, with wrong signature
-----BEGIN PGP SIGNATURE-----
Comment: GPGTools - https://gpgtools.org

iQIbBAEBCgAGBQJXU0eVAAoJEDVzElWdHgZLSsYP90ZNjvyIY63BTQv5tvRutF/V
sJ3eCIp2GCQ5AiQngv6dP0VMMN4f7bzTnjX4HpLOkgDftmtXm2LPyANkW2YXL1q0
A7WjkAUHlpnlGeGfkjfu58v++rVgVmORMTL1CRCuCWT/in4D3dBJJ6PUYR9W5S98
xnxmKfw+Gn9VJVl6I133k1wTEYfK2JY5o4aCQKcXiVZlFsE9CwatmoXhIJwIIV/Z
jDEMO74vURPqX1yesxIEBs7P97j6jiEgRqYkHmwqr+/FA524cYkjhA3vX7MG124N
nZt+8BREMJNzoCbSI2Nl/gQxTMEcyZtIOi8yKZzq5QmeT5ChdnPGVJhxXIFsNFUc
LR8goiONvIxATE2i5M+yPQvohiUlozwu/2s+zA9csjaya+IatcqMDTbkXxfUW7e7
wTiSv5IKwfuMb2JFhekElvJW5yRD3g+tEctB5eWGycTnUdtYBhdmkNZX2w2vnfly
Q+LDTtLH6MTPlkXb3+Vz0oy0sfZFhWou0p84L+SAMZf00083MaXJJbuUyRpbqJSm
lr1zsMVtcsW6vWCY2TIFV8krZk0v1A52CQFYm/9BC5sAFcFA6r5rtgQ56TVaW95b
wbMM0zN66Q7TlCJq4Wf34+9ZyQEs5IPk6QyyjnjQ6uPYExgfF3WrOsfjJSTupZLH
v85pPGXRppmFCX/Pk+U=
=eWfI
-----END PGP SIGNATURE-----
"""
        url = reverse("process_statement_create", args=[self.processes.app.pk, "intent"])
        client = self.make_test_client(self.persons.app)
        # Post an invalid signature
        response = client.post(url, data={"statement": statement})
        self.assertEqual(response.status_code, 200)
        self.assertFormErrorMatches(response, "form", "statement", "Ondřej Nový <novy@ondrej.org>")
        self.assertEqual(pmodels.Statement.objects.count(), 0)

    def test_encoding1(self):
        bmodels.Fingerprint.objects.create(person=self.persons.app, fpr="3D983C52EB85980C46A56090357312559D1E064B", is_active=True, audit_skip=True)
        statement = "\xe8"
        url = reverse("process_statement_create", args=[self.processes.app.pk, "intent"])
        client = self.make_test_client(self.persons.app)
        # Post an invalid signature
        response = client.post(url, data={"statement": statement})
        self.assertEqual(response.status_code, 200)
        self.assertFormErrorMatches(response, "form", "statement", "OpenPGP MIME data not found")
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
