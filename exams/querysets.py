"""
Custom QuerySets for the exams app.
"""
from __future__ import print_function, unicode_literals

import datetime
import operator
from functools import reduce

from django.db import models
from django.utils.timezone import now

from . import conf

################################################################

################################################################


class ExamQuerySet(models.query.QuerySet):
    """
    Custom query set for this model.
    """

    def active(self):
        """
        Filter out non-active objects
        """
        return self.filter(active=True).distinct()

    def public(self):
        """
        Like active, but only returns public items as well.
        """
        qs = self.active()
        return qs.filter(public=True)

    def future(self, dt=None):
        """
        Restricts only to exams in the future (after dt, if given).
        Makes no assumptions about active/public.
        If dt is not given, now is used.
        """
        if dt is None:
            dt = now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(dtstart__gte=dt)

    def past(self, dt=None):
        """
        Restricts only to exams in the past (before dt, if given).
        Makes no assumptions about active/public.
        If dt is not given, now is used.
        """
        if dt is None:
            dt = now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self.filter(dtstart__lt=dt)

    def for_course(self, course):
        """
        Return all of the exams for a particular course.
        """
        return self.filter(sections__course=course)

    def course_qs(self):
        """
        Return the queryset of courses which correspond to these exams.
        """
        from classes.models import Course

        return Course.objects.filter(
            id__in=self.values_list("sections__course_id", flat=True)
        )

    search_fields = ["slug", "verbose_name"]

    def search(self, *criteria):
        """
        Magic search.
        This is heavily modelled after the way the Django Admin handles
        search queries.
        See: django.contrib.admin.views.main.py:ChangeList.get_query_set
        """
        if len(criteria) == 0:
            assert False, "Supply search criteria"
        terms = ["{}".format(c) for c in criteria]
        if len(terms) == 1:
            terms = terms[0].split()

        def construct_search(field_name):
            if field_name.startswith("^"):
                return "%s__istartswith" % field_name[1:]
            elif field_name.startswith("="):
                return "%s__iexact" % field_name[1:]
            elif field_name.startswith("@"):
                return "%s__search" % field_name[1:]
            else:
                return "%s__icontains" % field_name

        qs = self.filter(active=True)
        orm_lookups = [
            construct_search(str(search_field)) for search_field in self.search_fields
        ]
        for bit in terms:
            or_queries = [models.Q(**{orm_lookup: bit}) for orm_lookup in orm_lookups]
            qs = qs.filter(reduce(operator.or_, or_queries))
        return qs.distinct()

    def vevent_list(self):
        """
        Return a list of vevents which correspond to this queryset.
        """
        return [o.vevent() for o in qs.distinct()]


################################################################


class ExamFileQuerySet(models.query.QuerySet):
    def course_qs(self):
        """
        Return the queryset of courses which correspond to these exams.
        """
        from classes.models import Course

        return Course.objects.filter(
            id__in=self.values_list("exam__sections__course_id", flat=True)
        )

    def released(self, dt=None):
        """
        Return only the exam files that are past their holding time.
        Only items marked public can be released.
        """
        if dt is None:
            dt = now().replace(hour=0, minute=0, second=0, microsecond=0)
        holding = conf.get("old_exams_holding_days")
        dt -= datetime.timedelta(days=holding)
        return self.filter(exam__dtstart__lt=dt, public=True)

    def public(self):
        """
        Like active, but only returns public items as well.
        """
        qs = self.active()
        return qs.filter(public=True)
