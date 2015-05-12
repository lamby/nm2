# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0004_auto_20150509_1544'),
    ]

    operations = [
        migrations.AlterField(
            model_name='person',
            name='status',
            field=models.CharField(max_length=20, verbose_name='current status in the project', choices=[('dc', 'Debian Contributor'), ('dc_ga', 'Debian Contributor, with guest account'), ('dm', 'Debian Maintainer'), ('dm_ga', 'Debian Maintainer, with guest account'), ('dd_u', 'Debian Developer, uploading'), ('dd_nu', 'Debian Developer, non-uploading'), ('dd_e', 'Debian Developer, emeritus'), ('dm_e', 'Debian Maintainer, emeritus'), ('dd_r', 'Debian Developer, removed'), ('dm_r', 'Debian Maintainer, removed'), ('dc_ga_r', 'Debian Contributor, with closed guest account')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='process',
            name='applying_as',
            field=models.CharField(max_length=20, verbose_name='original status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dm_e', 'DM, emeritus'), ('dd_r', 'DD, removed'), ('dm_r', 'DM, removed'), ('dc_ga_r', 'DC+closed acct.')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='process',
            name='applying_for',
            field=models.CharField(max_length=20, verbose_name='target status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dm_e', 'DM, emeritus'), ('dd_r', 'DD, removed'), ('dm_r', 'DM, removed'), ('dc_ga_r', 'DC+closed acct.')]),
            preserve_default=True,
        ),
    ]
