#######################################################################

from __future__ import print_function, unicode_literals

import codecs
import functools
import json
from collections import OrderedDict
from datetime import date, datetime
from itertools import zip_longest

from aurora.models import AuroraLocation
from classes.models import Course, Department, Section, Semester
from django.conf import global_settings, settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count
from django.utils.text import slugify
from django.utils.timezone import get_current_timezone, make_aware, now

from ... import conf
from ...models import Exam, ExamLocation, ExamType, exam_m2m_changed_handler

#######################################################################

# Python 2 and 3:
try:
    # Python 3:
    from urllib.parse import urlparse, urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError, URLError
except ImportError:
    # Python 2:
    from urlparse import urlparse
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError, URLError

#######################################################################

DATETIME_FORMATS = (
    "%b %d %Y %I:%M %p",
    "%b %d, %Y %I:%M %p",
    "%b. %d %Y %I:%M %p",
    "%b. %d, %Y %I:%M %p",
    "%B %d %Y %I:%M %p",
    "%B %d, %Y %I:%M %p",
    "%m/%d/%Y %I:%M %p",
    "%Y-%m-%d %H:%M:%S",
)

USE_TZ = getattr(settings, "USE_TZ", global_settings.USE_TZ)

#######################################################################


class ApiCommunicationError(Exception):
    # used to signal api failures at the communication layer.
    pass


#######################################################################


def _api_call(method, url, payload=None, headers={}, auth_token=None):
    """
    General API call.
    """
    if payload is not None:
        # for symmetry; submit json to the server.
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    else:
        data = None
    headers["Accept"] = "application/json"  # ; indent=4'
    if auth_token is not None:
        headers["Authorization"] = "Token " + auth_token

    request = Request(url, data, headers)
    request.get_method = lambda: method

    try:
        f = urlopen(request)
    except HTTPError as e:
        raise ApiCommunicationError(
            method + " " + url + " returned " + "HTTP error: %d" % e.code
        )
    except URLError as e:
        raise ApiCommunicationError(
            method + " " + url + " gave " + "Network error: %s" % e.reason.args[1]
        )
    else:
        if f.headers.get("content-length", None) != "0":
            info = f.info()
            if hasattr(info, "get_content_charset"):
                # Python 3:
                encoding = f.info().get_content_charset(failobj="utf-8")
            else:
                # Python 2:
                encoding = f.headers.getparam("charset")
                if encoding is None:
                    encoding = "utf-8"
            reader = codecs.getreader(encoding)
            return json.load(reader(f))


#######################################################################

######################################################################


