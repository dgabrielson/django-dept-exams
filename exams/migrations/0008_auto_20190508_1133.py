# Generated by Django 2.2.1 on 2019-05-08 16:33

import exams.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("exams", "0007_auto_20190311_0940")]

    operations = [
        migrations.AddField(
            model_name="examfile",
            name="public",
            field=models.BooleanField(
                choices=[(True, "Public"), (False, "Restricted")], default=True
            ),
        ),
        migrations.AlterField(
            model_name="exam",
            name="dtstart",
            field=models.DateTimeField(
                help_text="Dates are YYYY-MM-DD.  Time is in 24-hour notation.",
                validators=[exams.validators.validate_reasonable_time],
                verbose_name="date and start time",
            ),
        ),
        migrations.AlterField(
            model_name="exam",
            name="public",
            field=models.BooleanField(
                choices=[(True, "Advertise"), (False, "Hidden")],
                default=False,
                help_text="Set this to advertise the exam",
            ),
        ),
    ]