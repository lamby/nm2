# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0007_auto_20160516_1227'),
    ]

    operations = [
        migrations.RenameField(
            model_name='fingerprint',
            old_name='user',
            new_name='person',
        ),
    ]
