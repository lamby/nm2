# -*- coding: utf-8 -*-
# Generated by Django 1.10.7 on 2017-08-24 08:44
from __future__ import unicode_literals

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('process', '0007_auto_20170812_1825'),
    ]

    operations = [
        migrations.AddField(
            model_name='process',
            name='closed_by',
            field=models.ForeignKey(blank=True, help_text='Person that closed this process, or NULL if still open', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.RenameField(model_name='process', old_name='closed', new_name='closed_time'),
    ]
