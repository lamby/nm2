# -*- coding: utf-8 -*-


from django.db import models, migrations

def set_existing_fingerprints_as_active(apps, schema_editor):
    Fingerprint = apps.get_model("backend", "Fingerprint")
    Fingerprint.objects.update(is_active=True)

class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0005_fingerprint_is_active'),
    ]

    operations = [
        migrations.RunPython(set_existing_fingerprints_as_active),
    ]
