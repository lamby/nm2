# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0020_auto_20170519_0833'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='status',
            field=models.CharField(max_length=20, verbose_name='current status in the project', choices=[('dc', 'Debian Contributor'), ('dc_ga', 'Debian Contributor, with guest account'), ('dm', 'Debian Maintainer'), ('dm_ga', 'Debian Maintainer, with guest account'), ('dd_u', 'Debian Developer, uploading'), ('dd_nu', 'Debian Developer, non-uploading'), ('dd_e', 'Debian Developer, emeritus'), ('dd_r', 'Debian Developer, removed')]),
        ),
        migrations.AlterField(
            model_name='process',
            name='applying_as',
            field=models.CharField(max_length=20, verbose_name='original status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dd_r', 'DD, removed')]),
        ),
        migrations.AlterField(
            model_name='process',
            name='applying_for',
            field=models.CharField(max_length=20, verbose_name='target status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dd_r', 'DD, removed')]),
        ),
    ]
