# -*- coding: utf-8 -*-


from django.db import migrations, models
import django.utils.timezone
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('backend', '0012_auto_20160520_1030'),
    ]

    operations = [
        migrations.CreateModel(
            name='Log',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('is_public', models.BooleanField(default=False)),
                ('logdate', models.DateTimeField(default=django.utils.timezone.now)),
                ('logtext', models.TextField(default='', blank=True)),
                ('changed_by', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Process',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('applying_for', models.CharField(max_length=20, verbose_name='target status', choices=[('dc', 'DC'), ('dc_ga', 'DC+account'), ('dm', 'DM'), ('dm_ga', 'DM+account'), ('dd_u', 'DD, upl.'), ('dd_nu', 'DD, non-upl.'), ('dd_e', 'DD, emeritus'), ('dm_e', 'DM, emeritus'), ('dd_r', 'DD, removed'), ('dm_r', 'DM, removed'), ('dc_ga_r', 'DC+closed acct.')])),
                ('completed', models.DateTimeField(help_text='Date the process was reviewed and considered complete, or NULL if not complete', null=True)),
                ('closed', models.DateTimeField(help_text='Date the process was closed, or NULL if still open', null=True)),
                ('fd_comment', models.TextField(default='', verbose_name='Front Desk comments', blank=True)),
                ('person', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Requirement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('type', models.CharField(max_length=16, verbose_name='Requirement type', choices=[('intent', 'Declaration of intent'), ('sc_dmup', 'SC/DFSG/DMUP agreement'), ('advocate', 'Advocate'), ('keycheck', 'Key consistency checks'), ('am_ok', 'Application Manager report')])),
                ('is_ok', models.BooleanField(default=False)),
                ('process', models.ForeignKey(related_name='requirements', to='process.Process')),
            ],
        ),
        migrations.CreateModel(
            name='Statement',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('statement', models.TextField(verbose_name='Signed statement', blank=True)),
                ('statement_verified', models.DateTimeField(help_text='When the statement has been verified to have valid wording (NULL if it has not)', null=True)),
                ('fpr', models.ForeignKey(related_name='+', to='backend.Fingerprint', help_text='Fingerprint used to verify the statement')),
                ('requirement', models.ForeignKey(related_name='statements', to='process.Requirement')),
                ('uploaded_by', models.ForeignKey(related_name='+', to=settings.AUTH_USER_MODEL, help_text='Person who uploaded the statement', null=True)),
            ],
        ),
        migrations.AddField(
            model_name='log',
            name='process',
            field=models.ForeignKey(related_name='log', to='process.Process'),
        ),
        migrations.AlterUniqueTogether(
            name='requirement',
            unique_together=set([('process', 'type')]),
        ),
    ]
