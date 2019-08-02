"""
Forms for the exams application.
"""
from __future__ import print_function, unicode_literals

from random import random

import classes.conf
from classes.admin import SectionMultipleChoiceField
from classes.forms import MultiSectionFilterField
from classes.models import Section, Semester
from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.timezone import now

from . import conf
from .models import Exam, ExamFile, ExamLocation

#######################################################################
#######################################################################


def get_examform_section_queryset():
    qs = Section.objects.filter(active=True)
    if conf.get("exam_sections:restrict_advertised"):
        qs = qs.advertised()
    return qs.distinct()


#######################################################################


class ExamForm(forms.ModelForm):
    """
    Form for Exam objects
    """

    # sections = SectionMultipleChoiceField(queryset=get_examform_section_queryset())

    class Meta:
        model = Exam
        # exclude = []
        fields = [
            "active",
            "slug",
            "sections",
            "type",
            "verbose_name",
            "dtstart",
            "duration",
            "public",
            "student_count",
        ]
        widgets = {"slug": forms.HiddenInput}

    def __init__(self, *args, **kwargs):
        super(ExamForm, self).__init__(*args, **kwargs)
        if "sections" in self.fields:
            self.fields["sections"].queryset = get_examform_section_queryset()
        if "student_count" in self.fields and self.instance.pk:
            self.fields[
                "student_count"
            ].help_text += " - {} students registered".format(
                self.instance.registration_count
            )

    def clean_slug(self):
        """
        Clean the slug field -- this will enable the auto-slugging
        from the m2m_changed signal handler.
        """
        if not self.cleaned_data["slug"]:
            slug = "-save-fix-" + slugify("{}".format(random()))
            return slug
        return self.cleaned_data["slug"]

    def clean_sections(self):
        """
        Clean sections -- ensure they are all from the same term
        """
        terms = set((section.term for section in self.cleaned_data["sections"]))
        if len(terms) == 0:
            raise ValidationError("There are no sections selected")
        if not len(terms) == 1:
            raise ValidationError("All sections must belong to the same term")
        return self.cleaned_data["sections"]

    def clean(self):
        """
        Here we check the verbose_name against the sections.
        """
        verbose_name = self.cleaned_data.get("verbose_name", None)
        if not verbose_name:
            return self.cleaned_data
        sections = self.cleaned_data.get("sections", None)
        if not sections:
            return self.cleaned_data

        ## Reference: Exact m2m match:
        # qs = qs.filter(sections__in=sections)
        # qs = qs.annotate(count=Count('sections')).filter(count=len(sections))
        for section in sections:
            qs = Exam.objects.filter(
                verbose_name=verbose_name,
                sections__course=section.course,
                sections__term=section.term,
            )
            qs = qs.filter(sections=section)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.count() > 0:
                msg = "One or more of the selected section(s) already has an exam with this name"
                raise ValidationError(msg)
        return self.cleaned_data


#######################################################################


class CreateExamForm(ExamForm):
    sections = MultiSectionFilterField(queryset=get_examform_section_queryset())

    class Meta(ExamForm.Meta):
        fields = [
            "sections",
            "type",
            "verbose_name",
            "dtstart",
            "duration",
            "slug",
            "public",
        ]
        widgets = {"slug": forms.HiddenInput, "public": forms.HiddenInput}

    def clean(self, *args, **kwargs):
        result = super(CreateExamForm, self).clean(*args, **kwargs)
        if "dtstart" in self.cleaned_data:
            if self.cleaned_data["dtstart"] < now():
                # adding a historical exam.
                self.cleaned_data["public"] = True
        return result


#######################################################################


class ExamLocationForm(forms.ModelForm):
    """
    Form for ExamLocation objects
    """

    class Meta:
        model = ExamLocation
        exclude = []

    def clean_start_letter(self):
        """
        Clean the start_letter field -- If present, it must be an
        alphabetical sequence.
        """
        if not self.cleaned_data.get("start_letter", None):
            return ""
        if not self.cleaned_data["start_letter"].isalpha():
            raise ValidationError("Start letters can only be alphabetical")
        return self.cleaned_data["start_letter"]


#######################################################################


