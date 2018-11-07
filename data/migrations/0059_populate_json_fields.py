# -*- coding: utf-8 -*-
# Generated by Django 1.10.1 on 2018-11-05 17:05
from __future__ import unicode_literals

from django.db import migrations
import json


def populate_json_fields(apps, schema_editor):
    converting_fields = [
        # class              source field   destination field, default string value
        ("WorkflowVersion", "fields_json", "fields", '[]'),
        ("WorkflowConfiguration", "system_job_order_json", "system_job_order", '{}'),
    ]
    for converting_field in converting_fields:
        class_name, source_field, dest_field, default_string_value = converting_field
        Model = apps.get_model("data", class_name)
        for obj in Model.objects.all():
            json_str = getattr(obj, source_field)
            if not json_str:
                json_str = default_string_value
            setattr(obj, dest_field, json.loads(json_str))
            obj.save()


class Migration(migrations.Migration):

    dependencies = [
        ('data', '0058_auto_20181105_1704'),
    ]

    operations = [
        migrations.RunPython(populate_json_fields, migrations.RunPython.noop),
    ]
