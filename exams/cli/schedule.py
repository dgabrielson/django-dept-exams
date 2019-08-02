"""
Schedule an exam by supplying section ids and classroom ids.

Use this when you are not sure what room assignments are going to be.

Typically, you would:

./manage.py places list --classroom > ~/classrooms.txt
./manage.py classes section_list --course stat-1000 --term fall-2016 > ~/sections.txt
# edit these files appropriately

# If you have a column of rooms from a spreadsheet:
while read line; do ./manage.py places list --classroom | grep "${line}" || echo 'NO MATCH' ${line} ; done << EOF > ~/classrooms.txt
# and paste the relevant column followed by EOF

# FINALLY:
./manage.py exams schedule --classrooms $(cut -f 1 ~/classrooms.txt | tr '\\n' , ) --sections $(cut -f 1 ~/sections.txt | tr '\\n' , )
# -or-
./manage.py exams schedule --classrooms $(cut -f 1 ~/classrooms.txt | tr '\\n' , ) --sections $(cut -f 1 ~/sections.txt | tr '\\n' , ) --randomize --max-tries 1000
"""
from __future__ import print_function, unicode_literals

import sys
from datetime import datetime
from functools import reduce
from itertools import permutations
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
        ["--randomize"],
        dict(
            action="store_true",
            default=False,
            help="If given, the ordering of classrooms will be shuffled, "
            + "and multiple attempts will be made to find the best "
            + "order of rooms",
        ),
    ),
    (
        ["--permutations"],
        dict(
            action="store_true",
            default=False,
            help="If given, all possible classroom permutations will be checked to determine the best order (note: CTRL+C is handled gracefully)",
        ),
    ),
    (
        ["--bisection"],
        dict(
            action="store_true",
            default=False,
            help="If given, this will attempt to do room splits by the bisection-partition method",
        ),
    ),
    (
        ["--max-tries"],
        dict(
            type=int,
            default=100,
            help="The maximum number of tries that will be attempted, "
            + "only applicable with --randomize",
        ),
    ),
    (
        ["--max-ratio"],
        dict(
            type=float,
            default=0.5,
            help="The maximum occupancy ratio allowed in rooms, "
            + "only applicable with --bisection",
        ),
    ),
    (
        ["--best-score"],
        dict(
            type=int,
            default=2,
            help="The score at which we stop trying to find a better order "
            + "of rooms, only applicable with --randomize or --permutations"
            + " (6 is resonable if things need to be done very quickly)",
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
)

################################################################


class InvalidCutoff(Exception):
    """
    This one isn't going to work...
    """

    def __init__(self, fail, *args, **kwargs):
        self.fail = fail
        return super(InvalidCutoff, self).__init__(*args, **kwargs)


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
    return [model.objects.get(pk=pk) for pk in get_pks(pk_string)]


################################################################


def get_registrations(section_list):
    """
    Get the student registrations corresponing to the given section list
    """

    def registration_qs(**kwargs):
        return Student_Registration.objects.reg_list(
            good_standing=True, aurora_verified=True, **kwargs
        )

    def registration_check(section_list):
        count_list = [registration_qs(section=s).count() for s in section_list]
        is_zero_list = [c == 0 for c in count_list]
        if any(is_zero_list):
            if len(is_zero_list) > 1:
                plural = "s have"
            else:
                plural = " has"
            print(
                "Abort!  The following section{0} no (verified) students:".format(
                    plural
                )
            )
            for section in section_list:
                if registration_qs(section=section).count() == 0:
                    print("* {0}".format(section))
            sys.exit(1)

    registration_check(section_list)
    # section_keys = set(section_list.values_list('pk', flat=True))
    qs = registration_qs(section__in=section_list)
    return qs.select_related()


################################################################


def get_room_occupancy(room, ratio, slack_ratio=0.1):
    """
    Get the 'occupancy' count as a range min, max for this room.
    Good slack ratios are between 10% and 15%. (?)
    If the room occupancy is close to capacity, reduce the slack.
    """
    if not room.capacity:
        raise RuntimeError("Abort! The room {} has no capacity set!".format(room))

    count = int(ceil(room.capacity / ratio))
    assert count <= room.capacity
    # return count
    slack_count = int(round(room.capacity * slack_ratio))
    upto = min(count + slack_count, room.capacity)
    delta = upto - count
    downto = count - delta
    # return downto, upto
    # print(room, '\t', room.capacity, '\t', downto, '-', upto)
    return count


################################################################


def letter_cutoff(s1, s2, room_list):
    """
    Given two strings (family names) determine how much they have in common
    and return enough to distinguish a split between s1 and s2
    """
    s1 = s1.lower()
    s2 = s2.lower()
    if not (s1 < s2):
        raise InvalidCutoff(
            room_list,
            'These strings are not ordered correctly (s1:"{}" *not* strictly less than s2:"{}")!'.format(
                s1, s2
            ),
        )
    n = 0
    l1 = len(s1)
    l2 = len(s2)
    while True:
        if n >= l1:
            break
        if s1[n] != s2[n]:
            break
        n += 1
    return s2[: n + 1]


################################################################


def attempt_main(classrooms, ratio, registrations):
    """
    """
    occupancy_list = [get_room_occupancy(r, ratio) for r in classrooms]
    assert sum(occupancy_list) >= len(registrations)

    slice_list = []
    j = 0
    for i in range(len(classrooms)):
        k = j + occupancy_list[i]
        slice_list.append([j, k])
        j += occupancy_list[i]

    slice_list[-1][1] = None  # last slice index is upto None
    start_list = []

    # need to condition this to not break on people with the same last name.
    # do this by computing how much slack there is around each slice position
    # and then picking the optimal slice point within that.

    last_end = None
    room_list = []
    for room, o in zip(classrooms, slice_list):
        room_list.append(room)
        j, k = o
        slice = registrations[j:k]
        slice_count = len(slice)
        if last_end is None:
            start = "a"
        else:
            actual_start_idx = 0
            while True:
                # in case there's a break where people have the same surname
                # see above note for a "better" approach -- this is workable.
                current_start = slice[actual_start_idx]
                if last_end != current_start:
                    break
                actual_start_idx += 1
                if actual_start_idx > 5:
                    raise InvalidCutoff("Two many people with the same surname here")

            start = letter_cutoff(last_end, current_start, room_list)
        start_list.append(start)
        last_end = slice[-1]

        sys.stdout.write(".")
        sys.stdout.flush()

    # sum of squares to penalize long name breaks
    return sum([len(s) ** 2 for s in start_list]), start_list


################################################################


def shuffle_main(classrooms, ratio, registrations, max_tries, best_score):
    """
    Repeatedly shuffle classrooms in order to find the best match.
    """
    # for purposes of this function, cb_ indicates "current best"
    cb_score = None
    cb_start_list = None
    cb_shuffle = None
    success_count = 0
    try:
        for attempt_count in range(max_tries):
            start_list = None
            try:
                score, start_list = attempt_main(classrooms, ratio, registrations)
            except InvalidCutoff:
                score = None
                sys.stdout.write("!")
            else:
                sys.stdout.write("#")

            if score is not None:
                success_count += 1
                if cb_score is None or (score < cb_score):
                    cb_score = score
                    cb_start_list = start_list
                    cb_shuffle = [c.pk for c in classrooms]
                if score <= best_score:
                    break  # we are done
            # setup the next attempt
            shuffle(classrooms)

            sys.stdout.flush()
    except KeyboardInterrupt:
        pass

    print()
    print()
    print(
        "Success ratio of shuffling classrooms: %d out of %d"
        % (success_count, attempt_count)
    )
    return cb_score, cb_start_list, cb_shuffle


################################################################


def bisection_partition_main(
    classrooms, ratio, registrations, max_tries, best_score, max_ratio=0.5, debug=False
):
    """
    """

    def _classroom_partition(classrooms):
        assert len(classrooms) > 1, "Cannot partition 1 or fewer rooms."
        if len(classrooms) == 2:
            return classrooms[:1], classrooms[1:]
        caps = [r.capacity for r in classrooms]
        total = sum(caps)
        current = caps[0]
        target = 0.5 * total
        for i in range(1, len(caps)):
            current += caps[i]
            if current >= target:
                return classrooms[:i], classrooms[i:]
        # we know that there are 3 or more classrooms; and all of
        # the rooms got allocated to the first partition when this happens.
        # This ususally means the last room is the largest, which means
        # if we reverse the order and get a do-over, it will work.
        classrooms.reverse()
        return _classroom_partition(classrooms)
        # # Fail!
        # print('DEBUG')
        # print(classrooms)
        # print(caps)
        # print('total =', total)
        # from itertools import accumulate
        # print('partial sums =', list(accumulate(caps)))
        # print('target =', target)
        # assert False, '_classroom_partition() failed'

    def _best_split(name_list, start, stop, target):
        # A bunch of input sanitizing and edge case checks
        cutoff_list = []
        if start < 1:
            start = 1
        if stop >= len(name_list):
            stop = len(name_list) - 1
        if stop < start:
            start, stop = stop, start
        if start == stop:
            start = 1
            stop = len(name_list) - 1
        if target == start:
            target += 1
        if stop - start < 3:
            name_idx = start + (stop - start) // 2
            n1 = name_list[name_idx]
            n2 = name_list[name_idx]
            if n1 == n2:
                raise InvalidCutoff(classrooms)
            cutoff = letter_cutoff(n1, n2, classrooms)
            names_left = name_list[:name_idx]
            names_right = name_list[name_idx:]
            return cutoff, names_left, names_right

        # Final sanity check
        assert (
            0 < start < target < stop < len(name_list)
        ), "Invalid setup sequence: start={} target={} stop={} max={}".format(
            start, target, stop, len(name_list)
        )
        if debug:
            print(len(name_list), start, stop, target)
        for i in range(start, stop):
            n1 = name_list[i]
            n2 = name_list[i + 1]
            if not (n1 < n2):
                cutoff_list.append("-" * 100)
            else:
                cutoff_list.append(letter_cutoff(n1, n2, classrooms))
        score_list = [len(c) ** 2 for c in cutoff_list]
        min_score = min(score_list)
        # idx is an index in cutoff_list/score_list
        adj_target = target - start
        if score_list.count(min_score) == 1:
            idx = score_list.index(min_score)
        else:
            scores_left, scores_right = score_list[:adj_target], score_list[adj_target:]
            scores_left.reverse()
            try:
                l_idx = scores_left.index(min_score)
            except ValueError:
                l_idx = len(score_list)
            try:
                r_idx = scores_right.index(min_score)
            except ValueError:
                r_idx = len(score_list)
            if l_idx <= r_idx:
                idx = adj_target - 1 - l_idx
            else:
                idx = adj_target + r_idx

        cutoff = cutoff_list[idx]
        cutoff_score = len(cutoff) ** 2
        assert cutoff_score == min_score, "Did *not* determine the correct cutoff point"
        name_idx = start + idx
        names_left = name_list[:name_idx]
        names_right = name_list[name_idx:]
        return cutoff, names_left, names_right

    def _bisection_single_try(classrooms, max_ratio, registrations, first_start="a"):
        """
        returns score, start_list
        RECURSIVE.
        """
        assert len(classrooms) > 0, "0 or fewer classrooms"
        if len(classrooms) == 1:
            # tail
            return len(first_start) ** 2, [first_start]
        c1, c2 = _classroom_partition(classrooms)
        n1 = sum([r.capacity for r in c1])
        n2 = sum([r.capacity for r in c2])
        nT = n1 + n2
        local_ratio = (
            len(registrations) / nT
        )  # represents the "perfect balance" available
        if local_ratio > max_ratio:
            raise InvalidCutoff(classrooms)
        lr1 = int(n1 * local_ratio)
        lr2 = int(n2 * local_ratio)
        max1 = int(n1 * max_ratio)
        max2 = int(n2 * max_ratio)
        min1 = len(registrations) - max2
        min2 = len(registrations) - max1
        if debug:
            print("DEBUG")
            print("c1 =", c1)
            print("    ", [r.capacity for r in c1])
            print("c2 =", c2)
            print("    ", [r.capacity for r in c2])
            print("n1, n2, nT =", n1, n2, nT)
            print("len(registrations) = ", len(registrations))
            print("start_letter =", first_start)
            print("local_ratio = ", local_ratio)
            print("min1, lr1, max1 =", min1, lr1, max1)
            print("min2, lr2, max2 =", min2, lr2, max2)
        cutoff, reg1, reg2 = _best_split(registrations, min1, max1, lr1)
        if debug:  # first_start >= cutoff:
            print("cutoff =", cutoff)
            print("len(reg1) =", len(reg1), "(target: {})".format(lr1))
            print("len(reg2) =", len(reg2), "(target: {})".format(lr2))
        if cutoff == "-" * 100:
            raise InvalidCutoff(classrooms)
        if first_start == cutoff:
            raise InvalidCutoff(classrooms)
        assert (
            first_start < cutoff
        ), "Some kind of strangeness; first_start={}; cutoff={}".format(
            first_start, cutoff
        )
        if not (reg1 and reg2):
            raise InvalidCutoff(classrooms)
        score1, cutoff1 = _bisection_single_try(c1, max_ratio, reg1, first_start)
        score2, cutoff2 = _bisection_single_try(c2, max_ratio, reg2, cutoff)
        score = score1 + score2
        cutoff_list = cutoff1 + cutoff2
        return score, cutoff_list

    # bisection_partition_main() begins
    ntries = 0
    success_count = 0
    cb_score, cb_start_list, cb_shuffle = None, None, None
    try:
        while True:
            if ntries >= max_tries:
                break

            start_list = None
            try:
                score, start_list = _bisection_single_try(
                    classrooms, max_ratio, registrations
                )
            except InvalidCutoff:
                score = None
                sys.stdout.write("!")
            else:
                sys.stdout.write("#")

            if score is not None:
                success_count += 1
                if cb_score is None or (score < cb_score):
                    cb_score = score
                    cb_start_list = start_list
                    cb_shuffle = [c.pk for c in classrooms]
                if score <= best_score:
                    break  # we are done
            # setup the next attempt
            shuffle(classrooms)

            sys.stdout.flush()
            ntries += 1

    except KeyboardInterrupt:
        pass

    print()
    print()
    print(
        "Success ratio for bisection-partition of classrooms: %d out of %d"
        % (success_count, ntries)
    )
    return cb_score, cb_start_list, cb_shuffle


################################################################


def permutations_main(
    classrooms, ratio, registrations, cutoff_score, limit_threshold=12
):
    """
    Test all permutations of classrooms for the best score.
    """
    if len(classrooms) > limit_threshold:
        #    9! = 362,880 [completes in ~8 sec]
        #   10! = 3,628,800 [projected ~2.5 min]
        #   11! = 39,916,800 [projected ~30 min]
        #   12! = 479,001,600 [completes in ~3.5 hours]
        #   13! [projected ~3 days]
        print(
            "It is unwise to use --permutations with more than {0} classrooms.  (You have {1}.)".format(
                limit_threshold, len(classrooms)
            )
        )
        return None, None, None

    best_score = float("inf")
    best_start_list = None
    best_classrooms = None

    exclude = [None]

    try:
        for try_rooms in filter(
            lambda x: any((a != b for a, b in zip(exclude, (c.pk for c in x)))),
            permutations(classrooms),
        ):
            score = None
            try:
                score, start_list = attempt_main(try_rooms, ratio, registrations)
            except InvalidCutoff as e:
                exclude = [c.pk for c in e.fail]
                score = None
                sys.stdout.write("!")
            else:
                sys.stdout.write("#")
            if score is not None and score < best_score:
                best_score = score
                best_start_list = start_list[:]
                best_classrooms = [c.pk for c in try_rooms]
                if best_score <= cutoff_score:
                    break
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass

    print()
    return best_score, best_start_list, best_classrooms


################################################################


def model_choice_input(queryset, prompt="selection: "):
    """
    Do a text mode selection from a queryset of choices.
    """
    counter = 1
    response_map = {}
    for item in queryset:
        print("  [%d]" % counter, item)
        response_string = "%d" % counter
        response_map[response_string] = item
        counter += 1
    while True:
        response = input(prompt).strip()
        if response in response_map:
            return response_map[response]
        print("** Invalid selection, try again.")


################################################################


def datetime_input(prompt="enter a date and time [YYYY-MM-DD hh:mm]: "):
    """
    Enter and validate a datetime input
    """
    while True:
        resp = input(prompt).strip()
        try:
            value = datetime.strptime(resp, "%Y-%m-%d %H:%M")
        except ValueError:
            value = None
        if value is not None:
            if is_naive(value):
                value = make_aware(value, get_default_timezone())
            return value
        print("** %r: not in the correct datetime format. Try again." % resp)


################################################################


def integer_input(prompt="enter an integer value: "):
    """
    Enter and validate an integer
    """
    while True:
        resp = input(prompt).strip()
        try:
            value = int(resp)
        except ValueError:
            value = None
        if value is not None:
            return value
        print("** %r: not an integer. Try again." % resp)


################################################################


def get_save_info():
    """
    Get the additional information required for a save.
    """
    print()
    print("EXAM INFO")
    print()
    result = {}
    result["verbose_name"] = input('Exam Name (e.g., "Midterm 2"): ').strip()
    result["type"] = model_choice_input(
        ExamType.objects.filter(active=True), "Exam type: "
    )
    result["slug"] = "-save-fix-" + "{}".format(random())

    result["dtstart"] = datetime_input(
        "Enter the exam start date and time [YYYY-MM-DD hh:mm]: "
    )
    result["duration"] = integer_input("Enter the exam duration (minutes): ")
    print()
    return result


################################################################


def do_save(sections, room_assignments, public):
    """
    Save this solution to the database, prompting for additional information.
    """
    info = get_save_info()
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
    if options["sections"] is None or options["classrooms"] is None:
        print("You must supply both --sections and --classrooms")
        return
    if options["randomize"] and options["permutations"]:
        print("The randomize and permutations options are mutually exclusive.")
        return
    if args:
        print("This CLI takes no arguments")
        return

    classrooms = get_queryset_list(ClassRoom, options["classrooms"])
    for r in classrooms:
        assert int(r.capacity or 0) > 0, "Classroom {} has no capacity set".format(r)
    sections = get_queryset_list(Section, options["sections"])
    registrations = get_registrations(sections)

    seats_required = registrations.count()
    print("Registration Count:", seats_required)
    total_capacity = sum([r.capacity for r in classrooms])
    print("Seating Count:", total_capacity)
    assert seats_required < total_capacity, "Total capacity exceeded. Get more rooms."
    ratio = float(total_capacity) / seats_required
    print("One student every %f seat(s)." % ratio)
    surnames = [r.student.person.sn.lower() for r in registrations]

    best_score = options["best_score"] * len(classrooms)

    if options["bisection"]:
        score, start_list, classrooms = bisection_partition_main(
            classrooms,
            ratio,
            surnames,
            options["max_tries"],
            best_score,
            max_ratio=options["max_ratio"],
        )
        if score is not None:
            classrooms = [ClassRoom.objects.get(pk=pk) for pk in classrooms]

    elif options["randomize"]:
        score, start_list, classrooms = shuffle_main(
            classrooms, ratio, surnames, options["max_tries"], best_score
        )
        if score is not None:
            classrooms = [ClassRoom.objects.get(pk=pk) for pk in classrooms]

    elif options["permutations"]:
        score, start_list, classrooms = permutations_main(
            classrooms, ratio, surnames, best_score
        )
        if score is not None:
            classrooms = [ClassRoom.objects.get(pk=pk) for pk in classrooms]

    else:
        score, start_list = attempt_main(classrooms, ratio, surnames)

    print("Score was:", score)
    if score is not None:
        for room, start in zip(classrooms, start_list):
            print("{room}\t{start}\t{room.capacity}".format(room=room, start=start))

        if options["randomize"] or options["permutations"]:
            print("Classroom vector =", ",".join(["%d" % c.pk for c in classrooms]))

    if options["save"]:
        do_save(sections, zip(classrooms, start_list), options["public"])


################################################################
