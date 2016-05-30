# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0011_auto_20160530_0832'),
    ]

    operations = [
        migrations.AlterField(
            model_name='process',
            name='approved_time',
            field=models.DateTimeField(help_text='Date the process was reviewed and considered complete, or NULL if not yet reviewed', null=True),
        ),
    ]
