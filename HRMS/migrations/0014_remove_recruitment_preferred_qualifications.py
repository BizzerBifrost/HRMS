# Generated by Django 5.1.5 on 2025-06-11 16:05

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('HRMS', '0013_remove_recruitment_budget_allocated'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='recruitment',
            name='preferred_qualifications',
        ),
    ]
