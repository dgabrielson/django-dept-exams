"""
Models for the exams app.

The core model is the Exam, which specifies a
date, time, and duration of the exam; as well as
the course, term, and optionally sections for the exam
and the type of exam (e.g., Midterm, Final)

Each exam has one or more ExamLocations (0 locations may occur
for e.g., an online exam).

Additionally there are ExamFiles (fk to Exam).

"""
################################################################
from __future__ import division, print_function, unicode_literals

import datetime
from random import random

import vobject
from classes.models import Course, Section, Semester
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import models
from django.db.utils import IntegrityError
from django.urls import reverse
from django.utils.encoding import python_2_unicode_compatible
from django.utils.timezone import now
from places.models import ClassRoom
from students.models import Student_Registration

from . import conf
from .managers import ExamFileManager, ExamLocationManager, ExamManager
from .signals import exam_m2m_changed_handler
from .utils import slug_autonumber
from .validators import validate_reasonable_time

################################################################

UPLOAD_TO = conf.get("upload_to")
ADMIN_CONTACT = conf.get("admin_contact")
USE_CACHE = conf.get("cache_enabled")
CACHE_TIMEOUT = conf.get("cache_timeout")

################################################################


@python_2_unicode_compatible
class ExamType(models.Model):
    """
    The type of the exam.
    """

    active = models.BooleanField(default=True)
    created = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name="creation time"
    )
    modified = models.DateTimeField(
        auto_now=True, editable=False, verbose_name="last modification time"
    )

    slug = models.SlugField(
        unique=True, help_text="A url fragment to identify the exam type"
    )
    verbose_name = models.CharField(
        max_length=64, help_text="The name of the exam type"
    )

    def __str__(self):
        return self.verbose_name


################################################################


@python_2_unicode_compatible
class Exam(models.Model):
    """
    The exam information.
    """

    PUBLIC_CHOICES = ((True, "Advertise"), (False, "Hidden"))

    active = models.BooleanField(default=True)
    created = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name="creation time"
    )
    modified = models.DateTimeField(
        auto_now=True, editable=False, verbose_name="last modification time"
    )

    slug = models.SlugField(
        unique=True,
        blank=True,
        help_text='A url fragment to identify the exam, e.g., "stat1000-midterm-1-f11", (leave blank to set automatically)',
    )
    verbose_name = models.CharField(
        max_length=64,
        help_text='The name of the exam, usually "Midterm", "Midterm 1", "Midterm 2" or "Final Exam"',
    )
    type = models.ForeignKey(
        ExamType, on_delete=models.PROTECT, limit_choices_to={"active": True}
    )

    sections = models.ManyToManyField(
        Section,
        limit_choices_to={
            "active": True,
            "course__active": True,
            "course__department__active": True,
        },
    )
    dtstart = models.DateTimeField(
        verbose_name="date and start time",
        help_text="Dates are YYYY-MM-DD.  Time is in 24-hour notation.",
        validators=[validate_reasonable_time],
    )
    duration = models.PositiveSmallIntegerField(
        help_text="Duration of the exam, in minutes"
    )
    public = models.BooleanField(
        default=False,
        choices=PUBLIC_CHOICES,
        help_text="Set this to advertise the exam",
    )
    student_count = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Set this to override the number of students writing (for sign-in sheets)",
    )

    objects = ExamManager()

    class Meta:
        ordering = ["dtstart"]

    def __str__(self):
        return self.verbose_name

    def save(self, *args, **kwargs):
        while True:
            try:
                result = super(Exam, self).save(*args, **kwargs)
            except IntegrityError as e:
                msg = str(e)
                if "slug" in msg and "already exists" in msg:
                    self.slug = slug_autonumber(self.slug)
                else:
                    raise
            else:
                break
        return result

    def get_absolute_url(self):
        return reverse("exams-detail", kwargs={"slug": self.slug})

    def is_future(self, dt=None):
        if dt is None:
            dt = now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.dtstart >= dt

    @property
    def dtend(self):
        elapsed = datetime.timedelta(minutes=self.duration)
        return self.dtstart + elapsed

    def vevent(self):
        """
        Return the vevent which corresponds to this exam.
        """
        cal = vobject.iCalendar()
        ev = cal.add("vevent")
        ev.add("dtstamp").value = self.dtstart
        ev.add("dtstart").value = self.dtstart
        ev.add("dtend").value = self.dtend
        ev.add("summary").value = self.course + " " + self.verbose_name
        ev.add("location").value = ", ".join(
            ["{}".format(loc) for loc in self.examlocation_set.active()]
        )
        if not self.public:
            ev.add("description").value = "This exam is *not* being advertised."

        return ev

    def twitter_dtlist(self):
        """
        Return a list of suggested datetimes for tweeting this information.
        """
        if now() > self.dtstart:
            # Don't tweet about things which have already started.
            return []
        return [
            self.dtstart - datetime.timedelta(days=1),
            self.dtstart - datetime.timedelta(days=7),
        ]

    @property
    def registration_list(self):
        """
        Return a list of student registrations who are known to be
        writing this exam.
        """
        cache_key = "exams.%s:%r:registration_list" % (self.__class__.__name__, self.pk)

        result = cache.get(cache_key) if USE_CACHE else None
        if result is None:
            section_keys = self.sections.values_list("pk", flat=True)
            result = Student_Registration.objects.reg_list(
                section__in=section_keys, good_standing=True, aurora_verified=True
            ).select_related()
            if USE_CACHE:
                cache.set(cache_key, result, CACHE_TIMEOUT)

        return result

    def student_count_range(self):
        if self.student_count:
            return range(self.student_count)
        else:
            return range(0)

    @property
    def registration_count(self):
        """
        The number of students in the registration list, specifically
        """
        return self.registration_list.count()

    @property
    def registration_surnames(self):
        """
        Return a list of lower case student surnames known to be
        writing this exam.
        This list is presorted, so there is no need to sort the results.
        """
        if not self.active:
            return None
        cache_key = "exams.%s:%r:registration_surnames" % (
            self.__class__.__name__,
            self.pk,
        )

        result = cache.get(cache_key) if USE_CACHE else None
        if result is None:
            result = [r.student.person.sn.lower() for r in self.registration_list]
            # there is an optimization here, since the DB I'm using
            # returns this as a case insensitve ordering of the surnames
            result.sort()  # do it anyhow.
            if USE_CACHE:
                cache.set(cache_key, result, CACHE_TIMEOUT)

        return result

    @property
    def course_list(self):
        """
        Return a queryset of courses that this exam is for.
        Although at first glance it may seem like a good idea to restrict
        an exam to only one course, there are several cross numbered
        courses that would break on this, e.g. 4000/7000 level courses.
        """
        course_keys = self.sections.values_list("course", flat=True)
        return Course.objects.filter(pk__in=course_keys)

    @property
    def course(self):
        """
        Returns a string for the courses this corresponds to.
        """
        return "/".join([c.label for c in self.course_list])

    @property
    def term_list(self):
        """
        return a queryset of terms this exam is for.
        """
        keys = self.sections.values_list("term", flat=True)
        return Semester.objects.filter(pk__in=keys)

    @property
    def term(self):
        """
        Returns a string for the term this corresponds to.
        """
        return "/".join([str(t) for t in self.term_list])

    def reset_slug(self):
        self.slug = "-save-fix-{0}".format(id(self))
        exam_m2m_changed_handler(
            sender=Exam,
            instance=self,
            action="post_add",
            reverse=False,
            model=Exam,
            pk_set=[s.pk for s in self.sections.all()],
        )


