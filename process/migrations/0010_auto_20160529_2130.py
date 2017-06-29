# -*- coding: utf-8 -*-


from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('process', '0009_auto_20160529_2128'),
    ]

    operations = [
        migrations.AlterField(
            model_name='statement',
            name='uploaded_by',
            field=models.ForeignKey(related_name='+', default=0, to=settings.AUTH_USER_MODEL, help_text='Person who uploaded the statement'),
            preserve_default=False,
        ),
    ]
