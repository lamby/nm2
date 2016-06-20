# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0013_auto_20160531_1920'),
    ]

    operations = [
        migrations.AlterField(
            model_name='am',
            name='created',
            field=models.DateTimeField(default=django.utils.timezone.now, null=True, verbose_name='AM record created'),
        ),
        migrations.AlterField(
            model_name='log',
            name='logdate',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AlterField(
            model_name='person',
            name='created',
            field=models.DateTimeField(default=django.utils.timezone.now, null=True, verbose_name='Person record created'),
        ),
        migrations.AlterField(
            model_name='person',
            name='status_changed',
            field=models.DateTimeField(default=django.utils.timezone.now, verbose_name='when the status last changed'),
        ),
    ]
