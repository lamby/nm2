# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.contrib import admin
from django.db import models
import django.contrib.admin.widgets as adminwidgets
from . import models as pmodels

class ProcessAdmin(admin.ModelAdmin):
    exclude = ("person", )
    search_fields = ("person__cn", "person__sn", "person__email", "person__uid")
admin.site.register(pmodels.Process, ProcessAdmin)


class RequirementAdmin(admin.ModelAdmin):
    exclude = ("process", )
admin.site.register(pmodels.Requirement, RequirementAdmin)


class RequirementAMAssignment(admin.ModelAdmin):
    exclude = ("process", )
admin.site.register(pmodels.AMAssignment, RequirementAMAssignment)


class LogAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)
admin.site.register(pmodels.Log, LogAdmin)
