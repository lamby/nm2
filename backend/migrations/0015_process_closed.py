# -*- coding: utf-8 -*-


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('backend', '0014_auto_20160620_0025'),
    ]

    operations = [
        migrations.AddField(
            model_name='process',
            name='closed',
            field=models.DateTimeField(help_text='Date the process was closed, or NULL if still open', null=True, blank=True),
        ),
    ]
