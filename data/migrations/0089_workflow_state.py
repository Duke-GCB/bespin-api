# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2019-04-18 15:01
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0088_merge_20190404_1819'),
    ]

    operations = [
        migrations.AddField(
            model_name='workflow',
            name='state',
            field=models.CharField(choices=[('A', 'Active'), ('D', 'Deprecated')], default='A', help_text='State of the workflow', max_length=1),
        ),
    ]
