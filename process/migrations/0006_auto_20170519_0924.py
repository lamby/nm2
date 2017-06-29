# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0005_auto_20170519_0833'),
    ]

    operations = [
        migrations.AlterField(
            model_name='process',
            name='applying_for',
            field=models.CharField(max_length=20, verbose_name='target status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dd_r', 'DD, removed')]),
        ),
    ]
