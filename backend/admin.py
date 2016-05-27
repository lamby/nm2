# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.contrib import admin
from django.db import models
import django.contrib.admin.widgets as adminwidgets
import backend.models as bmodels


class PersonAdmin(admin.ModelAdmin):
    exclude = ("user",)
    search_fields = ("cn", "sn", "email", "uid")

    def save_model(self, request, obj, form, change):
        """
        Given a model instance save it to the database.
        """
        obj.save(audit_author=request.user, audit_notes="edited from admin")

admin.site.register(bmodels.Person, PersonAdmin)

class AMAdmin(admin.ModelAdmin):
    search_fields = ("person__cn", "person__sn", "person__email", "person__uid")
admin.site.register(bmodels.AM, AMAdmin)

class LogInline(admin.TabularInline):
    model = bmodels.Log

class ProcessAdmin(admin.ModelAdmin):
    raw_id_fields = ('manager',)
    filter_horizontal = ("advocates",)
    search_fields = ("person__cn", "person__sn", "person__email", "person__uid")
admin.site.register(bmodels.Process, ProcessAdmin)

class LogAdmin(admin.ModelAdmin):
    raw_id_fields = ('changed_by',)
admin.site.register(bmodels.Log, LogAdmin)
