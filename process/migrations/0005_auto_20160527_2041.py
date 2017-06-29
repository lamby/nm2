# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('process', '0004_auto_20160527_1938'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='requirement',
            name='is_ok',
        ),
        migrations.AddField(
            model_name='requirement',
            name='approved_by',
            field=models.ForeignKey(blank=True, to=settings.AUTH_USER_MODEL, help_text='Set to the person that reviewed and approved this requirement', null=True),
        ),
    ]
