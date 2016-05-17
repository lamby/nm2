# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models

def approve_dd_fprs(apps, schema_editor):
    Fingerprint = apps.get_model("backend", "Fingerprint")
    for f in Fingerprint.objects.all():
        if f.person.status in ("dc_ga", "dm_ga", "dd_u", "dd_nu", "dd_e", "dd_r", "dc_ga_r"):
            f.endorsement_valid = True
            f.save()


class Migration(migrations.Migration):
    dependencies = [
        ('backend', '0009_auto_20160517_1627'),
    ]

    operations = [
        migrations.RunPython(approve_dd_fprs),
    ]
