from __future__ import print_function, unicode_literals

from datetime import timedelta

from django.utils.text import slugify
from django.utils.timezone import now

from .. import conf

################################################################


def get_grace():
    """
    Get the current grace period.
    """
    return conf.get("grace_days")


################################################################


def slug_autonumber(slug):
    n = None
    replace = False
    try:
        main, last = slug.rsplit("-", 1)
    except ValueError:
        # no dashes
        n = 1
        main = slug
        last = ""
    if n is None:
        try:
            n = int(last)
        except ValueError:
            # last is not an integer
            n = 1
        else:
            replace = True
    result = main
    if not replace:
        result += "-" + last
    result += "-{0}".format(n + 1)
    return slugify(result)


################################################################


def old_examfiles_for_course(course, dt=None):
    """
    Returns a queryset of old exam files for a course.
    This incorporates several filters:
        * exam file is active,
        * exam is active, public, and in the past,
        * exam is tied to the given course.
    """
    from ..models import ExamFile

    if dt is None:
        dt = now().replace(hour=0, minute=0, second=0, microsecond=0)
    holding = conf.get("old_exams_holding_days")
    dt -= timedelta(days=holding)
    return ExamFile.objects.filter(
        active=True,
        public=True,
        exam__active=True,
        exam__public=True,
        exam__dtstart__lt=dt,
        exam__sections__course=course,
    ).distinct()


################################################################


def all_examfiles_for_course(course):
    """
    Returns a queryset of old exam files for a course.
    This incorporates several filters:
        * exam file is active,
        * exam is active, and
        * exam is tied to the given course.
    """
    from ..models import ExamFile

    return ExamFile.objects.filter(
        active=True, exam__active=True, exam__sections__course=course
    ).distinct()


################################################################
