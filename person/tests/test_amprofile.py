from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now
from django.core import mail
from backend import const
from backend import models as bmodels
from backend.unittest import PersonFixtureMixin, PageElements
import person.models as pmodels


class TestAMProfile(PersonFixtureMixin, TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestAMProfile, cls).setUpClass()
        cls.elements = PageElements()
        cls.elements.add_id("id_slots")
        cls.elements.add_id("id_is_am")
        cls.elements.add_id("id_is_fd")
        cls.elements.add_id("id_is_dam")
        cls.elements.add_id("id_fd_comment")
        cls.elements.add_id("fd_comments")

    @classmethod
    def __add_extra_tests__(cls):
        # Some users cannot access amprofile at all
        for visitor in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r"):
            for visited in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r", "activeam", "oldam", "fd", "dam"):
                cls._add_method(cls._test_get_fail, visitor, visited)
                cls._add_method(cls._test_post_fail, visitor, visited)

        # Some users have no amprofile
        for visitor in ("activeam", "oldam", "fd", "dam"):
            for visited in ("pending", "dc", "dc_ga", "dm", "dm_ga", "dd_nu", "dd_u", "dd_e", "dd_r"):
                cls._add_method(cls._test_get_fail, visitor, visited)
                cls._add_method(cls._test_post_fail, visitor, visited)

        # AMs / former AMs can only access self
        for visitor in ("activeam", "oldam"):
            for visited in ("activeam", "oldam", "fd", "dam"):
                if visitor == visited:
                    cls._add_method(cls._test_get_success, visitor, visited, elements=("id_slots", "id_is_am"))
                    cls._add_method(cls._test_post_success, visitor, visited, edited=("id_slots", "id_is_am"))
                else:
                    cls._add_method(cls._test_get_fail, visitor, visited)
                    cls._add_method(cls._test_post_fail, visitor, visited)

        # FD sees everything of everyone except the is_dam checkbox
        for visited in ("activeam", "oldam", "fd", "dam"):
            cls._add_method(cls._test_get_success, "fd", visited, elements=("id_slots", "id_is_am", "id_is_fd", "id_fd_comment", "fd_comments"))
            cls._add_method(cls._test_post_success, "fd", visited, edited=("id_slots", "id_is_am", "id_is_fd", "id_fd_comment", "fd_comments"))

        # DAM sees everything of everyone
        for visited in ("activeam", "oldam", "fd", "dam"):
            cls._add_method(cls._test_get_success, "dam", visited, elements=("id_slots", "id_is_am", "id_is_fd", "id_is_dam", "id_fd_comment", "fd_comments"))
            cls._add_method(cls._test_post_success, "dam", visited, edited=("id_slots", "id_is_am", "id_is_fd", "id_is_dam", "id_fd_comment", "fd_comments"))

    def _test_get_success(self, visitor, visited, elements):
        client = self.make_test_client(visitor)
        response = client.get(reverse("person_amprofile", args=[self.persons[visited].lookup_key]))
        self.assertEqual(response.status_code, 200)
        self.assertContainsElements(response, self.elements, *elements)

    def _test_get_fail(self, visitor, visited):
        client = self.make_test_client(visitor)
        response = client.get(reverse("person_amprofile", args=[self.persons[visited].lookup_key]))
        self.assertPermissionDenied(response)

    def _test_post_success(self, visitor, visited, edited):
        client = self.make_test_client(visitor)
        visited = self.persons[visited]
        response = client.post(reverse("person_amprofile", args=[self.persons[visited].lookup_key]), data={
            "slots": visited.am.slots + 1,
            "is_am": not visited.am.is_am,
            "is_fd": not visited.am.is_fd,
            "is_dam": not visited.am.is_dam,
            "fd_comment": "new fd comment",
        })
        self.assertEqual(response.status_code, 200)
        newvisited = bmodels.Person.objects.get(pk=visited.pk)
        if "id_slots" in edited: self.assertEqual(newvisited.am.slots, visited.am.slots + 1)
        if "id_is_am" in edited: self.assertEqual(newvisited.am.is_am, not visited.am.is_am)
        if "id_is_fd" in edited: self.assertEqual(newvisited.am.is_fd, not visited.am.is_fd)
        if "id_is_dam" in edited: self.assertEqual(newvisited.am.is_dam, not visited.am.is_dam)
        if "fd_comments" in edited: self.assertEqual(newvisited.am.fd_comment, "new fd comment")

    def _test_post_fail(self, visitor, visited):
        client = self.make_test_client(visitor)
        visited = self.persons[visited]
        try:
            orig_am = bmodels.AM.objects.get(person__pk=visited.pk)
        except bmodels.AM.DoesNotExist:
            orig_am = None
        response = client.post(reverse("person_amprofile", args=[self.persons[visited].lookup_key]), data={
            "slots": 5,
            "is_am": True,
            "is_fd": True,
            "is_dam": True,
            "fd_comment": "new fd comment",
        })
        self.assertPermissionDenied(response)
        try:
            am = bmodels.AM.objects.get(person__pk=visited.pk)
        except bmodels.AM.DoesNotExist:
            am = None
        if orig_am is None:
            self.assertIsNone(am)
        if am is None:
            return
        self.assertEqual(visited.am.slots, am.slots)
        self.assertEqual(visited.am.is_am, am.is_am)
        self.assertEqual(visited.am.is_fd, am.is_fd)
        self.assertEqual(visited.am.is_dam, am.is_dam)
        self.assertEqual(visited.am.fd_comment, am.fd_comment)
