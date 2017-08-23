from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from django.core import mail
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin
import process.models as pmodels
from unittest.mock import patch
from process.unittest import (ProcessFixtureMixin,
                     test_fingerprint1, test_fpr1_signed_valid_text,
                     test_fingerprint2, test_fpr2_signed_valid_text)
from process import ops as pops


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

    def test_basic_op(self):
        req = self.processes.app.requirements.get(type="intent")
        o = pops.ProcessStatementAdd(audit_author=self.persons.fd, requirement=req, statement="test statement")
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Added a new statement")
            self.assertEqual(o.requirement, req)
            self.assertEqual(o.statement, "test statement")

    def test_op(self):
        mail.outbox = []
        proc = self.processes.app
        req = self.processes.app.requirements.get(type="intent")
        o = pops.ProcessStatementAdd(audit_author=self.visitor, requirement=req, statement="test statement")
        o.execute()

        req.refresh_from_db()
        self.assertEqual(pmodels.Statement.objects.count(), 1)
        st = req.statements.get()
        self.assertEqual(st.fpr, self.fingerprints.visitor)
        self.assertEqual(st.statement, "test statement")
        self.assertEqual(st.uploaded_by, self.visitor)
        self.assertEqual(st.uploaded_time, o.audit_time)

        self.assertEqual(len(mail.outbox), 1)
        m = mail.outbox[0]
        self.assertEqual(mail.outbox[0].to, ["debian-newmaint@lists.debian.org"])
        self.assertCountEqual(mail.outbox[0].cc, ["{} <{}>".format(proc.person.fullname, proc.person.email), proc.archive_email])
        self.assertEqual(mail.outbox[0].subject, "App: Declaration of intent")
        self.assertIn("test statement", mail.outbox[0].body)
        self.assertIn(self.processes.app.get_absolute_url(), mail.outbox[0].body)

    @classmethod
    def __add_extra_tests__(cls):
        for req_type in ("intent", "sc_dmup", "advocate", "am_ok"):
            cls._add_method(cls._test_create_forbidden, req_type, set())
            cls._add_method(cls._test_create_success, req_type, { "edit_statements" })

    def _test_create_success(self, req_type, visit_perms):
        url = reverse("process_statement_create", args=[self.processes.app.pk, req_type])
        client = self.make_test_client(self.visitor)
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            with self.collect_operations() as ops:
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(ops), 0)

                # Post a signature done with the wrong key
                response = client.post(url, data={"statement": test_fpr2_signed_valid_text})
                self.assertEqual(response.status_code, 200)
                self.assertFormErrorMatches(response, "form", "statement", "NO_PUBKEY")
                self.assertEqual(len(ops), 0)

                # Post an invalid signature
                text = test_fpr1_signed_valid_text.replace("I agree", "I do not agree")
                response = client.post(url, data={"statement": text})
                self.assertEqual(response.status_code, 200)
                self.assertFormErrorMatches(response, "form", "statement", "BADSIG")
                self.assertEqual(len(ops), 0)

                # Post a valid signature
                response = client.post(url, data={"statement": test_fpr1_signed_valid_text})
                req = self.processes.app.requirements.get(type=req_type)
                self.assertRedirectMatches(response, req.get_absolute_url())
                self.assertEqual(len(ops), 1)

        op = ops[0]
        self.assertEqual(op.audit_author, self.visitor)
        self.assertEqual(op.audit_notes, "Added a new statement")
        self.assertEqual(op.requirement, self.processes.app.requirements.get(type=req_type))
        self.assertEqual(op.statement, test_fpr1_signed_valid_text.strip())

    def _test_create_forbidden(self, req_type, visit_perms=set()):
        client = self.make_test_client(self.visitor)
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            with self.collect_operations() as ops:
                response = client.get(reverse("process_statement_create", args=[self.processes.app.pk, req_type]))
                self.assertPermissionDenied(response)
                self.assertEqual(len(ops), 0)

                response = client.post(reverse("process_statement_create", args=[self.processes.app.pk, req_type]), data={"statement": test_fpr1_signed_valid_text})
                self.assertPermissionDenied(response)
                self.assertEqual(len(ops), 0)

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
        with self.collect_operations() as ops:
            response = client.post(url, data={"statement": statement})
            self.assertEqual(response.status_code, 200)
            self.assertFormErrorMatches(response, "form", "statement", "Ondřej Nový <novy@ondrej.org>")
            self.assertEqual(len(ops), 0)

    def test_encoding1(self):
        bmodels.Fingerprint.objects.create(person=self.persons.app, fpr="3D983C52EB85980C46A56090357312559D1E064B", is_active=True, audit_skip=True)
        statement = "\xe8"
        url = reverse("process_statement_create", args=[self.processes.app.pk, "intent"])
        client = self.make_test_client(self.persons.app)
        # Post an invalid signature
        with self.collect_operations() as ops:
            response = client.post(url, data={"statement": statement})
            self.assertEqual(response.status_code, 200)
            self.assertFormErrorMatches(response, "form", "statement", "OpenPGP MIME data not found")
            self.assertEqual(len(ops), 0)

    def test_description(self):
        self.fingerprints.create("dam", person=self.persons.dam, fpr=test_fingerprint2, is_active=True, audit_skip=True)
        client = self.make_test_client("dam")
        url = reverse("process_statement_create", args=[self.processes.app.pk, "intent"])
        with self.collect_operations() as ops:
            response = client.get(url)
            self.assertContains(response, 'The statement will be sent to <a href="https://lists.debian.org/debian-newmaint">debian-newmaint</a> as <tt>Dam')
            self.assertEqual(len(ops), 0)

        with self.collect_operations() as ops:
            response = client.post(reverse("process_statement_create", args=[self.processes.app.pk, "intent"]), data={"statement": test_fpr2_signed_valid_text})
            self.assertRedirectMatches(response, self.processes.app.requirements.get(type="intent").get_absolute_url())
            self.assertEqual(len(ops), 1)

        op = ops[0]
        self.assertEqual(op.audit_author, self.persons.dam)
        self.assertEqual(op.audit_notes, "Added a new statement")
        self.assertEqual(op.requirement, self.processes.app.requirements.get(type="intent"))
        self.assertEqual(op.statement, test_fpr2_signed_valid_text.strip())

        self.processes.app.applying_for = const.STATUS_EMERITUS_DD
        self.processes.app.save()
        with self.collect_operations() as ops:
            response = client.get(url)
            self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)

        self.processes.app.applying_for = const.STATUS_REMOVED_DD
        self.processes.app.save()
        with self.collect_operations() as ops:
            response = client.get(url)
            self.assertPermissionDenied(response)
            self.assertEqual(len(ops), 0)


