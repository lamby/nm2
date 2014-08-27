# coding: utf8
"""
Test permissions
"""
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.test import TestCase
from backend import const
from backend.test_common import *

class WhenView(NMTestUtilsWhen):
    def setUp(self, fixture):
        super(WhenView, self).setUp(fixture)
        self.url = reverse("person", kwargs={ "key": self.args["person"].lookup_key })

class ThenPerms(ThenSuccess):
    def __init__(self, perms):
        self.perms_expected = frozenset(perms.split() if perms else ())
    def __call__(self, fixture, response, when, test_client):
        super(ThenPerms, self).__call__(fixture, response, when, test_client)
        perms = response.context["vperms"].perms
        if perms != self.perms_expected:
            fixture.fail("{} got permissions ({}) instead of ({}) when {}".format(
                when.user, ", ".join(sorted(perms)), ", ".join(sorted(self.perms_expected)), when))

class ThenCanAdv(ThenSuccess):
    def __init__(self, adv):
        self.adv_expected = frozenset(adv.split() if adv else ())
    def __call__(self, fixture, response, when, test_client):
        super(ThenCanAdv, self).__call__(fixture, response, when, test_client)
        adv = frozenset(response.context["vperms"].advocate_targets)
        if adv != self.adv_expected:
            fixture.fail("{} can advocate for ({}) instead of ({}) when {}".format(
                when.user, ", ".join(sorted(adv)), ", ".join(sorted(self.adv_expected)), when))

class visit_base(object):
    def __init__(self, fixture, person, other_perms="", other_advs=""):
        self.fixture = fixture
        self.visitors_perms_seen = set()
        self.visitors_advs_seen = set()
        self.other_perms = other_perms
        self.other_advs = other_advs
        self.person = fixture.users[person]

    def __enter__(self):
        self.fixture.visit = self
        return self

    def _check_other_perms(self):
        "Test all other users not tested in the previous loop"
        if None not in self.visitors_perms_seen:
            self.fixture.assertVisit(WhenView(person=self.person), ThenPerms(self.other_perms))
        for u in self.fixture.users.viewkeys() - self.visitors_perms_seen:
            self.fixture.assertVisit(WhenView(person=self.person, user=self.fixture.users[u]), ThenPerms(self.other_perms))

    def _check_other_advs(self):
        "Test all other users not tested in the previous loop"
        if None not in self.visitors_advs_seen:
            self.fixture.assertVisit(WhenView(person=self.person), ThenCanAdv(self.other_advs))
        for u in self.fixture.users.viewkeys() - self.visitors_advs_seen:
            self.fixture.assertVisit(WhenView(person=self.person, user=self.fixture.users[u]), ThenCanAdv(self.other_advs))

class visit(visit_base):
    def __exit__(self, type, value, traceback):
        if type is not None: return
        self._check_other_perms()
        self._check_other_advs()
        self.fixture.visit = None

class visit_perms(visit_base):
    def __exit__(self, type, value, traceback):
        if type is not None: return
        self._check_other_perms()
        self.fixture.visit = None

class visit_advs(visit_base):
    def __exit__(self, type, value, traceback):
        if type is not None: return
        self._check_other_advs()
        self.fixture.visit = None

class PersonTestMixin(NMBasicFixtureMixin, NMTestUtilsMixin):
    def assertPerms(self, who, perms=""):
        # Go through all combinations of visitors and expected results
        for u in who.split():
            if u is None:
                self.assertVisit(WhenView(person=self.visit.person), ThenPerms(perms))
            else:
                self.assertVisit(WhenView(person=self.visit.person, user=self.users[u]), ThenPerms(perms))
            self.visit.visitors_perms_seen.add(u)

    def assertAdvs(self, who, adv):
        # Go through all combinations of visitors and expected results
        for u in who.split():
            if u is None:
                self.assertVisit(WhenView(person=self.visit.person), ThenCanAdv(adv))
            else:
                self.assertVisit(WhenView(person=self.visit.person, user=self.users[u]), ThenCanAdv(adv))
            self.visit.visitors_advs_seen.add(u)


