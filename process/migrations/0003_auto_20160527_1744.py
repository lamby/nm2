# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0002_auto_20160527_1740'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='statement',
            name='statement_verified',
        ),
        migrations.AddField(
            model_name='statement',
            name='uploaded_time',
            field=models.DateTimeField(default=datetime.datetime(2016, 5, 27, 17, 44, 3, 953292), help_text='When the statement has been uploaded'),
            preserve_default=False,
        ),
    ]
