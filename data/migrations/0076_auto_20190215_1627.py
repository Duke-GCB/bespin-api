# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2019-02-15 16:27
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0075_auto_20190124_1619'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='VMFlavor',
            new_name='JobFlavor',
        ),
    ]
