# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0005_auto_20150512_1511'),
    ]

    operations = [
        migrations.AddField(
            model_name='am',
            name='fd_comment',
            field=models.TextField(default='', verbose_name='Front Desk comments', blank=True),
            preserve_default=True,
        ),
    ]
