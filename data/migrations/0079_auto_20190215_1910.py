# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2019-02-15 19:10
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0078_auto_20190215_1639'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='VMSettings',
            new_name='JobSettings',
        ),
        migrations.AlterModelOptions(
            name='jobsettings',
            options={'verbose_name_plural': 'Job Settings Collections'},
        ),
    ]
