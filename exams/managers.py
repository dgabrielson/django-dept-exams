"""
Custom Managers for the exams app.
"""
from __future__ import print_function, unicode_literals

from django.db import models

from .querysets import ExamFileQuerySet, ExamQuerySet

################################################################

################################################################


class ExamManager(models.Manager):
    """
    Default manager for exams, just a wrapper for returning the
    custom _QuerySet
    """

    def get_queryset(self):
        """
        Return the custom QuerySet
        """
        return ExamQuerySet(self.model)


ExamManager = ExamManager.from_queryset(ExamQuerySet)

################################################################


class ExamLocationManager(models.Manager):
    """
    Default manager for exam locations.
    """

    def active(self):
        """
        Filter out non-active objects
        """
        return self.filter(active=True)


################################################################


class ExamFileManager(models.Manager):
    """
    Default manager for exams, just a wrapper for returning the
    custom _QuerySet
    """

    def get_queryset(self):
        """
        Return the custom QuerySet
        """
        return ExamFileQuerySet(self.model)


ExamFileManager = ExamFileManager.from_queryset(ExamFileQuerySet)

################################################################
