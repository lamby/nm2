# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0006_requirement_approved_time'),
    ]

    operations = [
        migrations.AddField(
            model_name='log',
            name='action',
            field=models.CharField(help_text='Action performed with this log entry, if any', max_length=16, blank=True),
        ),
    ]
