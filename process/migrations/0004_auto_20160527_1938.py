# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0003_auto_20160527_1744'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='log',
            options={'ordering': ['-logdate']},
        ),
        migrations.AddField(
            model_name='log',
            name='requirement',
            field=models.ForeignKey(related_name='log', blank=True, to='process.Requirement', null=True),
        ),
    ]
