# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import backend.models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('backend', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='InconsistentFingerprint',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('info', models.TextField(default=b'{"log": []}')),
                ('created', models.DateTimeField(auto_now=True)),
                ('fpr', backend.models.FingerprintField(unique=True, max_length=40, verbose_name='OpenPGP key fingerprint')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InconsistentPerson',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('info', models.TextField(default=b'{"log": []}')),
                ('created', models.DateTimeField(auto_now=True)),
                ('person', models.OneToOneField(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='InconsistentProcess',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('info', models.TextField(default=b'{"log": []}')),
                ('created', models.DateTimeField(auto_now=True)),
                ('process', models.OneToOneField(to='backend.Process')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
