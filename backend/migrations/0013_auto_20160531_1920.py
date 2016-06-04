# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0012_auto_20160520_1030'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='fingerprint',
            name='agreement',
        ),
        migrations.RemoveField(
            model_name='fingerprint',
            name='agreement_valid',
        ),
    ]
