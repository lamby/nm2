# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0016_oldprocessclosed'),
    ]

    operations = [
        migrations.AddField(
            model_name='person',
            name='email_ldap',
            field=models.EmailField(max_length=254, verbose_name='LDAP forwarding email address', blank=True),
        ),
    ]
