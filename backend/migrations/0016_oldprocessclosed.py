# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

def fill_closed(apps, schema_editor):
    Process = apps.get_model("backend", "Process")
    for process in Process.objects.filter(is_active=False, closed__isnull=True):
        process.closed = max(x.logdate for x in process.log.all())
        process.save()


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0015_process_closed'),
    ]

    operations = [
        migrations.RunPython(fill_closed),
    ]
