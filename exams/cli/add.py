"""
Schedule an exam by supplying section ids and classroom ids.

Use this when you are not sure what room assignments are going to be.

Typically, you would:

./manage.py places list --classroom > ~/classrooms.txt
./manage.py classes section_list | grep STAT.1000.A > ~/sections.txt
# edit these files appropriately

# If you have a column of rooms from a spreadsheet:
while read line; do ./manage.py places list --classroom | grep "${line}" || echo 'NO MATCH' ${line} ; done << EOF > ~/sections.txt
# and paste the relevant column followed by CTRL+D.

# FINALLY:
./manage.py exams add --classrooms `cut -f 1 ~/classrooms.txt | tr '\\n' , ` --sections `cut -f 1 ~/sections.txt | tr '\\n' , `
"""
from __future__ import print_function, unicode_literals

import sys
from datetime import datetime
from math import ceil
from pprint import pprint
from random import random, shuffle

from classes.models import Section
from django.db import models
from django.utils.timezone import get_default_timezone, is_naive, make_aware
from places.models import ClassRoom
from students.models import Student_Registration

from ..models import Exam, ExamLocation, ExamType, exam_m2m_changed_handler

################################################################

################################################################
################################################################

HELP_TEXT = __doc__.strip()
DJANGO_COMMAND = "main"
USE_ARGPARSE = True
OPTION_LIST = (
    (
        ["--sections"],
        dict(help="A comma delimited or whitespace delimited list of sections"),
    ),
    (
        ["--classrooms"],
        dict(help="A comma delimited or whitespace delimited list of classrooms"),
    ),
    (
        ["--start-list"],
        dict(
            help="A comma delimited or whitespace delimited list of start letters for rooms"
        ),
    ),
    (
        ["--save"],
        dict(action="store_true", default=False, help="Actually save the results"),
    ),
    (
        ["--public"],
        dict(
            action="store_true",
            default=False,
            help="When saving, mark as public (no effect when not saving)",
        ),
    ),
    (["--verbose-name"], dict(help="A verbose name for this exam")),
    (["--type"], dict(help="The exam type for this exam")),
    (
        ["--dtstart"],
        dict(help="A start date and time for this exam (YYYY-MM-DD hh:mm)"),
    ),
    (["--duration"], dict(help="A duration for this exam")),
)

################################################################


def get_pks(s):
    """
    Convert a comma or whitespace delimited string into a list
    """
    s = s.strip().strip(",")  # strip out spurious delimiters
    if "," in s:
        return s.split(",")
    return s.split()  # split on whitespace


################################################################


def get_queryset_list(model, pk_string):
    """
    Return a list from queryset for the given model and primary key string
    Respect the order of the primary keys listed in the returned list.
    """
    if pk_string is None:
        return []
    return [model.objects.get(pk=pk) for pk in get_pks(pk_string)]


################################################################


def model_choice_input(queryset, prompt="selection: ", default=None):
    """
    Do a text mode selection from a queryset of choices.
    """
    #     if default:
    #         prompt += ' [default: "{0}"] '.format(default)
    counter = 1
    response_map = {}
    for item in queryset:
        print("  [%d]" % counter, item)
        response_string = "%d" % counter
        response_map[response_string] = item
        counter += 1
    if default in response_map:
        return response_map[default]
    while True:
        response = input(prompt).strip()
        if response in response_map:
            return response_map[response]
        print("** Invalid selection, try again.")


################################################################


def datetime_input(prompt="enter a date and time [YYYY-MM-DD hh:mm]: ", default=None):
    """
    Enter and validate a datetime input
    """

    def _make_dt_proper(s):
        try:
            value = datetime.strptime(s, "%Y-%m-%d %H:%M")
        except ValueError:
            value = None
        if value is not None:
            if is_naive(value):
                value = make_aware(value, get_default_timezone())
        return value

    if default:
        # prompt += ' [default: "{0}"] '.format(default)
        value = _make_dt_proper(default)
        if value is not None:
            return value
    while True:
        resp = input(prompt).strip()
        value = _make_dt_proper(resp)
        if value is not None:
            return value
        print("** %r: not in the correct datetime format. Try again." % resp)


################################################################


def integer_input(prompt="enter an integer value: ", default=None):
    """
    Enter and validate an integer
    """

    def _make_int_proper(s):
        try:
            value = int(s)
        except ValueError:
            value = None
        return value

    if default:
        # prompt += ' [default: "{0}"] '.format(default)
        value = _make_int_proper(default)
        if value is not None:
            return value
    while True:
        resp = input(prompt).strip()
        value = _make_int_proper(resp)
        if value is not None:
            return value
        print("** %r: not an integer. Try again." % resp)


################################################################


def string_input(prompt, default=None):
    if default:
        return default

    result = input(prompt).strip()
    if not result:
        result = default
    return result


################################################################


def get_save_info(initial=None):
    """
    Get the additional information required for a save.
    """
    print()
    print("EXAM INFO")
    print()
    if initial is None:
        initial = {}
    result = {}
    result["verbose_name"] = string_input(
        "Exam Name: ", initial.get("verbose_name", "")
    )
    result["type"] = model_choice_input(
        ExamType.objects.filter(active=True), "Exam type: ", initial.get("type", "")
    )
    result["slug"] = "-save-fix-" + "{}".format(random())

    result["dtstart"] = datetime_input(
        "Enter the exam start date and time [YYYY-MM-DD hh:mm]: ",
        initial.get("dtstart", ""),
    )
    result["duration"] = integer_input(
        "Enter the exam duration (minutes): ", initial.get("duration", "")
    )
    print()
    return result


################################################################


def do_save(sections, room_assignments, public, initial=None):
    """
    Save this solution to the database, prompting for additional information.
    """
    info = get_save_info(initial)
    info["public"] = public
    print("Exam Info:")
    pprint(info)
    resp = input("Are you sure you want to save? [y/N] ").strip().lower()
    if resp not in ["y", "ye", "yes"]:
        return

    exam = Exam(**info)
    exam.save()

    exam.sections = sections
    # for some reason, this signal does not fire, so call it manually.
    exam_m2m_changed_handler(
        sender="exams.cli.schedule:do_save()",
        instance=exam,
        action="post_add",
        reverse=False,
        model=Exam,
        pk_set=[s.pk for s in sections],
    )
    loc_info = {"exam": exam}

    for location, start_letter in room_assignments:
        loc_info["location"] = location
        loc_info["start_letter"] = start_letter
        loc = ExamLocation(**loc_info)
        loc.save()

    print("SAVE COMPLETE")


################################################################


def main(options, args):
    if options["sections"] is None:
        print("You must supply  --sections")
        return
    if args:
        print("This CLI takes no arguments")
        return

    classrooms = get_queryset_list(ClassRoom, options["classrooms"])
    sections = get_queryset_list(Section, options["sections"])
    start_list = get_pks(options.get("start-list", ""))

    if options["save"]:
        do_save(
            sections, zip(classrooms, start_list), options["public"], initial=options
        )


################################################################
