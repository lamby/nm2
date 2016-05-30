# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('process', '0010_auto_20160529_2130'),
    ]

    operations = [
        migrations.RenameField(
            model_name='process',
            old_name='completed',
            new_name='approved_time',
        ),
        migrations.AddField(
            model_name='process',
            name='approved_by',
            field=models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, help_text='Person that reviewed this process and considered it complete, or NULL if not yet reviewed', null=True),
        ),
        migrations.AddField(
            model_name='process',
            name='submitted_by',
            field=models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, help_text='Person that froze this process for review, or NULL if it is still being worked on', null=True),
        ),
        migrations.AddField(
            model_name='process',
            name='submitted_time',
            field=models.DateTimeField(help_text='Date the process was frozen for review, or NULL if it is still being worked on', null=True, blank=True),
        ),
    ]
