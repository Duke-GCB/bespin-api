# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2017-05-26 15:13


from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0007_jobanswerset_job_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='jobquestionnaire',
            name='user_fields',
            field=models.TextField(help_text='JSON containing the array of fields required by the user when providing a job answer set.', null=True),
        ),
    ]
