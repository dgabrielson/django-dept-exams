"""
Search exams
"""
from __future__ import print_function, unicode_literals

from exams.models import Exam

HELP_TEXT = __doc__.strip()
DJANGO_COMMAND = "main"
USE_ARGPARSE = True
OPTION_LIST = (
    (
        ["--all"],
        dict(
            action="store_true",
            default=False,
            help="Search all exams, not just active ones",
        ),
    ),
    (
        ["--include-past"],
        dict(
            action="store_true",
            default=False,
            help="Search all exams, not just current/future ones",
        ),
    ),
    (
        ["--public-only"],
        dict(action="store_true", default=False, help="Only search public exams"),
    ),
    (["search_terms"], {"nargs": "+", "help": "Search terms"}),
)


def print_exam(exam):
    print("{}\t{}".format(exam.pk, exam.slug))


def main(options, args):

    args = options["search_terms"]

    if options["all"]:
        exam_list = Exam.objects.all()
    else:
        exam_list = Exam.objects.active()
    if not options["include_past"]:
        exam_list = exam_list.future()
    if options["public_only"]:
        exam_list = exam_list.public()

    exam_list = exam_list.search(*args)

    for exam in exam_list:
        print_exam(exam)
