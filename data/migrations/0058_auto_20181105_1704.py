# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2018-11-05 17:04
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0057_auto_20181101_1314'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflowconfiguration',
            name='system_job_order',
            field=django.contrib.postgres.fields.jsonb.JSONField(help_text='Dictionary containing the portion of the job order specified by system.', null=True),
        ),
        migrations.AddField(
            model_name='workflowversion',
            name='fields',
            field=django.contrib.postgres.fields.jsonb.JSONField(help_text='Array of fields required by this workflow.', null=True),
        ),
    ]
