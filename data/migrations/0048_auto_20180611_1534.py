# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2018-06-11 15:34


from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0047_auto_20180419_1330'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ddsusercredential',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bespin_api_user', to=settings.AUTH_USER_MODEL),
        ),
    ]
