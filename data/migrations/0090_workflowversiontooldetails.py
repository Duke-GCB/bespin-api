# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2019-05-02 19:56
from __future__ import unicode_literals

import django.contrib.postgres.fields.jsonb
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0089_workflow_state'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorkflowVersionToolDetails',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('details', django.contrib.postgres.fields.jsonb.JSONField(help_text='JSON array of tool details and versions')),
                ('workflow_version', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='tool_details', to='data.WorkflowVersion')),
            ],
        ),
    ]