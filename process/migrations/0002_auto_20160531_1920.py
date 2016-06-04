# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0001_squashed_0014_auto_20160530_0851'),
    ]

    operations = [
        migrations.AlterField(
            model_name='statement',
            name='uploaded_by',
            field=models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, help_text='Person who uploaded the statement'),
        ),
        migrations.AlterField(
            model_name='statement',
            name='uploaded_time',
            field=models.DateTimeField(help_text='When the statement has been uploaded'),
        ),
    ]
