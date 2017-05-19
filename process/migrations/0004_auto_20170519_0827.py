# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0003_auto_20160620_1316'),
    ]

    operations = [
        migrations.AlterField(
            model_name='process',
            name='applying_for',
            field=models.CharField(max_length=20, verbose_name='target status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dd_r', 'DD, removed'), ('dm_r', 'DM, removed'), ('dc_ga_r', 'DC+closed acct.')]),
        ),
    ]
