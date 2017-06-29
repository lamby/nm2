# -*- coding: utf-8 -*-


from django.db import models, migrations
import backend.models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Fingerprint',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('fpr', backend.models.FingerprintField(unique=True, max_length=40, verbose_name='OpenPGP key fingerprint')),
                ('user', models.ForeignKey(related_name='fprs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'fingerprints',
            },
        ),
    ]
