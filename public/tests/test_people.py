# coding: utf-8
"""
Test person view
"""




from django.test import TestCase
from backend.test_common import NMFactoryMixin
from backend import const

class PersonPageTestCase(NMFactoryMixin, TestCase):
    def setUp(self):
        super(PersonPageTestCase, self).setUp()
        # Create a test person and process
        self.person = self.make_user("test", const.STATUS_DC, cn="Test", sn="Test", email="testuser@debian.org")
        self.process = self.make_process(self.person, applying_for=const.STATUS_DM, progress=const.PROGRESS_APP_OK, applying_as=const.STATUS_DC)

    def test_person_listing(self):
        """
        Tests that a person is listed on the public persons page
        """
        # Check that the new person is listed on the page
        response = self.client.get('/public/people')
        self.assertContains(response, 'Test Test', 1)
        self.assertContains(response, '>test<', 1)
