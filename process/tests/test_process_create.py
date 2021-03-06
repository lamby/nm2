from django.test import TestCase
from django.urls import reverse
from backend import const
from .common import ProcessFixtureMixin
import process.models as pmodels


class TestCreate(ProcessFixtureMixin, TestCase):
    @classmethod
    def __add_extra_tests__(cls):
        def ok(visited, target):
            cls._add_method(cls._test_success, visited, visited, target)
            cls._add_method(cls._test_success, "fd", visited, target)
            cls._add_method(cls._test_success, "dam", visited, target)
            for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r"):
                if visitor == visited: continue
                cls._add_method(cls._test_forbidden, visitor, visited, target)

        def dde(visited, target):
            cls._add_method(cls._test_success_dde, visited, visited, target)
            cls._add_method(cls._test_success_dde, "fd", visited, target)
            cls._add_method(cls._test_success_dde, "dam", visited, target)
            for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r"):
                if visitor == visited: continue
                cls._add_method(cls._test_forbidden, visitor, visited, target)

        def no(visited, target):
            cls._add_method(cls._test_invalid, visited, visited, target)
            cls._add_method(cls._test_invalid, "fd", visited, target)
            cls._add_method(cls._test_invalid, "dam", visited, target)
            for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r"):
                if visitor == visited: continue
                cls._add_method(cls._test_forbidden, visitor, visited, target)

        no("dc", "dc")
        ok("dc", "dc_ga")
        ok("dc", "dm")
        no("dc", "dm_ga")
        ok("dc", "dd_u")
        ok("dc", "dd_nu")
        no("dc", "dd_e")

        ok("dc_ga", "dm_ga")
        no("dc_ga", "dm")
        ok("dc_ga", "dd_u")
        ok("dc_ga", "dd_nu")
        no("dc_ga", "dd_e")

        no("dm", "dm")
        ok("dm", "dm_ga")
        ok("dm", "dd_u")
        ok("dm", "dd_nu")
        no("dm", "dd_e")

        no("dm_ga", "dm_ga")
        ok("dm_ga", "dd_u")
        ok("dm_ga", "dd_nu")
        no("dm_ga", "dd_e")

        no("dd_nu", "dd_nu")
        ok("dd_nu", "dd_u")
        dde("dd_nu", "dd_e")

        no("dd_u", "dd_u")
        dde("dd_u", "dd_e")

        no("dd_e", "dd_e")
        ok("dd_e", "dd_u")
        ok("dd_e", "dd_nu")

        no("dd_r", "dd_r")
        ok("dd_r", "dd_u")
        ok("dd_r", "dd_nu")
        no("dd_r", "dd_e")


    def _test_success(self, visitor, visited, target):
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_create", args=[self.persons[visited].lookup_key]))
        self.assertEqual(response.status_code, 200)
        response = client.post(reverse("process_create", args=[self.persons[visited].lookup_key]), data={"applying_for": target})
        self.assertRedirectMatches(response, r"/process/\d+$")
        p = pmodels.Process.objects.get(person=self.persons[visited], applying_for=target, closed_time__isnull=True)
        self.assertIsNone(p.frozen_by)
        self.assertIsNone(p.frozen_time)
        self.assertIsNone(p.approved_by)
        self.assertIsNone(p.approved_time)
        self.assertIsNone(p.closed_by)
        self.assertIsNone(p.closed_time)
        self.assertEqual(p.fd_comment, "")

        from django.core import mail
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].cc, [p.archive_email])
        self.assertEqual(mail.outbox[0].from_email, '"nm.debian.org" <nm@debian.org>')
        self.assertIn(const.ALL_STATUS_DESCS[target], mail.outbox[0].subject)

    def _test_success_dde(self, visitor, visited, target):
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_create", args=[self.persons[visited].lookup_key]))
        self.assertEqual(response.status_code, 200)
        response = client.post(reverse("process_create", args=[self.persons[visited].lookup_key]), data={"applying_for": target})
        self.assertRedirectMatches(response, reverse("process_emeritus", args=[self.persons[visited].lookup_key]))

    def _test_invalid(self, visitor, visited, target):
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_create", args=[self.persons[visited].lookup_key]))
        self.assertEqual(response.status_code, 200)

        response = client.post(reverse("process_create", args=[self.persons[visited].lookup_key]), data={"applying_for": target})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(pmodels.Process.objects.filter(person=self.persons[visited], applying_for=target, closed_time__isnull=True).exists())
        self.assertIn("Select a valid choice.", response.context["form"].errors["applying_for"][0])

    def _test_forbidden(self, visitor, visited, target):
        client = self.make_test_client(visitor)
        response = client.get(reverse("process_create", args=[self.persons[visited].lookup_key]))
        self.assertPermissionDenied(response)

        response = client.post(reverse("process_create", args=[self.persons[visited].lookup_key]), data={"applying_for": target})
        self.assertPermissionDenied(response)
        self.assertFalse(pmodels.Process.objects.filter(person=self.persons[visited], applying_for=target, closed_time__isnull=True).exists())
