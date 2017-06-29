# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0013_auto_20160530_0837'),
    ]

    operations = [
        migrations.RenameField(
            model_name='process',
            old_name='review_requested_by',
            new_name='frozen_by',
        ),
        migrations.RenameField(
            model_name='process',
            old_name='review_requested_time',
            new_name='frozen_time',
        ),
    ]
