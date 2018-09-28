# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-08-11 18:39


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0024_job_vm_volume_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='cleanup_vm',
            field=models.BooleanField(default=True, help_text='Should the VM and Volume be deleted upon job completion'),
        ),
    ]
