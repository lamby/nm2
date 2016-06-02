# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from django.core.urlresolvers import reverse
from django.utils.timezone import now
from backend import const
from mock import patch
from .common import ProcessFixtureMixin, get_all_process_types
import process.models as pmodels
import datetime
import uuid

# TODO:  list log entries, check confidentiality filter


class TestLog(ProcessFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestLog, cls).setUpClass()
        cls.orig_ts = datetime.datetime(2015, 1, 1, 0, 0, 0)
#        cls.proc_states = {
#            "normal": { "frozen_by": None, "frozen_time": None, "approved_by": None, "approved_time": None, "closed": None },
#            "frozen": { "frozen_by": cls.persons.fd, "frozen_time": ts, "approved_by": None, "approved_time": None, "closed": None },
#            "approved": { "frozen_by": cls.persons.fd, "frozen_time": ts, "approved_by": cls.persons.dam, "approved_time": ts, "closed": None },
#            "done": { "frozen_by": cls.persons.fd, "frozen_time": ts, "approved_by": cls.persons.dam, "approved_time": ts, "closed": ts },
#            "cancelled": { "frozen_by": None, "frozen_time": None, "approved_by": None, "approved_time": None, "closed": ts },
#        }

        # Create a process with an AM
        cls.persons.create("app", status=const.STATUS_DM)
        cls.processes.create("app", person=cls.persons.app, applying_for=const.STATUS_DD_U)
        cls.req_intent = pmodels.Requirement.objects.get(process=cls.processes.app, type="intent")
        cls.persons.create("am", status="dd_nu")
        cls.ams.create("am", person=cls.persons.am)
        cls.req_am_ok = pmodels.Requirement.objects.get(process=cls.processes.app, type="am_ok")

        cls.processes.app.frozen_by = cls.persons.fd
        cls.processes.app.frozen_time = cls.orig_ts
        cls.processes.app.approved_by = cls.persons.fd
        cls.processes.app.approved_time = cls.orig_ts
        cls.processes.app.closed = cls.orig_ts
        cls.processes.app.save()

        cls.url = reverse("process_add_log", args=[cls.processes.app.pk])

        cls.visitor = None

        #    if cls.am_assigned:
        #        pmodels.AMAssignment.objects.create(process=cls.processes.app, am=cls.ams.am, assigned_by=cls.persons["fd"], assigned_time=ts)
        #else:
        #    cls.req_am_ok = None

#    @classmethod
#    def __add_extra_tests__(cls):
#        visitors = [None, "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "activeam", "fd", "dam", "app", "am"]
#        for visitor in visitors:
#            cls._add_method(cls._test_add_log, visitor, "log_private", "add_log")
#            cls._add_method(cls._test_add_log, visitor, "log_public", "add_log")
#            cls._add_method(cls._test_add_log, visitor, "req_approve", "req_approve")
#            cls._add_method(cls._test_add_log, visitor, "req_unapprove", "req_unapprove")
#            cls._add_method(cls._test_add_log, visitor, "proc_freeze", "proc_freeze")
#            cls._add_method(cls._test_add_log, visitor, "proc_unfreeze", "proc_unfreeze")
#            cls._add_method(cls._test_add_log, visitor, "proc_approve", "proc_approve")

    def get_new_log(self, process, logtext):
        entry = pmodels.Log.objects.get(process=process, logtext=logtext)
        self.assertEqual(entry.changed_by, self.visitor)
        self.assertEqual(entry.process, self.processes.app)
        return entry

    def assertFailed(self, response, logtext):
        self.assertPermissionDenied(response)
        self.assertFalse(pmodels.Log.objects.filter(process=self.processes.app, logtext=logtext).exists())
        self.processes.app.refresh_from_db()
        self.assertEqual(self.processes.app.frozen_by, self.persons.fd)
        self.assertEqual(self.processes.app.frozen_time, self.orig_ts)
        self.assertEqual(self.processes.app.approved_by, self.persons.fd)
        self.assertEqual(self.processes.app.approved_time, self.orig_ts)
        self.assertEqual(self.processes.app.closed, self.orig_ts)

    def test_process_log_private(self):
        client = self.make_test_client(self.visitor)
        logtext = uuid.uuid4().hex

        with patch.object(pmodels.Process, "permissions_of", return_value=set()):
            response = client.post(self.url, data={"logtext": logtext, "add_action": "log_private"})
            self.assertFailed(response, logtext)

        with patch.object(pmodels.Process, "permissions_of", return_value=set(["add_log"])):
            response = client.post(self.url, data={"logtext": logtext, "add_action": "log_private"})
            self.assertRedirectMatches(response, self.processes.app.get_absolute_url())
            entry = self.get_new_log(self.processes.app, logtext)
            self.assertIsNone(entry.requirement)
            self.assertFalse(entry.is_public)
            self.assertEqual(entry.action, "")


