# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-08-12 18:22
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0004_merge_20170810_1547'),
    ]

    operations = [
        migrations.AddField(
            model_name='process',
            name='started',
            field=models.DateTimeField(auto_now_add=True, null=True, verbose_name='process started'),
        ),
    ]
