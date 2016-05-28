# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0005_auto_20160527_2041'),
    ]

    operations = [
        migrations.AddField(
            model_name='requirement',
            name='approved_time',
            field=models.DateTimeField(help_text='When the requirement has been approved', null=True, blank=True),
        ),
    ]