class TestProcessStatementDelete(ProcessFixtureMixin, TestCase):
    def test_basic_op(self):
        req = self.processes.app.requirements.get(type="intent")
        st = pmodels.Statement.objects.create(requirement=req, statement="test", uploaded_by=self.persons.fd, uploaded_time=now())

        o = pops.ProcessStatementRemove(audit_author=self.persons.fd, statement=st)
        @self.assertOperationSerializes(o)
        def _(o):
            self.assertEqual(o.audit_author, self.persons.fd)
            self.assertEqual(o.audit_notes, "Removed a statement")
            self.assertEqual(o.statement, st)

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

    def test_op(self):
        mail.outbox = []

        o = pops.ProcessStatementRemove(audit_author=self.persons.fd, statement=self.statements.intent)
        o.execute()
        self.assertFalse(pmodels.Statement.objects.filter(pk=self.statements.intent.pk).exists())

        o = pops.ProcessStatementRemove(audit_author=self.persons.fd, statement=self.statements.sc_dmup)
        o.execute()
        self.assertFalse(pmodels.Statement.objects.filter(pk=self.statements.sc_dmup.pk).exists())

        o = pops.ProcessStatementRemove(audit_author=self.persons.fd, statement=self.statements.advocate)
        o.execute()
        self.assertFalse(pmodels.Statement.objects.filter(pk=self.statements.advocate.pk).exists())

        o = pops.ProcessStatementRemove(audit_author=self.persons.fd, statement=self.statements.am_ok)
        o.execute()
        self.assertFalse(pmodels.Statement.objects.filter(pk=self.statements.am_ok.pk).exists())

        self.assertEqual(len(mail.outbox), 0)

        # Notice that the statements were removed, so tearDownClass does not fail trying to remove them again
        self.statements.refresh()

    @classmethod
    def __add_extra_tests__(cls):
        for req_type in ("intent", "sc_dmup", "advocate", "am_ok"):
            cls._add_method(cls._test_delete_forbidden, req_type, visit_perms=set())
            cls._add_method(cls._test_delete_success, req_type, visit_perms={"edit_statements"})

    def _test_delete_success(self, req_type, visit_perms):
        client = self.make_test_client(self.visitor)
        statement = self.statements[req_type]
        url = reverse("process_statement_delete", args=[self.processes.app.pk, req_type, statement.pk])
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            with self.collect_operations() as ops:
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(len(ops), 0)

                response = client.post(url)
                self.assertRedirectMatches(response, statement.requirement.get_absolute_url())
                self.assertEqual(len(ops), 1)

        op = ops[0]
        self.assertEqual(op.audit_author, client.visitor)
        self.assertEqual(op.audit_notes, "Removed a statement")
        self.assertEqual(op.statement, statement)

    def _test_delete_forbidden(self, req_type, visit_perms=set()):
        client = self.make_test_client(self.visitor)
        statement = self.statements[req_type]
        url = reverse("process_statement_delete", args=[self.processes.app.pk, req_type, statement.pk])
        with patch.object(pmodels.Requirement, "permissions_of", return_value=visit_perms):
            with self.collect_operations() as ops:
                response = client.get(url)
                self.assertPermissionDenied(response)
                self.assertEqual(len(ops), 0)

                response = client.post(url)
                self.assertPermissionDenied(response)
                self.assertEqual(len(ops), 0)


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
        self.assertEqual(response.content.decode("utf8"), test_fpr1_signed_valid_text)
