# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0002_personauditlog'),
    ]

    operations = [
        migrations.AlterField(
            model_name='log',
            name='logtext',
            field=models.TextField(default='', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='bio',
            field=models.TextField(default='', help_text='Please enter here a short biographical information', verbose_name='short biography', blank=True),
            preserve_default=True,
        ),
    ]
