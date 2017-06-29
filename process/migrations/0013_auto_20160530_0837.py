# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0012_auto_20160530_0832'),
    ]

    operations = [
        migrations.RenameField(
            model_name='process',
            old_name='submitted_by',
            new_name='review_requested_by',
        ),
        migrations.RenameField(
            model_name='process',
            old_name='submitted_time',
            new_name='review_requested_time',
        ),
    ]
