# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    replaces = [(b'process', '0001_initial'), (b'process', '0002_auto_20160527_1740'), (b'process', '0003_auto_20160527_1744'), (b'process', '0004_auto_20160527_1938'), (b'process', '0005_auto_20160527_2041'), (b'process', '0006_requirement_approved_time'), (b'process', '0007_log_action'), (b'process', '0008_amassignment'), (b'process', '0009_auto_20160529_2128'), (b'process', '0010_auto_20160529_2130'), (b'process', '0011_auto_20160530_0832'), (b'process', '0012_auto_20160530_0832'), (b'process', '0013_auto_20160530_0837'), (b'process', '0014_auto_20160530_0851')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('backend', '0012_auto_20160520_1030'),
    ]

    operations = [
        migrations.CreateModel(
            name='Log',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_public', models.BooleanField(default=False)),
                ('logdate', models.DateTimeField(default=django.utils.timezone.now)),
                ('logtext', models.TextField(default='', blank=True)),
                ('changed_by', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Process',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('applying_for', models.CharField(max_length=20, verbose_name='target status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dm_e', 'DM, emeritus'), ('dd_r', 'DD, removed'), ('dm_r', 'DM, removed'), ('dc_ga_r', 'DC+closed acct.')])),
                ('completed', models.DateTimeField(help_text='Date the process was reviewed and considered complete, or NULL if not complete', null=True)),
                ('closed', models.DateTimeField(help_text='Date the process was closed, or NULL if still open', null=True)),
                ('fd_comment', models.TextField(default='', verbose_name='Front Desk comments', blank=True)),
                ('person', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Requirement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=16, verbose_name='Requirement type', choices=[('intent', 'Declaration of intent'), ('sc_dmup', 'SC/DFSG/DMUP agreement'), ('advocate', 'Advocate'), ('keycheck', 'Key consistency checks'), ('am_ok', 'Application Manager report')])),
                ('is_ok', models.BooleanField(default=False)),
                ('process', models.ForeignKey(related_name='requirements', to='process.Process')),
            ],
        ),
        migrations.CreateModel(
            name='Statement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('statement', models.TextField(verbose_name='Signed statement', blank=True)),
                ('fpr', models.ForeignKey(related_name='+', to='backend.Fingerprint', help_text='Fingerprint used to verify the statement')),
                ('requirement', models.ForeignKey(related_name='statements', to='process.Requirement')),
                ('uploaded_by', models.ForeignKey(related_name='+', default=0, to=settings.AUTH_USER_MODEL, help_text='Person who uploaded the statement')),
                ('uploaded_time', models.DateTimeField(default=datetime.datetime(2016, 5, 27, 17, 44, 3, 953292), help_text='When the statement has been uploaded')),
            ],
        ),
        migrations.AddField(
            model_name='log',
            name='process',
            field=models.ForeignKey(related_name='log', to='process.Process'),
        ),
        migrations.AlterUniqueTogether(
            name='requirement',
            unique_together=set([('process', 'type')]),
        ),
        migrations.AlterModelOptions(
            name='requirement',
            options={'ordering': ['type']},
        ),
        migrations.AlterModelOptions(
            name='log',
            options={'ordering': ['-logdate']},
        ),
        migrations.AddField(
            model_name='log',
            name='requirement',
            field=models.ForeignKey(related_name='log', blank=True, to='process.Requirement', null=True),
        ),
        migrations.RemoveField(
            model_name='requirement',
            name='is_ok',
        ),
        migrations.AddField(
            model_name='requirement',
            name='approved_by',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, help_text='Set to the person that reviewed and approved this requirement', null=True),
        ),
        migrations.AddField(
            model_name='requirement',
            name='approved_time',
            field=models.DateTimeField(help_text='When the requirement has been approved', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='log',
            name='action',
            field=models.CharField(help_text='Action performed with this log entry, if any', max_length=16, blank=True),
        ),
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
        migrations.AlterModelOptions(
            name='amassignment',
            options={'ordering': ['-assigned_by']},
        ),
        migrations.AlterField(
            model_name='amassignment',
            name='unassigned_by',
            field=models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, help_text='Person who did the unassignment', null=True),
        ),
        migrations.AlterField(
            model_name='amassignment',
            name='unassigned_time',
            field=models.DateTimeField(help_text='When the unassignment happened', null=True, blank=True),
        ),
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
            name='frozen_by',
            field=models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, help_text='Person that froze this process for review, or NULL if it is still being worked on', null=True),
        ),
        migrations.AddField(
            model_name='process',
            name='frozen_time',
            field=models.DateTimeField(help_text='Date the process was frozen for review, or NULL if it is still being worked on', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='process',
            name='approved_time',
            field=models.DateTimeField(help_text='Date the process was reviewed and considered complete, or NULL if not yet reviewed', null=True),
        ),
    ]
