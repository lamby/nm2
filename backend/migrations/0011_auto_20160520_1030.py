# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0010_auto_20160517_1650'),
    ]

    operations = [
        migrations.RenameField(
            model_name='fingerprint',
            old_name='endorsement',
            new_name='agreement',
        ),
        migrations.RenameField(
            model_name='fingerprint',
            old_name='endorsement_valid',
            new_name='agreement_valid',
        ),
    ]
