"""
Exams admin
"""
from __future__ import print_function, unicode_literals

import time
from collections import OrderedDict

from classes.admin import (
    SectionCourseFilter,
    SectionMultipleChoiceField,
    SectionSemesterFilter,
)
from classes.models import Semester
from django.conf.urls import url
from django.contrib import admin, messages
from django.contrib.admin import widgets
from django.forms.models import modelform_factory
from django.utils.timezone import now

from . import conf
from .forms import (
    CreateExamForm,
    ExamFileForm,
    ExamForm,
    ExamLocationForm,
    ExamLocationInlineFormSet,
    get_examform_section_queryset,
)
from .models import Exam, ExamFile, ExamLocation, ExamType, Section
from .views import admin_room_poster
from .views.admin import DoRoomSplitsFormView

######################################################################


class SectionM2MCourseFilter(SectionCourseFilter):
    field_name = "sections__course"


class ExamSectionM2MCourseFilter(SectionCourseFilter):
    field_name = "exam__sections__course"


######################################################################


class SectionM2MSemesterFilter(SectionSemesterFilter):
    field_name = "sections__term"


class ExamSectionM2MSemesterFilter(SectionSemesterFilter):
    field_name = "exam__sections__term"


######################################################################


def merge_selected(modeladmin, request, queryset):
    # must be for the same course, date, time, and duration to merge.
    original_count = queryset.count()
    if original_count < 2:
        messages.error(
            request, "You must select more than one exam to merge", fail_silently=True
        )
        return
    first = queryset[0]
    rest = queryset[1:]

    def _check():
        for e in rest:
            if e.course != first.course:
                messages.error(
                    request, "Course mismatch in selected exams", fail_silently=True
                )
                return False
            if e.dtstart != first.dtstart:
                messages.error(
                    request,
                    "Scheduled date/time mismatch in selected exams",
                    fail_silently=True,
                )
                return False
            if e.duration != first.duration:
                messages.error(
                    request, "Duration mismatch in selected exams", fail_silently=True
                )
                return False
        return True

    def _copy_to_first():
        sections = list(first.sections.all())
        for e in rest:
            sections += list(e.sections.all())
            e.examlocation_set.all().update(exam=first)
            e.examfile_set.all().update(exam=first)
        return sections

    def _clean_duplicate_locations():
        locations = first.examlocation_set.values()
        delete_list = []
        check_list = []
        for loc in locations:
            if loc in check_list:
                continue
            for check in locations:
                if loc["id"] == check["id"]:
                    continue
                print(loc["location_id"], check["location_id"])
                if (
                    loc["location_id"] == check["location_id"]
                    and check["id"] not in delete_list
                ):
                    delete_list.append(check["id"])
                    print("-> delete", check["id"])
            check_list.append(check["id"])
        if delete_list:
            print(delete_list)
            first.examlocation_set.filter(pk__in=delete_list).delete()

    if not _check():
        return
    sections = _copy_to_first()
    _clean_duplicate_locations()
    for e in rest:
        e.delete()
    first.slug = "-save-fix-{}".format(time.time())  # regenerate the exam slug
    first.save()
    first.sections = sections
    messages.success(
        request, "Merged {} exams".format(original_count), fail_silently=True
    )


merge_selected.short_description = "Merge the selected exams"

######################################################################


def set_public(modeladmin, request, queryset):
    queryset.update(public=True)


set_public.short_description = "Set the public flag for the selected exams"

######################################################################


def clear_public(modeladmin, request, queryset):
    queryset.update(public=False)


clear_public.short_description = "Clear the public flag for the selected exams"

######################################################################


class ExamFileAdmin(admin.ModelAdmin):
    form = ExamFileForm
    list_filter = [
        "exam__type",
        ExamSectionM2MCourseFilter,
        ExamSectionM2MSemesterFilter,
    ]
    list_display = ["verbose_name", "exam_course", "exam", "exam_term", "solutions"]
    raw_id_fields = ["exam"]

    def exam_course(self, obj):
        return obj.exam.course

    exam_course.short_description = "course"

    def exam_term(self, obj):
        return obj.exam.term

    exam_term.short_description = "term"

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ["exam"]
        return []

    def view_on_site(self, obj):
        return obj.get_absolute_url()


admin.site.register(ExamFile, ExamFileAdmin)

