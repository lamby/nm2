# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0008_amassignment'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='amassignment',
            options={'ordering': ['-assigned_by']},
        ),
        migrations.AlterField(
            model_name='amassignment',
            name='unassigned_by',
            field=models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, help_text='Person who did the unassignment', null=True),
        ),
        migrations.AlterField(
            model_name='amassignment',
            name='unassigned_time',
            field=models.DateTimeField(help_text='When the unassignment happened', null=True, blank=True),
        ),
    ]
