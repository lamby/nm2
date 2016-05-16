# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import backend.models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Key',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('fpr', backend.models.FingerprintField(unique=True, max_length=40, verbose_name='OpenPGP key fingerprint')),
                ('key', models.TextField(verbose_name='ASCII armored key material')),
                ('key_updated', models.DateTimeField(verbose_name='Datetime when the key material was downloaded')),
                ('check_sigs', models.TextField(verbose_name='gpg --check-sigs results', blank=True)),
                ('check_sigs_updated', models.DateTimeField(null=True, verbose_name='Datetime when the check_sigs data was computed')),
            ],
        ),
    ]