class Command(BaseCommand):
    help = "From a json source of exam information, load it."

    input_required_keys = ["term_code", "course", "section", "date", "time"]
    input_optional_keys = [
        "instructor",
        "location",
        "alpha splits",
        "seats",
        "duration",
        "actual_enrolment",
        "__multisection_hint",
    ]
    # The __multisection_hint field is a way of specifying that
    #   otherwise "equal" sections (for multisection) should NOT
    #   be combined as a multisection exam.
    # Augment individual records as required; e.g., with
    #       "__multisection_hint": false
    # for a single section which is not part of an otherwise
    # multisection exam.
    input_none_rooms = ["", "tba", "by-dept", "seats"]
    input_none_seats = ["", "tba"]
    input_none_splits = [""]

    def add_arguments(self, parser):
        """
        Add arguments to the command.
        """
        parser.add_argument("-s", "--simulate", action="store_true", help="Do not save")
        parser.add_argument(
            "--url",
            default=conf.get("from_json:default_url"),
            help="Specify a url to load",
        )
        parser.add_argument(
            "--exam-type",
            default="final",
            help="Set the type of the loaded exams (by slug; default: final)",
        ),
        parser.add_argument(
            "--exam-name",
            default="Final Exam",
            help='Set the name of the loaded exams (default: "Final Exam")',
        ),
        parser.add_argument(
            "--public", action="store_true", help="Set the created exams to be public"
        ),
        parser.add_argument(
            "--duration",
            default=180,
            type=int,
            help="Set the duration of the exam, in minutes, if not given (default: 180)",
        ),
        parser.add_argument(
            "--allowed-fields",
            action="store_true",
            help="Show the list of allowed fields and exit",
        ),

    #######################################################

    # When you are using management commands and wish to provide console output,
    # you should write to self.stdout and self.stderr, instead of printing to
    # stdout and stderr directly. By using these proxies, it becomes much easier
    # to test your custom command. Note also that you don't need to end messages
    # with a newline character, it will be added automatically, unless you
    # specify the ``ending`` parameter to write()

    def handle(self, *args, **options):
        """
        Do the thing!
        """
        self.verbosity = options.get("verbosity")
        if options.get("allowed_fields", False):
            self.stdout.write("required: " + ", ".join(self.input_required_keys))
            self.stdout.write("optional: " + ", ".join(self.input_optional_keys))
            return

        data = self.load_json_from_url(options.get("url"))
        if data is None:
            if self.verbosity > 0:
                self.stdout.write("No data retreived.")
                return

        data = self._santize_keys(data)
        if not self._sanity_check(data):
            return

        data = self._filter_advertised(data)
        data = self._filter_future(data)
        data = self._combine_multisection(data)
        data = self._prep_exams(
            data,
            options["exam_type"],
            options["exam_name"],
            options["public"],
            options["duration"],
        )
        commit = not options["simulate"]
        self._save_all(data, commit)

    #######################################################

    def load_json_from_url(self, url):
        if self.verbosity > 2:
            self.stdout.write("Retrieve json from: " + url)
        try:
            data = _api_call("GET", url)
        except ApiCommunicationError as e:
            self.stderr.write(str(e))
            data = None
        else:
            if self.verbosity > 2:
                self.stdout.write("-> {} records".format(len(data)))
        return data

    #######################################################

    def _santize_keys(self, data):
        """
        Convert all keys to lower case.
        """
        return [{k.lower(): v for k, v in d.items()} for d in data]

    #######################################################

    def _sanity_check(self, data):
        """
        Make sure the record headers are things we can deal with.
        """
        if self.verbosity > 2:
            self.stdout.write("First result:")
            self.stdout.write(str(data[0]))
        required = set(self.input_required_keys)
        optional = set(self.input_optional_keys)
        for d in data:
            h = set(d)
            if h.intersection(required) != required:
                self.stderr.write("Data did not have all required fields")
                self.stderr.write("-> expected: " + ", ".join(required))
                return False
            unrecognized = h.difference(required).difference(optional)
            if unrecognized != set():
                self.stderr.write("Data has unrecognized fields")
                self.stderr.write("-> unrecognized: " + ", ".join(unrecognized))
                return False
        return True

    #######################################################

    def _filter_advertised(self, data):
        """
        Filter the data so that only our advertised departments are included.
        """
        adv = set(
            Department.objects.active().advertised().values_list("code", flat=True)
        )
        if self.verbosity > 2:
            self.stdout.write("Advertised codes: " + str(adv))
        result = [d for d in data if d["course"].split(None, 1)[0] in adv]
        if self.verbosity > 2:
            self.stdout.write("-> {} records".format(len(result)))
        return result

    #######################################################

    def _filter_future(self, data):
        """
        Use the date and time fields to determine what is beyond now.
        This also augments the returned record with 'dtstart',
        a python object for the combined datatime.
        """

        def _augment(record):
            date = record.get("date")
            time = record.get("time")
            if "T" in date:
                date = date.split("T", 1)[0]
            dt_str = date + " " + time
            dt = None
            for fmt in DATETIME_FORMATS:
                try:
                    dt = datetime.strptime(dt_str, fmt)
                except ValueError:
                    pass
                else:
                    break

            if dt is None:
                raise ValueError(
                    "Tried all available datetime formats against {0!r} -- could not parse datetime.".format(
                        dt_str
                    )
                )

            if USE_TZ:
                dt = make_aware(dt, get_current_timezone())

            record["dtstart"] = dt
            return record

        # compute dtstart attribute
        data_aug = [_augment(d) for d in data]
        # filter
        N = now()
        if self.verbosity > 2:
            self.stdout.write("Check for dtstart beyond: " + str(N))
        result = [d for d in data_aug if d["dtstart"] >= N]
        if self.verbosity > 2:
            self.stdout.write("-> {} records".format(len(result)))
        return result

    #######################################################

    def _combine_multisection(self, data):
        """
        Amalgamate multisection exams
        """

        def _equal(r1, r2):
            eq_keys = ["term_code", "course", "dtstart", "__multisection_hint"]
            v = [r1.get(k) == r2.get(k) for k in eq_keys]
            return all(v)

        def _combine(d, matches):
            result = d.copy()
            result["multisection"] = True
            result["section_list"] = [d0["section"]] + [d["section"] for d in matches]
            if "ALL" in result["section_list"]:
                # seen: ALL + A01 (autocomplete error?)
                result["section_list"] = ["ALL"]
            for h in self.input_optional_keys:
                h_list = []
                if h in d:
                    h_list.append(d[h])
                h_list.extend([d[h] for d in matches if h in d])
                result[h + "_list"] = h_list
            if self.verbosity > 3:
                self.stdout.write("Multisection combine: " + str(result))
            return result

        result = []
        if self.verbosity > 2:
            self.stdout.write("Checking for multisection exams...")
        while True:
            if not data:
                break
            d0 = data.pop(0)
            matches = [d for d in data if _equal(d0, d)]
            if matches:
                result.append(_combine(d0, matches))
                data = [d for d in data if not _equal(d0, d)]
            else:
                result.append(d0)

        if self.verbosity > 2:
            self.stdout.write("-> {} records".format(len(result)))
        return result

    #######################################################

    def _prep_exams(
        self, data, exam_type_slug, exam_verbose_name, public, default_duration
    ):
        """
        Take the list of dictionaries in ``data``, and produce
        a new list of data suitable passing (elementwise) to
        ``_save_exam``
        """

        def _get_banner_term_queryterms(academic_period):
            year = int(academic_period[:4])
            start_m = academic_period[4]
            zero = academic_period[5]
            if zero != "0":
                raise RuntimeError(
                    'invalid academic period "{}"'.format(academic_period)
                )
            if start_m not in ["1", "5", "9"]:
                raise RuntimeError(
                    'invalid academic period "{}"'.format(academic_period)
                )
            term = None
            if start_m == "1":
                term = "1"
            if start_m == "5":
                term = "2"
            if start_m == "9":
                term = "3"
            return {"term__year": year, "term__term": term, "term__active": True}

        def _get_term_query(d):
            code = d["term_code"]
            return _get_banner_term_queryterms(str(code))

        def _get_course_query(d):
            prefix = "course__"  # for searching within sections
            course_str = d["course"]
            dept_code, course_code = course_str.split(None, 1)
            return {
                prefix + "code": course_code,
                prefix + "active": True,
                prefix + "department__code": dept_code,
                prefix + "department__active": True,
            }

        def _get_sections(d):
            query = _get_term_query(d)
            query.update(_get_course_query(d))
            query["active"] = True
            if d.get("multisection", False):
                if d["section_list"] != ["ALL"]:
                    query["section_name__in"] = d["section_list"]
                else:
                    query["section_type__in"] = conf.get("from_json:all_section_types")
            else:
                query["section_name__iexact"] = d["section"]
            return Section.objects.filter(**query)

        def _get_location_set(d):
            @functools.lru_cache(maxsize=None)
            def _get_examlocation(room, split, seats):
                # NOTE: we don't use seats; but we might in the future.
                if room is not None and room.lower() in self.input_none_rooms:
                    room = None
                if room is None:
                    return None
                if split is not None and split.lower() in self.input_none_splits:
                    split = None
                if seats is not None and seats.lower() in self.input_none_seats:
                    seats = None
                aurora_location, created = AuroraLocation.objects.find(
                    room, create=True
                )
                if created and self.verbosity > 0:
                    self.stdout.write("Created new location: " + str(aurora_location))
                if split is not None:
                    start_letter = split.split("-")[0].lower().strip()
                else:
                    start_letter = ""
                return aurora_location.classroom, start_letter
                # return ExamLocation(location=aurora_location.classroom,
                #                     start_letter=start_letter)

            if d.get("multisection", False):
                # remove duplicates but preserve ordering
                room_list = d.get("location_list", [])
                splits_list = d.get("alpha splits_list", [])
                seats_list = d.get("seats_list", [])
            else:
                location = d.get("location", None)
                split = d.get("alpha splits", None)
                seats = d.get("seats", None)
                room_list = [] if location is None else [location]
                splits_list = [] if split is None else [split]
                seats_list = [] if seats is None else [seats]
            results = []
            location_data = zip_longest(room_list, splits_list, seats_list)
            # De-duplicate:
            location_data = list(OrderedDict.fromkeys(location_data))
            # NOTE: we cannot trust at this point that the data has
            # been fully de-duplicated; because "U.Centre" != "U. Centre"
            location_data = [
                _get_examlocation(room, split, seats)
                for room, split, seats in location_data
                if _get_examlocation(room, split, seats) is not None
            ]
            # final deduplicate
            location_data = sorted(
                set(location_data),
                key=lambda e: (e[1], e[0].building.lower(), e[0].number.lower()),
            )
            results = [
                ExamLocation(location=location, start_letter=start_letter)
                for location, start_letter in location_data
            ]
            # self.stdout.write(str(results))
            return results

        def _exam_name(d, section_list, verbose_name):
            course = d["course"]
            term = d["term_code"]
            if section_list.all().count() == 1:
                sections = section_list.get().section_name + " "
            else:
                sections = ""
            return "{course} {sections}{verbose_name} {term}".format(
                course=course, sections=sections, verbose_name=verbose_name, term=term
            )

        def _get_duration(value):
            """
            120 -> 120
            "120" -> 120
            "2 hours" -> 120
            "1 hour" -> 60
            "2" -> 120  # cutover is 12

            raise ValueError() when the value cannot be converted to
            minutes in a sensible way.
            """
            result = None
            if isinstance(value, str):
                h, *rest = value.split()
                if rest:
                    if rest == ["hours"] or rest == ["hour"]:
                        result = int(h) * 60
                else:
                    result = int(h)
            if isinstance(value, int):
                if value <= 12:
                    result = value * 60
                else:
                    result = value
            if result is None:
                raise ValueError('unexpected duration format: "{}"'.format(value))
            return result

        def _prep_record(d, exam_type):
            sections = _get_sections(d)
            exam_name = _exam_name(d, sections, exam_verbose_name)
            duration_in_minutes = _get_duration(d.get("duration", default_duration))
            examinfo = {
                "type": exam_type,
                "verbose_name": exam_verbose_name,
                "public": public,
                "duration": duration_in_minutes,
                "slug": slugify(exam_name),
                "dtstart": d["dtstart"],
            }
            location_set = _get_location_set(d)
            return examinfo, sections, location_set

        exam_type = ExamType.objects.get(active=True, slug=exam_type_slug)
        if self.verbosity > 2:
            self.stdout.write("Exam type: " + str(exam_type))

        if self.verbosity > 2:
            self.stdout.write("Preparing exam records...")
        result = [_prep_record(d, exam_type) for d in data]
        if self.verbosity > 2:
            self.stdout.write("Preparation complete")
        return result

    #######################################################

    def _save_all(self, data, commit):
        def _save_by_update(exam, examdata, sections):
            if self.verbosity > 2:
                self.stdout.write("Updating existing exam...")
            do_save = False
            for f in examdata:
                v = getattr(exam, f)
                if f == "public" and v:
                    # do not hide things that have been made public.
                    examdata["public"] = True
                if f == "slug":
                    # skip updating the slug -- autoslug can modify this.
                    continue
                if v != examdata[f]:
                    if self.verbosity > 2:
                        self.stdout.write(
                            "\tfield: {}; value: {} -> {}".format(f, v, examdata[f])
                        )
                    setattr(exam, f, examdata[f])
                    do_save = True
            if commit and do_save:
                exam.save()
            exam_section_set = set(exam.sections.all().values_list("pk", flat=True))
            new_section_set = set(sections.values_list("pk", flat=True))
            if exam_section_set != new_section_set:
                if self.verbosity > 2:
                    self.stdout.write(
                        "\tsection set has changed: {} -> {}".format(
                            exam_section_set, new_section_set
                        )
                    )
                do_save = True
                if commit:
                    exam.sections.set(sections)
                    exam.save()
                    exam_m2m_changed_handler(
                        sender="exams.exams_from_json:_save_by_update()",
                        instance=exam,
                        action="post_add",
                        reverse=False,
                        model=Exam,
                        pk_set=[s.pk for s in sections],
                    )
            return exam, do_save

        def _save_by_create(examdata, sections):
            if self.verbosity > 2:
                self.stdout.write("Creating new exam...")
            exam = Exam(**examdata)
            if commit:
                exam.save()
                exam.sections.set(sections)
                exam.save()
            return exam

        def _save_exam(exam_queryset, examdata, sections, location_set):
            if self.verbosity > 2:
                self.stdout.write("Pre-save data::")
                self.stdout.write(str(examdata))
                self.stdout.write(str(sections))
                self.stdout.write(str(location_set))

            qs = exam_queryset.filter(type=examdata["type"])
            # Exact m2m match:
            qs = qs.filter(sections__in=sections)
            qs = qs.annotate(count=Count("sections")).filter(count=len(sections))
            qs = qs.distinct()
            changed = False
            if qs.count() == 1:
                exam, changed = _save_by_update(qs.get(), examdata, sections)
                create = False
            else:
                if qs.count() > 1:
                    if self.verbosity > 0:
                        # delete one at a time for verbosity
                        for o in qs:
                            self.stdout.write(
                                "- Deleting old, confilicting exam: " + str(o)
                            )
                            o.delete()
                    else:
                        # nuke queryset
                        qs.delete()
                exam = _save_by_create(examdata, sections)
                create = True
                changed = True
            # do location_set
            # self.stdout.write('[1] changed = {}'.format(changed))
            if location_set and exam.examlocation_set.exists():
                exam_location_set = set(
                    exam.examlocation_set.all().values_list(
                        "location_id", "start_letter"
                    )
                )
                new_location_set = set(
                    [(l.location.pk, l.start_letter) for l in location_set]
                )
                if (
                    exam_location_set != new_location_set
                    or len(location_set) != exam.examlocation_set.count()
                ):
                    changed = True
                    if commit:
                        if self.verbosity > 2:
                            self.stdout.write("deleting existing examlocaation set...")
                        exam.examlocation_set.all().delete()

            # self.stdout.write('[2] changed = {}'.format(changed))
            if (
                (not changed)
                and (len(location_set) > 0)
                and (not exam.examlocation_set.exists())
            ):
                changed = True

            # self.stdout.write('[3] changed = {}'.format(changed))
            if changed:
                for location in location_set:
                    location.exam = exam
                    if commit:
                        location.save()
                        if self.verbosity > 2:
                            self.stdout.write(
                                "Saved examlocation: location_id = {}\tstart_letter = {}".format(
                                    location.location_id, location.start_letter
                                )
                            )
            # self.stdout.write('[4] changed = {}'.format(changed))
            return exam, changed, create

        ## _save_all() begins ##

        if self.verbosity > 2:
            if commit:
                self.stdout.write("Saving exams...")
            else:
                self.stdout.write("Pretending to save exams...")

        qs = Exam.objects.all()

        for record in data:
            exam, changed, created = _save_exam(qs, *record)
            if changed:
                if self.verbosity > 0:
                    verb = "Created: " if created else "Updated: "
                    self.stdout.write(verb + exam.slug)
            elif self.verbosity > 1:
                self.stdout.write("Unchanged: " + exam.slug)

        if self.verbosity > 2:
            self.stdout.write("DONE")


#######################################################################
