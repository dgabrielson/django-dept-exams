from __future__ import print_function, unicode_literals

import datetime

from django.utils.timezone import now

from . import conf
from .models import Exam


def get_queryset(days=None, max_count=None, startfrom_dtstart=None, upto_dtstart=None):
    if days is None:
        days = conf.get("upcoming_days")
    if startfrom_dtstart is None:
        n = now()
    else:
        n = startfrom_dtstart
    start = n - datetime.timedelta(hours=3)
    if upto_dtstart is None:
        finish = n + datetime.timedelta(days=days)
    else:
        finish = upto_dtstart
    object_list = Exam.objects.filter(
        active=True, public=True, dtstart__range=(start, finish)
    ).order_by("dtstart")
    if max_count is None:
        max_count = conf.get("upcoming_max_count")
    if max_count and (upto_dtstart is None):
        object_list = object_list[:max_count]
    return object_list


def upcoming_exams(request):
    """
    Returns upcoming exams.
    """
    return {"upcoming_exams": get_queryset()}


#