#    def _test_add_log(self, visitor, action, perm):
#        if visitor == "am" and not self.has_am: return
#        client = self.make_test_client(visitor)
#        self._test_post(client, self.processes.app, action, perm)
#        self._test_post(client, self.req_intent, action, perm, req_state={})
#        if self.req_am_ok: self._test_post(client, self.req_am_ok, action, perm, req_state={})
#
#    def _test_post(self, client, target, action, perm, req_state=None):
#        import uuid
#        postdata = {
#            "logtext": uuid.uuid4().hex,
#            "add_action": action,
#        }
#        if req_state is not None:
#            process = target.process
#            requirement = target
#            postdata["req_type"] = target.type
#            # Set the Requirement to the known initial state
#            for k, v in req_state.items():
#                setattr(requirement, k, v)
#            requirement.save()
#        else:
#            process = target
#            requirement = None
#
#        visit_perms = target.permissions_of(client.visitor)
#        response = client.post(reverse("process_add_log", args=[process.pk]), data=postdata)
#        if perm in visit_perms:
#            self.assertRedirectMatches(response, target.get_absolute_url())
#            entry = pmodels.Log.objects.get(process=process, logtext=postdata["logtext"])
#            self.assertEqual(entry.changed_by, client.visitor)
#            self.assertEqual(entry.process, process)
#            self.assertEqual(entry.requirement, requirement)
#            self.assertEqual(entry.is_public, action != "log_private")
#            self.assertEqual(entry.action, action if action not in ("log_private", "log_public") else "")
#        else:
#            self.assertPermissionDenied(response)
#            self.assertFalse(pmodels.Log.objects.filter(process=process, logtext=postdata["logtext"]).exists())


# Generate the rest of the file with ./manage.py test_make_process_test_log

