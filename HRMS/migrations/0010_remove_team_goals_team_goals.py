# Generated by Django 5.1.5 on 2025-05-28 15:05

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('HRMS', '0009_feedback_status'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='team',
            name='goals',
        ),
        migrations.CreateModel(
            name='TEAM_GOALS',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('title', models.TextField(max_length=200)),
                ('description', models.TextField()),
                ('target_date', models.DateField()),
                ('created_date', models.DateField(auto_now_add=True)),
                ('status', models.TextField(choices=[('Not Started', 'not_started'), ('In Progress', 'in_progress'), ('Completed', 'completed'), ('On Hold', 'on_hold')], default='Not Started')),
                ('priority', models.TextField(choices=[('Low', 'low'), ('Medium', 'medium'), ('High', 'high'), ('Critical', 'critical')], default='Medium')),
                ('progress_percentage', models.IntegerField(default=0)),
                ('notes', models.TextField(blank=True, default='')),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='HRMS.manager')),
                ('team', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_goals', to='HRMS.team')),
            ],
            options={
                'verbose_name': 'Team Goal',
                'verbose_name_plural': 'Team Goals',
                'ordering': ['-created_date'],
            },
        ),
    ]
