# Generated by Django 2.1.5 on 2019-05-09 13:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0004_pass_history_year_month_day'),
    ]

    operations = [
        migrations.AddField(
            model_name='employee',
            name='dt_begin_1',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='dt_begin_2',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='dt_begin_3',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='dt_end_1',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='dt_end_2',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='employee',
            name='dt_end_3',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]