"""
Room splits handling.

See also forms/DoRoomSplitForm; which does some of the prechecking
for this.
"""
from __future__ import print_function, unicode_literals

from random import shuffle

from django.forms import ValidationError
from places.models import ClassRoom

from ..models import ExamLocation

################################################################

################################################################


class InvalidCutoff(Exception):
    """
    This one isn't going to work...
    """

    def __init__(self, fail, *args, **kwargs):
        self.fail = fail
        return super(InvalidCutoff, self).__init__(*args, **kwargs)


################################################################


def get_exam_classrooms(exam):
    pk_list = exam.examlocation_set.active().values_list("location_id", flat=True)
    return list(ClassRoom.objects.filter(pk__in=pk_list))


################################################################


def sanity_checks(exam, classrooms, min_cap_ratio, max_cap_ratio):
    """
    Final check for potential problems.
    """
    if len(classrooms) < 2:
        raise ValidationError("Two or more rooms required for splits")
    reg_count = exam.registration_count
    if reg_count == 0:
        raise ValidationError("There are no students registered for this exam")
    no_caps = [c for c in classrooms if not c.capacity]
    if no_caps:
        plural = "s have" if len(no_caps) != 1 else "has"
        raise ValidationError(
            "The following room{} unknown capacity: ".format(plural)
            + ", ".join([str(c) for c in no_caps])
        )
    total_cap = sum([c.capacity for c in classrooms])
    ratio = reg_count / total_cap
    if not (min_cap_ratio <= ratio <= max_cap_ratio):
        raise ValidationError(
            "There is an occupancy ratio of {:.2f}, which is outside the given range of values".format(
                ratio
            )
        )
    return ratio


################################################################


def letter_cutoff(s1, s2, room_list):
    """
    Given two strings (lower case surnames) determine how much they have in common
    and return enough to distinguish a split between s1 and s2
    """
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


################################################################


def _best_split(name_list, start, stop, target, classrooms, debug=False):
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
    if not (0 < start < target < stop < len(name_list)):
        if debug:
            print(
                "Invalid setup sequence: start={} target={} stop={} max={}".format(
                    start, target, stop, len(name_list)
                )
            )
        raise InvalidCutoff(classrooms)
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


################################################################


def _bisection_single_try(
    classrooms, max_ratio, registrations, first_start="a", debug=False
):
    """
    returns score, start_list
    RECURSIVE.
    """
    assert len(classrooms) > 0, "0 or fewer classrooms"
    if len(classrooms) == 1:
        # tail for recursion
        # final check of ratio:
        cap = classrooms[0].capacity
        if len(registrations) / cap > max_ratio:
            raise InvalidCutoff(classrooms)
        return len(first_start) ** 2, [first_start]
    c1, c2 = _classroom_partition(classrooms)
    n1 = sum([r.capacity for r in c1])
    n2 = sum([r.capacity for r in c2])
    nT = n1 + n2
    local_ratio = len(registrations) / nT  # represents the "perfect balance" available
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
    cutoff, reg1, reg2 = _best_split(
        registrations, min1, max1, lr1, classrooms, debug=debug
    )
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
    ), "Some kind of strangeness; first_start={}; cutoff={}".format(first_start, cutoff)
    if not (reg1 and reg2):
        raise InvalidCutoff(classrooms)
    score1, cutoff1 = _bisection_single_try(
        c1, max_ratio, reg1, first_start, debug=debug
    )
    score2, cutoff2 = _bisection_single_try(c2, max_ratio, reg2, cutoff, debug=debug)
    score = score1 + score2
    cutoff_list = cutoff1 + cutoff2
    return score, cutoff_list


################################################################


def bisection_partition_main(
    classrooms, ratio, registrations, max_tries, best_score, max_ratio=0.5, debug=False
):
    """
    Make attempts at bisection/partition splits.  Success ration seems
    to be about 20%; execution speed is fast for each attempt.
    """
    ntries = 0
    success_count = 0
    cb_score, cb_start_list, cb_shuffle = None, None, None
    while True:
        if ntries >= max_tries:
            break
        start_list = None
        try:
            score, start_list = _bisection_single_try(
                classrooms, max_ratio, registrations, debug=debug
            )
        except InvalidCutoff:
            score = None
        else:
            success_count += 1
            if cb_score is None or (score < cb_score):
                cb_score = score
                cb_start_list = start_list
                cb_shuffle = [c.pk for c in classrooms]
            if score <= best_score:
                break  # we are done
        # setup the next attempt
        shuffle(classrooms)
        ntries += 1

    return cb_score, cb_start_list, cb_shuffle


################################################################


def do_room_splits(
    exam, commit=True, check_only=False, max_tries=1000, min_ratio=0.3, max_ratio=0.5
):
    """
    Worker entry point for this module; does room splits.

    This is computationally intesive (~5 seconds) and forms calling this
    as part of the request response cycle should take this into consideration.
    """
    classrooms = get_exam_classrooms(exam)
    ratio = sanity_checks(
        exam, classrooms, min_cap_ratio=min_ratio, max_cap_ratio=max_ratio
    )
    if check_only:
        return None
    surnames = [
        n.lower()
        for n in exam.registration_list.values_list("student__person__sn", flat=True)
    ]
    best_score = len(classrooms)  # used to be a parameter with older methods
    score, start_list, classrooms = bisection_partition_main(
        classrooms,
        ratio,
        surnames,
        max_tries=max_tries,
        best_score=best_score,
        max_ratio=max_ratio,
    )
    if score is None:
        raise ValidationError("Could not find any valid splits.")

    classrooms = [ClassRoom.objects.get(pk=pk) for pk in classrooms]
    if commit:
        exam.examlocation_set.all().delete()
        loc_info = {"exam": exam}
        for room, start_letter in zip(classrooms, start_list):
            loc_info["location"] = room
            loc_info["start_letter"] = start_letter
            loc = ExamLocation(**loc_info)
            loc.save()
    return score


################################################################