######################################################################


class ExamLocationInline(admin.TabularInline):
    model = ExamLocation
    extra = 0
    # note: we must specify both the form and formset for the correct
    #   inline logic.
    form = ExamLocationForm
    formset = ExamLocationInlineFormSet
    readonly_fields = ["student_count", "occupancy_percent_display"]


class ExamFileInline(admin.TabularInline):
    model = ExamFile
    form = ExamFileForm
    extra = 0


class ExamAdmin(admin.ModelAdmin):
    date_hierarchy = "dtstart"
    inlines = [ExamLocationInline, ExamFileInline]
    list_display = ["course", "verbose_name", "public", "dtstart"]
    list_filter = [
        "active",
        "type",
        "public",
        SectionM2MCourseFilter,
        SectionM2MSemesterFilter,
        "created",
        "modified",
    ]
    readonly_fields = ["registration_count"]
    search_fields = ["verbose_name"]
    ordering = ["-dtstart"]
    save_on_top = True
    form = ExamForm  # see get_form() below

    def get_actions(self, request, *args, **kwargs):
        actions = super(ExamAdmin, self).get_actions(request, *args, **kwargs)
        if request.user.is_superuser:
            for name, f in [
                ("exams_merge_selected", merge_selected),
                ("set_public", set_public),
                ("clear_public", clear_public),
            ]:
                if name not in actions:
                    actions[name] = f, name, f.short_description

        return actions

    def get_form(self, request, obj=None, **kwargs):
        if obj is None:
            self.form = CreateExamForm
        else:
            self.form = ExamForm
        return super(ExamAdmin, self).get_form(request, obj, **kwargs)

    def get_inline_instances(self, request, obj=None, **kwargs):
        if obj is None:
            return []
        return super(ExamAdmin, self).get_inline_instances(request, obj, **kwargs)

    def get_queryset(self, request):
        """
        This function restricts the default queryset in the
        admin list view.
        """
        qs = super(ExamAdmin, self).get_queryset(request)
        # If super-user, show all; otherwise restrict to future by conf setting:
        if not request.user.is_superuser and conf.get("staff_sees_only_future"):
            qs = qs.future()
        return qs.distinct()

    def get_urls(self):
        """
        Extend the admin urls for this model.
        Provide a link by subclassing the admin change_form,
        and adding to the object-tools block.
        """
        urls = super(ExamAdmin, self).get_urls()
        urls = [
            url(
                r"^(?P<pk>[\d]+)/poster/$",
                self.admin_site.admin_view(admin_room_poster),
                name="exam_room_poster",
            ),
            url(
                r"^(?P<pk>.+)/split-rooms/$",
                self.admin_site.admin_view(DoRoomSplitsFormView.as_view()),
                name="exams_exam_split_rooms",
                kwargs={"admin_options": self},
            ),
        ] + urls
        return urls

    def get_object(self, *args, **kwargs):
        # Save the object so we can be adaptive about it's m2m widget later.
        obj = super(ExamAdmin, self).get_object(*args, **kwargs)
        if obj is not None:
            self._obj = obj
        return obj

    def is_for_current_term(self, obj):
        if obj.pk is None:
            return False
        s = set(obj.sections.values_list("term_id", flat=True))
        if len(s) != 1:
            return False
        pk = s.pop()
        return pk == Semester.objects.get_current().pk

    autocomplete_fields = ["sections"]

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        obj = getattr(self, "_obj", None)  # cannot call get_object() here.
        if db_field.name == "sections":
            # adaptive m2m widget and queryset.
            kwargs["widget"] = widgets.AutocompleteSelectMultiple(
                db_field.remote_field,
                self.admin_site,
                using=kwargs.get("using"),
                attrs={"style": "width:25em"},
            )
            qs = get_examform_section_queryset()
            if obj is not None:
                # restrict queryset of sections to set term
                qs = qs.filter(term=Semester.objects.get_by_date(obj.dtstart))
            kwargs["queryset"] = qs
            return SectionMultipleChoiceField(**kwargs)

        return super().formfield_for_manytomany(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and now() > obj.dtstart:
            return [
                "verbose_name",
                "sections",
                "type",
                "dtstart",
                "duration",
                "student_count",
            ]
        return []


admin.site.register(ExamType)
admin.site.register(Exam, ExamAdmin)

######################################################################
