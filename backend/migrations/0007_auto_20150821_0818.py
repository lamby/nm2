# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0006_am_fd_comment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='username',
            field=models.CharField(help_text='Debian SSO username', unique=True, max_length=255),
            preserve_default=True,
        ),
    ]
