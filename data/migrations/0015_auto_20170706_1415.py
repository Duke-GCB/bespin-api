# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-07-06 14:15
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0014_auto_20170615_1855'),
    ]

    operations = [
        migrations.CreateModel(
            name='JobToken',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=255, unique=True)),
            ],
        ),
        migrations.AddField(
            model_name='job',
            name='run_token',
            field=models.OneToOneField(help_text='Token that allows permission for a job to be run', null=True, on_delete=django.db.models.deletion.CASCADE, to='data.JobToken'),
        ),
    ]
