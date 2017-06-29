# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0002_auto_20160531_1920'),
    ]

    operations = [
        migrations.AlterField(
            model_name='process',
            name='approved_time',
            field=models.DateTimeField(help_text='Date the process was reviewed and considered complete, or NULL if not yet reviewed', null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='process',
            name='closed',
            field=models.DateTimeField(help_text='Date the process was closed, or NULL if still open', null=True, blank=True),
        ),
    ]
