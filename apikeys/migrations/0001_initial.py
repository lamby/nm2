# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='AuditLog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('ts', models.DateTimeField(auto_now_add=True)),
                ('key_enabled', models.BooleanField(default=False)),
                ('remote_addr', models.CharField(max_length=255)),
                ('request_method', models.CharField(max_length=8)),
                ('absolute_uri', models.TextField()),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Key',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=16)),
                ('value', models.CharField(unique=True, max_length=16)),
                ('enabled', models.BooleanField(default=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='auditlog',
            name='key',
            field=models.ForeignKey(to='apikeys.Key'),
            preserve_default=True,
        ),
    ]
