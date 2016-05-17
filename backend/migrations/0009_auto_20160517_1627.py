# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0008_auto_20160517_1548'),
    ]

    operations = [
        migrations.AddField(
            model_name='fingerprint',
            name='endorsement',
            field=models.TextField(help_text='Endorsement of DC and SMUP signed with this key', blank=True),
        ),
        migrations.AddField(
            model_name='fingerprint',
            name='endorsement_valid',
            field=models.BooleanField(default=False, help_text='True if the endorsement has been verified to have valid wording'),
        ),
    ]
