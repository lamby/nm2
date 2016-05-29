# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('backend', '0012_auto_20160520_1030'),
        ('process', '0007_log_action'),
    ]

    operations = [
        migrations.CreateModel(
            name='AMAssignment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('paused', models.BooleanField(default=False, help_text='Whether this process is paused and the AM is free to take another applicant in the meantime')),
                ('assigned_time', models.DateTimeField(help_text='When the assignment happened')),
                ('unassigned_time', models.DateTimeField(help_text='When the unassignment happened')),
                ('am', models.ForeignKey(to='backend.AM')),
                ('assigned_by', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, help_text='Person who did the assignment')),
                ('process', models.ForeignKey(related_name='ams', to='process.Process')),
                ('unassigned_by', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, help_text='Person who did the unassignment')),
            ],
        ),
    ]
