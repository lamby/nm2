# -*- coding: utf-8 -*-

from django.db import models, migrations
import re

def person_fpr_to_fingerprint(apps, schema_editor):
    Person = apps.get_model("backend", "Person")
    Fingerprint = apps.get_model("backend", "Fingerprint")
    re_valid = re.compile(r"^[0-9A-Fa-f]+$")
    for p in Person.objects.all():
        # Skip empty fingerprints
        if not p.fpr: continue
        # Skip invalid fingerprints (match by hex regexp)
        if not re_valid.match(p.fpr): continue
        # Create a corresponding Fingerprint object
        Fingerprint.objects.create(user=p, fpr=p.fpr)


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0002_fingerprint'),
    ]

    operations = [
        migrations.RunPython(person_fpr_to_fingerprint),
    ]
