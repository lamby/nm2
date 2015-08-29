# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0004_remove_person_fpr'),
    ]

    operations = [
        migrations.AddField(
            model_name='fingerprint',
            name='is_active',
            field=models.BooleanField(default=False, help_text='whether this key is curently in use'),
            preserve_default=True,
        ),
    ]
