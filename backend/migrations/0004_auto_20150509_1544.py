# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0003_auto_20150509_1517'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='fd_comment',
            field=models.TextField(default='', verbose_name='Front Desk comments', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='mn',
            field=models.CharField(default='', max_length=250, verbose_name='middle name', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='person',
            name='sn',
            field=models.CharField(default='', max_length=250, verbose_name='last name', blank=True),
            preserve_default=True,
        ),
    ]
