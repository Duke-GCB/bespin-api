# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-12-12 18:56


from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0040_auto_20171211_1914'),
    ]

    operations = [
        migrations.RenameField(
            model_name='job',
            old_name='volume_mounts',
            new_name='vm_volume_mounts',
        ),
    ]
