# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0003_auto_20150829_0905'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='person',
            name='fpr',
        ),
    ]
