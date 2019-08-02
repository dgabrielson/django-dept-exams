# -*- coding: utf-8 -*-
# Generated by Django 1.11.6 on 2017-10-17 18:45
from __future__ import unicode_literals

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("exams", "0004_auto_20170602_1055")]

    operations = [
        migrations.AlterField(
            model_name="exam",
            name="created",
            field=models.DateTimeField(auto_now_add=True, verbose_name="creation time"),
        ),
        migrations.AlterField(
            model_name="exam",
            name="dtstart",
            field=models.DateTimeField(verbose_name="date and start time"),
        ),
        migrations.AlterField(
            model_name="exam",
            name="duration",
            field=models.PositiveSmallIntegerField(
                help_text="Duration of the exam, in minutes"
            ),
        ),
        migrations.AlterField(
            model_name="exam",
            name="modified",
            field=models.DateTimeField(
                auto_now=True, verbose_name="last modification time"
            ),
        ),
        migrations.AlterField(
            model_name="exam",
            name="public",
            field=models.BooleanField(
                default=False, help_text="Set this to advertise the exam"
            ),
        ),
        migrations.AlterField(
            model_name="exam",
            name="slug",
            field=models.SlugField(
                blank=True,
                help_text='A url fragment to identify the exam, e.g., "stat1000-midterm-1-f11", (leave blank to set automatically)',
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="exam",
            name="student_count",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Set this to override the number of students writing (for sign-in sheets)",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="exam",
            name="verbose_name",
            field=models.CharField(
                help_text='The name of the exam, usually "Midterm", "Midterm 1", "Midterm 2" or "Final Exam"',
                max_length=64,
            ),
        ),
        migrations.AlterField(
            model_name="examfile",
            name="created",
            field=models.DateTimeField(auto_now_add=True, verbose_name="creation time"),
        ),
        migrations.AlterField(
            model_name="examfile",
            name="modified",
            field=models.DateTimeField(
                auto_now=True, verbose_name="last modification time"
            ),
        ),
        migrations.AlterField(
            model_name="examfile",
            name="solutions",
            field=models.BooleanField(
                default=False,
                help_text="Set this when the attached file contains worked solutions",
            ),
        ),
        migrations.AlterField(
            model_name="examfile",
            name="the_file",
            field=models.FileField(upload_to="%Y/%m/%d"),
        ),
        migrations.AlterField(
            model_name="examfile",
            name="verbose_name",
            field=models.CharField(help_text="A title for the file", max_length=64),
        ),
        migrations.AlterField(
            model_name="examlocation",
            name="created",
            field=models.DateTimeField(auto_now_add=True, verbose_name="creation time"),
        ),
        migrations.AlterField(
            model_name="examlocation",
            name="location",
            field=models.ForeignKey(
                help_text='If you require a room not in this list, please contact <a href="mailto:e">w</a>',
                on_delete=django.db.models.deletion.PROTECT,
                to="places.ClassRoom",
            ),
        ),
        migrations.AlterField(
            model_name="examlocation",
            name="modified",
            field=models.DateTimeField(
                auto_now=True, verbose_name="last modification time"
            ),
        ),
        migrations.AlterField(
            model_name="examlocation",
            name="start_letter",
            field=models.CharField(
                blank=True,
                help_text="Always use lowercase (leave this blank if there is only one room)",
                max_length=8,
            ),
        ),
        migrations.AlterField(
            model_name="examtype",
            name="created",
            field=models.DateTimeField(auto_now_add=True, verbose_name="creation time"),
        ),
        migrations.AlterField(
            model_name="examtype",
            name="modified",
            field=models.DateTimeField(
                auto_now=True, verbose_name="last modification time"
            ),
        ),
        migrations.AlterField(
            model_name="examtype",
            name="slug",
            field=models.SlugField(
                help_text="A url fragment to identify the exam type", unique=True
            ),
        ),
        migrations.AlterField(
            model_name="examtype",
            name="verbose_name",
            field=models.CharField(
                help_text="The name of the exam type", max_length=64
            ),
        ),
    ]
