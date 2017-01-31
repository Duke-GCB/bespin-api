# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-01-21 20:15
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0027_auto_20170120_2132'),
    ]

    operations = [
        migrations.AlterField(
            model_name='jobanswer',
            name='kind',
            field=models.CharField(choices=[('string', 'Text'), ('dds_file', 'DukeDS File'), ('dds_output_directory', 'DukeDS Output Directory')], help_text='Determines child table associated with this answer.', max_length=30),
        ),
    ]