class ExamLocationBaseInlineFormSet(forms.models.BaseInlineFormSet):
    """
    Used for the formset when attached to an Exam,
    provide a custom clean method.
    """

    # def clean(self):
    #     """
    #     Custom clean method to validate that the entire sequence
    #     of location makes senses as a group.
    #
    #     Remember: self.cleaned_data is a list of cleaned_data OrderedDict
    #         objects for each form in self.forms.
    #         form.cleaned_data is each OrderedDict.
    #     """
    #     result = super(ExamLocationBaseInlineFormSet, self).clean()
    #     if len(self.forms) > 1:
    #         # formset validation only engages when there is more than
    #         # a single location.
    #         for form in self.forms:
    #             if not hasattr(form, 'cleaned_data'):
    #                 return result   # some other problem with this form.
    #             if not form.cleaned_data.get('start_letter', None):
    #                 raise ValidationError('You must set a start letter for each exam location')
    #
    #         start_letters = [form.cleaned_data['start_letter'].lower() \
    #                          for form in self.forms]
    #         l = start_letters[0]
    #         for c in start_letters[1:]:
    #             if not (l < c):
    #                 raise ValidationError('Exam location must be in order of the starting letter(s)')
    #             l = c
    #
    #     return result


ExamLocationInlineFormSet = forms.models.inlineformset_factory(
    Exam, ExamLocation, formset=ExamLocationBaseInlineFormSet, exclude=[]
)

#######################################################################


class LaTeXFormatForm(forms.Form):
    """
    Form for choosing formatting options.
    """

    pk = forms.IntegerField(widget=forms.HiddenInput())
    paper_size = forms.ChoiceField(
        choices=[
            ("letter", "Letter (8.5x11in)"),
            ("legal", "Legal (8.5x14in)"),
            ("tabloid", "Tabloid (11x17in)"),
        ],
        help_text="Select a papersize",
    )
    landscape = forms.BooleanField(required=False, help_text="Is the output landscape?")
    src = forms.BooleanField(
        required=False,
        label="Download source",
        help_text="Select to download LaTeX source",
    )

    class Media:
        css = {"all": ("admin/css/widgets.css",)}


#######################################################################


class ExamFileForm(forms.ModelForm):
    class Meta:
        model = ExamFile
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        result = super(ExamFileForm, self).__init__(*args, **kwargs)
        if "verbose_name" in self.fields:
            self.fields["verbose_name"].required = False
            self.fields["verbose_name"].help_text += (
                ". <br><strong>RECOMMENDED:</strong> Leave blank to use the name of the exam.  "
                + "<br><strong>CAUTION:</strong> This name affects the exam file headings on the website."
            )
        return result

    def clean(self, *args, **kwargs):
        result = super(ExamFileForm, self).clean(*args, **kwargs)
        if not self.cleaned_data.get("verbose_name", None):
            exam = self.cleaned_data.get("exam")
            if exam is not None:
                self.cleaned_data["verbose_name"] = exam.verbose_name
            elif hasattr(self.instance, "exam"):
                self.cleaned_data["verbose_name"] = self.instance.exam.verbose_name
        return result


#######################################################################


class DoRoomSplitForm(forms.Form):

    exam = forms.ModelChoiceField(
        queryset=Exam.objects.future(), widget=forms.HiddenInput
    )
    min_ratio = forms.FloatField(
        label="Minimum occupancy", help_text="Catch too few students or too many rooms"
    )
    max_ratio = forms.FloatField(
        label="Maximum occupancy",
        help_text="Catch too many students or not enough rooms",
    )
    max_tries = forms.IntegerField(
        max_value=10000,
        min_value=50,
        label="Computation time",
        help_text="Higher numbers give better results, but take longer to run. Minimum 50, maximum 10000.",
    )

    def clean_exam(self):
        exam = self.cleaned_data.get("exam", None)
        if exam is None:
            raise forms.ValidationError("An exam is required")
        return exam

    def do_room_splits(self, check_only, commit=False):
        from .utils.room_splits import do_room_splits as utils_room_splits

        exam = self.cleaned_data.get("exam")
        max_tries = self.cleaned_data.get("max_tries")
        min_ratio = self.cleaned_data.get("min_ratio")
        max_ratio = self.cleaned_data.get("max_ratio")
        return utils_room_splits(
            exam,
            check_only=check_only,
            commit=commit,
            max_tries=max_tries,
            min_ratio=min_ratio,
            max_ratio=max_ratio,
        )

    def clean(self, *args, **kwargs):
        result = super(DoRoomSplitForm, self).clean(*args, **kwargs)
        self.do_room_splits(check_only=True)
        return result

    def save(self, commit=True):
        """
        Remember - this is not a model form -- this must be called explicitly in the view.
        """
        return self.do_room_splits(commit=commit, check_only=False)


#######################################################################
