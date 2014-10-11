# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import backend.models
import datetime
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_superuser', models.BooleanField(default=False, help_text='Designates that this user has all permissions without explicitly assigning them.', verbose_name='superuser status')),
                ('username', models.CharField(unique=True, max_length=255)),
                ('last_login', models.DateTimeField(default=django.utils.timezone.now, verbose_name='last login')),
                ('date_joined', models.DateTimeField(default=django.utils.timezone.now, verbose_name='date joined')),
                ('is_staff', models.BooleanField(default=False)),
                ('cn', models.CharField(max_length=250, verbose_name='first name')),
                ('mn', models.CharField(max_length=250, null=True, verbose_name='middle name', blank=True)),
                ('sn', models.CharField(max_length=250, null=True, verbose_name='last name', blank=True)),
                ('email', models.EmailField(unique=True, max_length=75, verbose_name='email address')),
                ('bio', backend.models.TextNullField(help_text='Please enter here a short biographical information', null=True, verbose_name='short biography', blank=True)),
                ('uid', backend.models.CharNullField(max_length=32, unique=True, null=True, verbose_name='Debian account name', blank=True)),
                ('fpr', backend.models.FingerprintField(max_length=40, unique=True, null=True, verbose_name='OpenPGP key fingerprint', blank=True)),
                ('status', models.CharField(max_length=20, verbose_name='current status in the project', choices=[('dc', 'Debian Contributor'), ('dc_ga', 'Debian Contributor, with guest account'), ('dm', 'Debian Maintainer'), ('dm_ga', 'Debian Maintainer, with guest account'), ('dd_u', 'Debian Developer, uploading'), ('dd_nu', 'Debian Developer, non-uploading'), ('dd_e', 'Debian Developer, emeritus'), ('dm_e', 'Debian Maintainer, emeritus'), ('dd_r', 'Debian Developer, removed'), ('dm_r', 'Debian Maintainer, removed')])),
                ('status_changed', models.DateTimeField(default=datetime.datetime.utcnow, verbose_name='when the status last changed')),
                ('fd_comment', models.TextField(null=True, verbose_name='Front Desk comments', blank=True)),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow, null=True, verbose_name='Person record created')),
                ('expires', models.DateField(default=None, help_text='This person will be deleted after this date if the status is still dc and no Process has started', null=True, verbose_name='Expiration date for the account', blank=True)),
                ('pending', models.CharField(max_length=255, verbose_name='Nonce used to confirm this pending record', blank=True)),
                ('groups', models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Group', blank=True, help_text='The groups this user belongs to. A user will get all permissions granted to each of his/her group.', verbose_name='groups')),
                ('user_permissions', models.ManyToManyField(related_query_name='user', related_name='user_set', to='auth.Permission', blank=True, help_text='Specific permissions for this user.', verbose_name='user permissions')),
            ],
            options={
                'db_table': 'person',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='AM',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('slots', models.IntegerField(default=1)),
                ('is_am', models.BooleanField(default=True, verbose_name='Active AM')),
                ('is_fd', models.BooleanField(default=False, verbose_name='FD member')),
                ('is_dam', models.BooleanField(default=False, verbose_name='DAM')),
                ('is_am_ctte', models.BooleanField(default=False, verbose_name='NM CTTE member')),
                ('created', models.DateTimeField(default=datetime.datetime.utcnow, null=True, verbose_name='AM record created')),
                ('person', models.OneToOneField(related_name='am', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'am',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Log',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('progress', models.CharField(max_length=20, choices=[('app_new', 'Applicant asked to enter the process'), ('app_rcvd', 'Applicant replied to initial mail'), ('app_hold', 'On hold before entering the queue'), ('adv_rcvd', 'Received enough advocacies'), ('poll_sent', 'Activity poll sent'), ('app_ok', 'Advocacies have been approved'), ('am_rcvd', 'Waiting for AM to confirm'), ('am', 'Interacting with an AM'), ('am_hold', 'AM hold'), ('am_ok', 'AM approved'), ('fd_hold', 'FD hold'), ('fd_ok', 'FD approved'), ('dam_hold', 'DAM hold'), ('dam_ok', 'DAM approved'), ('done', 'Completed'), ('cancelled', 'Cancelled')])),
                ('is_public', models.BooleanField(default=False)),
                ('logdate', models.DateTimeField(default=datetime.datetime.utcnow)),
                ('logtext', backend.models.TextNullField(null=True, blank=True)),
                ('changed_by', models.ForeignKey(related_name='log_written', to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'db_table': 'log',
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Process',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('applying_as', models.CharField(max_length=20, verbose_name='original status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dm_e', 'DM, emeritus'), ('dd_r', 'DD, removed'), ('dm_r', 'DM, removed')])),
                ('applying_for', models.CharField(max_length=20, verbose_name='target status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dm_e', 'DM, emeritus'), ('dd_r', 'DD, removed'), ('dm_r', 'DM, removed')])),
                ('progress', models.CharField(max_length=20, choices=[('app_new', 'Applied'), ('app_rcvd', 'Validated'), ('app_hold', 'App hold'), ('adv_rcvd', 'Adv ok'), ('poll_sent', 'Poll sent'), ('app_ok', 'App ok'), ('am_rcvd', 'AM assigned'), ('am', 'AM'), ('am_hold', 'AM hold'), ('am_ok', 'AM ok'), ('fd_hold', 'FD hold'), ('fd_ok', 'FD ok'), ('dam_hold', 'DAM hold'), ('dam_ok', 'DAM ok'), ('done', 'Done'), ('cancelled', 'Cancelled')])),
                ('is_active', models.BooleanField(default=False)),
                ('archive_key', models.CharField(unique=True, max_length=128, verbose_name='mailbox archive key')),
                ('advocates', models.ManyToManyField(related_name='advocated', to=settings.AUTH_USER_MODEL, blank=True)),
                ('manager', models.ForeignKey(related_name='processed', blank=True, to='backend.AM', null=True)),
                ('person', models.ForeignKey(related_name='processes', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'process',
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='log',
            name='process',
            field=models.ForeignKey(related_name='log', to='backend.Process'),
            preserve_default=True,
        ),
    ]
