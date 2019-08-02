"""
Copy the sections and room locations of an existing exam.
"""
from __future__ import print_function, unicode_literals

from pprint import pprint
from random import random

from exams.models import Exam, ExamLocation

from ..signals import exam_m2m_changed_handler
from .schedule import datetime_input, integer_input, model_choice_input

HELP_TEXT = __doc__.strip()
DJANGO_COMMAND = "main"
USE_ARGPARSE = True
OPTION_LIST = ((["exam_pk"], {"help": "Primary key of source exam"}),)


def print_exam_detail(exam):
    for f in [f.name for f in exam._meta.fields]:
        print(f + "\t" + "{}".format(getattr(exam, f)))
    print()


def get_copy_info(old_exam):
    """
    Get the additional information required for a copy.
    """
    print()
    print("NEW EXAM INFO")
    print()
    result = {}
    result["verbose_name"] = input('Exam Name (e.g., "Midterm 2"): ').strip()
    result["type"] = old_exam.type
    result["slug"] = "-TMP-save-fix-" + "{}".format(random())

    result["dtstart"] = datetime_input(
        "Enter the exam start date and time [YYYY-MM-DD hh:mm]: "
    )
    result["duration"] = old_exam.duration
    print()
    return result


def do_copy(old_exam):  # sections, room_assignments, public):
    """
    Save this solution to the database, prompting for additional information.
    """
    info = get_copy_info(old_exam)
    info["public"] = old_exam.public
    print("Exam Info:")
    pprint(info)
    resp = input("Are you sure you want to copy? [y/N] ").strip().lower()
    if resp not in ["y", "ye", "yes"]:
        return

    exam = Exam(**info)
    exam.save()
    for s in old_exam.sections.all():
        exam.sections.add(s)
    exam.slug = "-save-fix-" + "{}".format(random())
    exam.save()
    # for some reason, this signal does not fire, so call it manually.
    exam_m2m_changed_handler(
        sender="exams.cli.copy:do_copy()",
        instance=exam,
        action="post_add",
        reverse=False,
        model=Exam,
        pk_set=exam.sections.values_list("pk", flat=True),
    )

    loc_info = {"exam": exam}

    for old_loc in old_exam.examlocation_set.all():
        loc_info["location"] = old_loc.location
        loc_info["start_letter"] = old_loc.start_letter
        loc = ExamLocation(**loc_info)
        loc.save()

    print("SAVE COMPLETE")


def main(options, args):

    exam = Exam.objects.get(pk=options["exam_pk"])
    print_exam_detail(exam)
    do_copy(exam)
