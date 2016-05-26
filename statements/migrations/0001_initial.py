# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('backend', '0012_auto_20160520_1030'),
    ]

    operations = [
        migrations.CreateModel(
            name='Statement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=16, verbose_name='Statement type', choices=[('sc_dmup', 'SC/DFSG/DMUP agreement'), ('advocacy', 'Advocacy')])),
                ('statement', models.TextField(verbose_name='Signed statement', blank=True)),
                ('statement_verified', models.DateTimeField(help_text='When the statement has been verified to have valid wording (NULL if it has not)', null=True)),
                ('fpr', models.ForeignKey(help_text='Fingerprint used to verify the statement', to='backend.Fingerprint')),
                ('uploaded_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, help_text='Person who uploaded the statement', null=True)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='statement',
            unique_together=set([('fpr', 'type')]),
        ),
    ]
