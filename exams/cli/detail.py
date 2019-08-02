"""
Print details of an existing exam.
"""
from __future__ import print_function, unicode_literals

from pprint import pprint
from random import random

from exams.models import Exam, ExamLocation

from ..signals import exam_m2m_changed_handler
from .schedule import datetime_input, integer_input, model_choice_input

HELP_TEXT = __doc__.strip()
DJANGO_COMMAND = "main"
OPTION_LIST = ((["pk"], {"nargs": "+", "help": "Primary key for exam(s)"}),)


def print_exam_detail(exam):
    for f in [f.name for f in exam._meta.fields]:
        print(f + "\t" + "{}".format(getattr(exam, f)))
    print(
        "sections\t"
        + ",".join(["{}".format(v) for v in exam.sections.values_list("pk", flat=True)])
    )
    # print('examlocation_set\t' + ','.join(['{}'.format(v) for v in exam.examlocation_set.values_list('pk', flat=True)]))
    print(
        "classrooms\t"
        + ",".join(
            [
                "{}".format(v)
                for v in exam.examlocation_set.values_list("location__pk", flat=True)
            ]
        )
    )
    for loc in exam.examlocation_set.active():
        print(
            "\t{loc.location}\t{loc.start_letter}\t{loc.location.capacity}\t{loc.student_count}\t{loc.occupancy_percent}%".format(
                loc=loc
            )
        )
    print()


def main(options, args):
    args = options.get("pk")
    if len(args) < 1:
        print("You need to specify one or more primary keys")
        return

    for arg in args:
        exam = Exam.objects.get(pk=arg)
        print_exam_detail(exam)
