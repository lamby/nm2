# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from backend.unittest import NamedObjects, PersonFixtureMixin
import backend.models as bmodels
import process.models as pmodels


class TestProcesses(NamedObjects):
    def __init__(self, **defaults):
        super(TestProcesses, self).__init__(pmodels.Process, **defaults)

    def create(self, _name, **kw):
        self._update_kwargs_with_defaults(_name, kw)

#        if "process" in kw:
#            kw.setdefault("is_active", kw["process"] not in (const.PROGRESS_DONE, const.PROGRESS_CANCELLED))
#        else:
#            kw.setdefault("is_active", True)
#
#        if "manager" in kw:
#            try:
#                am = kw["manager"].am
#            except AM.DoesNotExist:
#                am = AM.objects.create(person=kw["manager"])
#            kw["manager"] = am

        self[_name] = o = self._model.objects.create(**kw)
#        for a in advocates:
#            o.advocates.add(a)
        return o


class ProcessFixtureMixin(PersonFixtureMixin):
    @classmethod
    def get_processes_defaults(cls):
        """
        Get default arguments for test processes
        """
        return {}

    @classmethod
    def setUpClass(cls):
        super(ProcessFixtureMixin, cls).setUpClass()
        cls.processes = TestProcesses(**cls.get_processes_defaults())

    @classmethod
    def tearDownClass(cls):
        cls.processes.delete_all()
        super(ProcessFixtureMixin, cls).tearDownClass()

    def setUp(self):
        super(ProcessFixtureMixin, self).setUp()
        self.processes.refresh();


def get_all_process_types():
    """
    Generate all valid (source_status, applying_for) pairs for all possible
    processes.
    """
    for src, tgts in bmodels.Person._new_status_table.items():
        for tgt in tgts:
            yield src, tgt


