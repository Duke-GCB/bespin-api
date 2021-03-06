# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2019-01-24 16:12
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0073_workflowversion_enable_ui'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jobquestionnaire',
            name='workflow_version',
            field=models.ForeignKey(help_text='Workflow that this questionaire is for', on_delete=django.db.models.deletion.CASCADE, related_name='questionnaires', to='data.WorkflowVersion'),
        ),
        migrations.AlterField(
            model_name='workflowversion',
            name='enable_ui',
            field=models.BooleanField(default=True, help_text='Should this workflow version be enabled in the web portal.'),
        ),
    ]
