# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("classes", "0001_initial"), ("places", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Exam",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="creation time"
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        auto_now=True, verbose_name="last modification time"
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text='A url fragment to identify the exam, e.g., "stat1000-midterm-1-f11", (leave blank to set automatically)',
                        unique=True,
                        blank=True,
                    ),
                ),
                (
                    "verbose_name",
                    models.CharField(help_text="The name of the exam", max_length=64),
                ),
                ("dtstart", models.DateTimeField(verbose_name="date and start time")),
                (
                    "duration",
                    models.PositiveSmallIntegerField(
                        help_text="Duration of the exam, in minutes"
                    ),
                ),
                (
                    "public",
                    models.BooleanField(
                        default=False, help_text="Set this to advertise the exam"
                    ),
                ),
                ("sections", models.ManyToManyField(to="classes.Section")),
            ],
            options={"ordering": ["dtstart"]},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="ExamFile",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="creation time"
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        auto_now=True, verbose_name="last modification time"
                    ),
                ),
                (
                    "verbose_name",
                    models.CharField(help_text="A title for the file", max_length=64),
                ),
                ("the_file", models.FileField(upload_to="%Y/%m/%d")),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, to="exams.Exam"
                    ),
                ),
            ],
            options={"ordering": ["exam", "verbose_name"]},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="ExamLocation",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="creation time"
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        auto_now=True, verbose_name="last modification time"
                    ),
                ),
                (
                    "start_letter",
                    models.CharField(
                        help_text="Always use lowercase (leave this blank if there is only one room)",
                        max_length=8,
                        blank=True,
                    ),
                ),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, to="exams.Exam"
                    ),
                ),
                (
                    "location",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        help_text='If you require a room not in this list, please contact <a href="mailto:a">D</a>',
                        to="places.ClassRoom",
                    ),
                ),
            ],
            options={"ordering": ["exam", "start_letter"]},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="ExamSolution",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="creation time"
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        auto_now=True, verbose_name="last modification time"
                    ),
                ),
                (
                    "verbose_name",
                    models.CharField(help_text="A title for the file", max_length=64),
                ),
                ("the_file", models.FileField(upload_to="%Y/%m/%d")),
                (
                    "exam",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE, to="exams.Exam"
                    ),
                ),
            ],
            options={"ordering": ["exam", "verbose_name"]},
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name="ExamType",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("active", models.BooleanField(default=True)),
                (
                    "created",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="creation time"
                    ),
                ),
                (
                    "modified",
                    models.DateTimeField(
                        auto_now=True, verbose_name="last modification time"
                    ),
                ),
                (
                    "slug",
                    models.SlugField(
                        help_text="A url fragment to identify the exam type",
                        unique=True,
                    ),
                ),
                (
                    "verbose_name",
                    models.CharField(
                        help_text="The name of the exam type", max_length=64
                    ),
                ),
            ],
            options={},
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name="exam",
            name="type",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE, to="exams.ExamType"
            ),
            preserve_default=True,
        ),
    ]