#class TestAddLog(ProcessFixtureMixin, TestCase):
#    @classmethod
#    def __add_extra_tests__(cls):
#        for src, tgt in get_all_process_types():
#            want_am = "am_ok" in pmodels.Process.objects.compute_requirements(src, tgt)
#            visitors = [None, "pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "activeam", "fd", "dam", "app"]
#            if want_am: visitors.append("am")
#            for visitor in visitors:
#                if want_am:
#                    cls._add_method(cls._test_add_log, src, tgt, visitor, am="dd_nu")
#                else:
#                    cls._add_method(cls._test_add_log, src, tgt, visitor)
#
#    def _test_post(self, client, target, proc_state, action, permission, req_state=None):
#        import uuid
#        postdata = {
#            "logtext": uuid.uuid4().hex,
#            "add_action": action,
#        }
#        if req_state is not None:
#            process = target.process
#            requirement = target
#            postdata["req_type"] = target.type
#            # Set the Requirement to the known initial state
#            for k, v in req_state.items():
#                setattr(requirement, k, v)
#            requirement.save()
#        else:
#            process = target
#            requirement = None
#
#        # Set the Process to the known initial state
#        for k, v in proc_state.items():
#            setattr(process, k, v)
#        process.save()
#
#        visit_perms = target.permissions_of(client.visitor)
#        response = client.post(reverse("process_add_log", args=[process.pk]), data=postdata)
#        if permission in visit_perms:
#            self.assertRedirectMatches(response, target.get_absolute_url())
#            entry = pmodels.Log.objects.get(process=process, logtext=postdata["logtext"])
#            self.assertEqual(entry.changed_by, client.visitor)
#            self.assertEqual(entry.process, process)
#            self.assertEqual(entry.requirement, requirement)
#            self.assertEqual(entry.is_public, action != "log_private")
#            self.assertEqual(entry.action, action if action not in ("log_private", "log_public") else "")
#        else:
#            self.assertPermissionDenied(response)
#            self.assertFalse(pmodels.Log.objects.filter(process=process, logtext=postdata["logtext"]).exists())
#
#    def _test_all_actions(self, client, target, proc_state, req_state=None):
#        self._test_post(client, target, proc_state, "log_private", "add_log", req_state=req_state)
#        self._test_post(client, target, proc_state, "log_public", "add_log", req_state=req_state)
#        self._test_post(client, target, proc_state, "req_approve", "req_approve", req_state=req_state)
#        self._test_post(client, target, proc_state, "req_unapprove", "req_unapprove", req_state=req_state)
#        self._test_post(client, target, proc_state, "proc_freeze", "proc_freeze", req_state=req_state)
#        self._test_post(client, target, proc_state, "proc_unfreeze", "proc_unfreeze", req_state=req_state)
#        self._test_post(client, target, proc_state, "proc_approve", "proc_approve", req_state=req_state)
#        self._test_post(client, target, proc_state, "proc_unapprove", "proc_unapprove", req_state=req_state)
#
#    def _test_requirement_log(self, client, proc_state, req):
#        req_state = {"approved_by": None, "approved_time": None}
#        self._test_all_actions(client, req, proc_state, req_state=req_state) # requirement unapproved
#        req_state = {"approved_by": self.persons.fd, "approved_time": now()}
#        self._test_all_actions(client, req, proc_state, req_state=req_state) # requirement approved
#
#    def _test_requirement_log_intent(self, client, proc_state):
#        req = pmodels.Requirement.objects.get(process=self.processes.app, type="intent")
#        self._test_requirement_log(client, proc_state, req) # intent requirement
#
#    def _test_requirement_log_am_ok(self, client, proc_state):
#        req = pmodels.Requirement.objects.get(process=self.processes.app, type="am_ok")
#        self._test_requirement_log(client, proc_state, req) # am_ok requirement
#
#    def _test_all_requirements(self, visitor, proc_state):
#        client = self.make_test_client(visitor)
#        self._test_all_actions(client, self.processes.app, proc_state)
#        self._test_requirement_log_intent(client, proc_state)
#        if "am" in self.persons:
#            self._test_requirement_log_am_ok(client, proc_state)
#
#    def _test_all_process_states(self, visitor):
#        # Normal
#        state = { "frozen_by": None, "frozen_time": None, "approved_by": None, "approved_time": None, "closed": None }
#        self._test_all_requirements(visitor, state) # process being edited
#
#        # Frozen
#        state = { "frozen_by": self.persons.fd, "frozen_time": now(), "approved_by": None, "approved_time": None, "closed": None }
#        self._test_all_requirements(visitor, state) # process frozen for review
#
#        # Approved
#        state = { "frozen_by": self.persons.fd, "frozen_time": now(), "approved_by": self.persons.dam, "approved_time": now(), "closed": None }
#        self._test_all_requirements(visitor, state) # process approved
#
#        # Closed
#        state = { "frozen_by": self.persons.fd, "frozen_time": now(), "approved_by": self.persons.dam, "approved_time": now(), "closed": now() }
#        self._test_all_requirements(visitor, state) # process closed
#
#        # Closed without completion
#        state = { "frozen_by": None, "frozen_time": None, "approved_by": None, "approved_time": None, "closed": now() }
#        self._test_all_requirements(visitor, state) # process closed incomplete
#
#    def _test_add_log(self, src, tgt, visitor, am=None):
#        # Create process
#        self.persons.create("app", status=src)
#        self.processes.create("app", person=self.persons.app, applying_for=tgt, fd_comment="test")
#        if am is not None:
#            self.persons.create("am", status=am)
#            self.ams.create("am", person=self.persons.am)
#
#        self._test_all_process_states(visitor)
#
#        # Assign am and repeat
#        if am:
#            pmodels.AMAssignment.objects.create(process=self.processes.app, am=self.ams.am, assigned_by=self.persons["fd"], assigned_time=now())
#            self._test_all_process_states(visitor)


