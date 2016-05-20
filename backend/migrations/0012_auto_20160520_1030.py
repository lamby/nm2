# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0011_auto_20160520_1030'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fingerprint',
            name='agreement',
            field=models.TextField(help_text='Agreement of DC and SMUP signed with this key', blank=True),
        ),
        migrations.AlterField(
            model_name='fingerprint',
            name='agreement_valid',
            field=models.BooleanField(default=False, help_text='True if the agreement has been verified to have valid wording'),
        ),
    ]