################################################################

models.signals.m2m_changed.connect(
    exam_m2m_changed_handler, sender=Exam.sections.through
)

################################################################


@python_2_unicode_compatible
class ExamLocation(models.Model):
    """
    Where an exam takes place... frequently divided up by letters
    """

    active = models.BooleanField(default=True)
    created = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name="creation time"
    )
    modified = models.DateTimeField(
        auto_now=True, editable=False, verbose_name="last modification time"
    )

    exam = models.ForeignKey(
        Exam, on_delete=models.CASCADE, limit_choices_to={"active": True}
    )
    location = models.ForeignKey(
        ClassRoom,
        on_delete=models.PROTECT,
        limit_choices_to={"active": True},
        help_text="If you require a room not in this list, please contact "
        + '<a href="mailto:%s">%s</a>' % (ADMIN_CONTACT[0][1], ADMIN_CONTACT[0][0]),
    )
    start_letter = models.CharField(
        max_length=8,
        blank=True,
        help_text="Always use lowercase (leave this blank if there is only one room)",
    )

    objects = ExamLocationManager()

    class Meta:
        ordering = ["exam", "start_letter"]

    def __str__(self):
        return "{}".format(self.location)

    def vevent(self):
        """
        Return the vevent which corresponds to this exam.
        """
        return None

    @property
    def registration_list(self):
        """
        Return a sorted list of registrations at this location.
        NOTE: this is a sorted list so that classlists and similar
        are ordered correctly.
        """
        if not self.active:
            return None
        cache_key = "exams.%s:%r:registration_list" % (self.__class__.__name__, self.pk)

        result = cache.get(cache_key) if USE_CACHE else None
        if result is None:
            if self.start_letter:
                start = self.start_letter.lower()
            else:
                qs = ExamLocation.objects.filter(active=True, exam=self.exam)
                n = qs.count()
                if n == 1:
                    start = "a"
                else:
                    return []
            finish = self.upto_letter.lower()
            if not finish:
                finish = "|"
            # This happens when this is the only location.
            reg_list = self.exam.registration_list
            result = [
                reg
                for reg in reg_list
                if start <= reg.student.person.sn.lower() < finish
            ]
            result.sort(key=lambda reg: reg.student.person.sn.lower())
            if USE_CACHE:
                cache.set(cache_key, result, CACHE_TIMEOUT)

        return result

    @property
    def registration_surnames(self):
        """
        Return a sorted list of lower case surnames at this location.
        NOTE: this is a sorted list so that classlists and similar
        are ordered correctly.
        """
        if not self.active:
            return None
        cache_key = "exams.%s:%r:registration_surnames" % (
            self.__class__.__name__,
            self.pk,
        )

        result = cache.get(cache_key) if USE_CACHE else None
        if result is None:
            start = self.start_letter.lower()
            finish = self.upto_letter.lower()
            reg_list = self.exam.registration_surnames
            result = [reg for reg in reg_list if start <= reg < finish]
            # result.sort(key=lambda reg: reg.student.person.sn.lower())
            if USE_CACHE:
                cache.set(cache_key, result, CACHE_TIMEOUT)

        return result

    @property
    def upto_letter(self):
        """
        Returns the start_letter of the *next* exam location
        """
        if not self.active:
            return None
        if not self.start_letter:
            return ""
        if not self.start_letter.isalpha():
            return ""
        qs = ExamLocation.objects.filter(active=True, exam=self.exam)
        n = qs.count()
        if n == 0:  # no active locations
            return "|"

        if qs[n - 1] == self:  # i'm the last one
            return "|"

        for i in range(n):
            if qs[i] == self:
                next_loc = qs[i + 1]
                return next_loc.start_letter

        # return '~'
        # should never reach this, so raise an AssertionError:
        assert False, "there was a serious problem finding the next exam location"

    @property
    def finish_letter(self):
        """
        This is sort of like upto letter... and might be expensive.
        """
        if not self.active:
            return None

        def _to_number(s):
            """convert the string s to a number n"""
            if s == "|":
                return 26 * 26
            s = s.lower()
            n = 25
            for c in s:
                n *= 26
                n += ord(c) - ord("a")
            return n

        def _to_string(n):
            """convert the number n to a string s"""
            s = ""
            while True:
                k = n % 26
                s = chr(k + ord("a")) + s
                n //= 26
                if n == 25:
                    return s

        upto = self.upto_letter.lower()
        if not upto:
            return ""
        start = self.start_letter.lower()
        if not (start < upto):
            return ""
        n = _to_number(upto)
        s = _to_string(n - 1)
        if start[: len(s)] == s:
            s += "z"
        return s

    @property
    def student_count(self):
        if self.active:
            return len(self.registration_list)

    @property
    def occupancy_percent(self):
        if not self.active:
            return None
        if self.location.capacity:
            return 100 * len(self.registration_list) // int(self.location.capacity)
        return "N/A"

    @property
    def occupancy_percent_display(self):
        if not self.active:
            return None
        perc = self.occupancy_percent
        if isinstance(perc, int):
            perc = "{}%".format(perc)
        return perc

    @property
    def blank_lines(self):
        """
        Strictly a utility for generating signin sheets.
        """
        lines_per_page = 30
        count = self.student_count
        min_spread = 3 * round(count / 100.0)
        factor = 1
        if lines_per_page - count % lines_per_page < min_spread:
            factor = 2
        upto = lines_per_page * ((count // lines_per_page) + factor) - 1
        return range(count, upto)


################################################################


@python_2_unicode_compatible
class ExamFile(models.Model):
    """
    Typically, a PDF which archives the exam as seen by the students.
    """

    PUBLIC_CHOICES = ((True, "Public"), (False, "Restricted"))

    active = models.BooleanField(default=True)
    created = models.DateTimeField(
        auto_now_add=True, editable=False, verbose_name="creation time"
    )
    modified = models.DateTimeField(
        auto_now=True, editable=False, verbose_name="last modification time"
    )

    verbose_name = models.CharField(max_length=64, help_text="A title for the file")
    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        limit_choices_to={"active": True},
        help_text="For existing exams",
    )
    the_file = models.FileField(upload_to=UPLOAD_TO)
    solutions = models.BooleanField(
        default=False,
        help_text="Set this when the attached file contains worked solutions",
    )
    public = models.BooleanField(default=False, choices=PUBLIC_CHOICES)

    objects = ExamFileManager()

    class Meta:
        ordering = ["exam", "verbose_name"]

    def __str__(self):
        return self.verbose_name

    def is_past_holding(self, dt=None):
        if dt is None:
            dt = now().replace(hour=0, minute=0, second=0, microsecond=0)
        holding = conf.get("old_exams_holding_days")
        dt -= datetime.timedelta(days=holding)
        return self.exam.dtstart < dt

    def get_absolute_url(self):
        """
        Note: examfiles should actually be secured before the holding
        period has ellapsed, and not just rely on difficult to guess
        filename urls.
        """
        if self.is_past_holding():
            return self.the_file.url
        return None

    @property
    def exam_course(self):
        return self.exam.course

    def course_qs(self):
        return self.exam.sections.course_qs()

    @property
    def semester(self):
        return self.exam.term


################################################################
