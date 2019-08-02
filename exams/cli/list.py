"""
List exams
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
            help="List all exams, not just current ones",
        ),
    ),
    (
        ["--public-only"],
        dict(action="store_true", default=False, help="Only list public exams"),
    ),
)


def print_exam(exam):
    print("{}\t{}".format(exam.pk, exam.slug))


def main(options, args):

    if options["all"]:
        exam_list = Exam.objects.all()
    else:
        exam_list = Exam.objects.active()

    if options["public_only"]:
        exam_list = exam_list.public()

    for exam in exam_list:
        print_exam(exam)
