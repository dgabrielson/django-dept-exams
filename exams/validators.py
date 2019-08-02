from datetime import time

from django.core.exceptions import ValidationError
from django.utils.timezone import localtime

from . import conf


def validate_reasonable_time(value):
    """
    Straight wall time check.
    Here we need to be careful since value is probably in UTC.
    """
    earliest = conf.get("exams:dtstart:reasonable-time:earliest")
    earliest = time(*earliest)
    latest = conf.get("exams:dtstart:reasonable-time:latest")
    latest = time(*latest)
    wall = localtime(value)
    wall_time = wall.time()
    if not (earliest <= wall_time <= latest):
        raise ValidationError("The time is not reasonable")