class NoProcessTestCase(PersonTestMixin, TestCase):
    """
    Test permissions when each kind of person visits each kind of person, with
    no processes involved
    """
    def test_pending(self):
        with visit(self, "pending"):
            self.assertPerms("fd dam", "edit_bio edit_ldap")

    def test_dc(self):
        with visit(self, "dc"):
            self.assertPerms("fd dam dc", "edit_bio edit_ldap")
            self.assertAdvs("fd dam dd_nu dd_u", "mm_ga dm dd_u dd_nu")
            self.assertAdvs("dm dm_ga", "mm_ga")

    def test_dc_ga(self):
        with visit(self, "dc_ga"):
            self.assertPerms("fd dam dc_ga", "edit_bio")
            self.assertAdvs("fd dam dd_nu dd_u", "dm_ga dd_u dd_nu")

    def test_dm(self):
        with visit(self, "dm"):
            self.assertPerms("fd dam", "edit_bio edit_ldap")
            self.assertPerms("dm", "edit_bio edit_ldap")
            self.assertAdvs("fd dam dd_nu dd_u", "dm_ga dd_u dd_nu")
            self.assertAdvs("dm dm_ga", "dm_ga")

    def test_dm_ga(self):
        with visit(self, "dm_ga"):
            self.assertPerms("fd dam dm_ga", "edit_bio")
            self.assertAdvs("fd dam dd_nu dd_u", "dd_u dd_nu")

    def test_dd_nu(self):
        with visit(self, "dd_nu"):
            self.assertPerms("fd dam dd_nu", "edit_bio")

    def test_dd_u(self):
        with visit(self, "dd_u"):
            self.assertPerms("fd dam dd_u", "edit_bio")

    def test_fd(self):
        with visit(self, "fd"):
            self.assertPerms("fd dam", "edit_bio")

    def test_dam(self):
        with visit(self, "dam"):
            self.assertPerms("fd dam", "edit_bio")

class ProcTestMixin(PersonTestMixin, TestCase):
    applying_as = None
    applying_for = None
    advocate_status = const.STATUS_DD_NU

    def setUp(self):
        super(ProcTestMixin, self).setUp()
        self.app = self.make_user("app", self.applying_as, alioth=True)
        self.adv = self.make_user("adv", self.advocate_status)
        self.am = self.make_user("am", const.STATUS_DD_NU)
        self.am_am = bmodels.AM.objects.create(person=self.am)
        self.proc = self.make_process(self.app, self.applying_for, const.PROGRESS_APP_RCVD)

    def assertAdvsInitial(self): self.fail("Not implemented")
    def assertAdvsAdv(self): self.fail("Not implemented")
    def assertAdvsAdvAM(self): self.fail("Not implemented")
    def assertAdvsFDDAM(self): self.fail("Not implemented")
    def assertAdvsDone(self): self.fail("Not implemented")

    def test_advs(self):
        self.proc.advocates.clear()
        self.proc.manager = None
        self.proc.save()

        # States without advocates and AMs
        for p in (const.PROGRESS_APP_NEW, const.PROGRESS_APP_RCVD, const.PROGRESS_APP_HOLD, const.PROGRESS_ADV_RCVD, const.PROGRESS_POLL_SENT):
            self.proc.progress = p
            self.proc.save()
            with visit_advs(self, "app"):
                self.assertAdvsInitial()

        # States with advocates and no AMs
        self.proc.advocates.add(self.adv)
        for p in (const.PROGRESS_APP_OK,):
            self.proc.progress = p
            self.proc.save()
            with visit_advs(self, "app"):
                self.assertAdvsAdv()

        # States with advocates and AMs
        self.proc.manager = self.am_am
        for p in (const.PROGRESS_AM_RCVD, const.PROGRESS_AM, const.PROGRESS_AM_HOLD):
            self.proc.progress = p
            self.proc.save()
            with visit_advs(self, "app"):
                self.assertAdvsAdvAM()

        # States after the AM
        for p in (const.PROGRESS_AM_OK, const.PROGRESS_FD_HOLD, const.PROGRESS_FD_OK, const.PROGRESS_DAM_HOLD, const.PROGRESS_DAM_OK):
            self.proc.progress = p
            self.proc.save()

            with visit_advs(self, "app"):
                self.assertAdvsFDDAM()

        # Final states
        self.app.status = self.applying_for
        self.app.save()
        for p in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED):
            self.proc.progress = p
            self.proc.is_active = False
            self.proc.save()

            with visit_advs(self, "app"):
                self.assertAdvsDone()

    def test_perms(self):
        self.proc.advocates.clear()
        self.proc.manager = None
        self.proc.save()

        # States without advocates and AMs
        for p in (const.PROGRESS_APP_NEW, const.PROGRESS_APP_RCVD, const.PROGRESS_APP_HOLD, const.PROGRESS_ADV_RCVD, const.PROGRESS_POLL_SENT):
            self.proc.progress = p
            self.proc.save()
            with visit_perms(self, "app"):
                self.assertPerms("fd dam app", "edit_bio edit_ldap")

        # States with advocates and no AMs
        self.proc.advocates.add(self.adv)
        for p in (const.PROGRESS_APP_OK,):
            self.proc.progress = p
            self.proc.save()
            with visit_perms(self, "app"):
                self.assertPerms("fd dam adv app", "edit_bio edit_ldap")

        # States with advocates and AMs
        self.proc.manager = self.am_am
        for p in (const.PROGRESS_AM_RCVD, const.PROGRESS_AM, const.PROGRESS_AM_HOLD):
            self.proc.progress = p
            self.proc.save()
            with visit_perms(self, "app"):
                self.assertPerms("fd dam adv am app", "edit_bio edit_ldap")

        # States after the AM
        for p in (const.PROGRESS_AM_OK, const.PROGRESS_FD_HOLD, const.PROGRESS_FD_OK, const.PROGRESS_DAM_HOLD, const.PROGRESS_DAM_OK):
            self.proc.progress = p
            self.proc.save()

            with visit_perms(self, "app"):
                self.assertPerms("fd dam", "edit_bio edit_ldap")

        # Final states
        self.app.status = self.applying_for
        self.app.save()
        for p in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED):
            self.proc.progress = p
            self.proc.is_active = False
            self.proc.save()

            with visit_perms(self, "app"):
                self.assertPerms("fd dam app", "edit_bio")


class ProcDcgaAdvDMTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
    """
    applying_as = const.STATUS_MM
    applying_for = const.STATUS_MM_GA
    advocate_status = const.STATUS_DM

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "mm_ga dm dd_u dd_nu")
        self.assertAdvs("adv dm dm_ga", "mm_ga")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "mm_ga dm dd_u dd_nu")
        self.assertAdvs("dm dm_ga", "mm_ga")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "mm_ga dm dd_u dd_nu")
        self.assertAdvs("dm dm_ga", "mm_ga")
        self.assertAdvs("am", "dm dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm_ga dd_u dd_nu")

class ProcDcgaAdvDDTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dd advocate
    """
    applying_as = const.STATUS_MM
    applying_for = const.STATUS_MM_GA
    advocate_status = const.STATUS_DD_NU

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDmgaAdvDMTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
    """
    applying_as = const.STATUS_DM
    applying_for = const.STATUS_DM_GA
    advocate_status = const.STATUS_DM

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDmgaAdvDDTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dd advocate
    """
    applying_as = const.STATUS_DM
    applying_for = const.STATUS_DM_GA
    advocate_status = const.STATUS_DD_NU

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDMTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dd advocate
    """
    applying_as = const.STATUS_MM
    applying_for = const.STATUS_DM
    advocate_status = const.STATUS_DD_NU

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDcDdnuTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
    """
    applying_as = const.STATUS_MM
    applying_for = const.STATUS_DD_NU
    advocate_status = const.STATUS_DD_NU

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDcgaDdnuTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
    """
    applying_as = const.STATUS_MM_GA
    applying_for = const.STATUS_DD_NU
    advocate_status = const.STATUS_DD_NU

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDcDduTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
    """
    applying_as = const.STATUS_MM
    applying_for = const.STATUS_DD_U
    advocate_status = const.STATUS_DD_U

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDcgaDduTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
    """
    applying_as = const.STATUS_MM_GA
    applying_for = const.STATUS_DD_U
    advocate_status = const.STATUS_DD_U

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDmDduTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
    """
    applying_as = const.STATUS_DM
    applying_for = const.STATUS_DD_U
    advocate_status = const.STATUS_DD_U

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

class ProcDmgaDduTestCase(ProcTestMixin, TestCase):
    """
    Test all visit combinations for an applicant from dc to dc_ga, with a dm advocate
    """
    applying_as = const.STATUS_DM_GA
    applying_for = const.STATUS_DD_U
    advocate_status = const.STATUS_DD_U

    def assertAdvsInitial(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dm dd_u dd_nu")
    def assertAdvsAdv(self):
        self.assertAdvs("fd dam am dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv", "dd_u dd_nu")
    def assertAdvsAdvAM(self):
        self.assertAdvs("fd dam dd_nu dd_u", "dm dd_u dd_nu")
        self.assertAdvs("adv am", "dd_u dd_nu")
    def assertAdvsFDDAM(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")
    def assertAdvsDone(self):
        self.assertAdvs("fd dam adv am dd_nu dd_u", "dd_u dd_nu")

