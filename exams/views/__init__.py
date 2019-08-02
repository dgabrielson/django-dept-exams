"""
Views for the exams app.
"""
################################################################

from classes.models import Course
from django.contrib.auth.decorators import permission_required
from django.shortcuts import get_object_or_404
from django.views.generic.detail import DetailView
from django.views.generic.edit import FormView
from django.views.generic.list import ListView
from latex.djangoviews import LaTeXDetailView, LaTeXResponseMixin
from webcal.views import generic_queryset_icalendar

from .. import utils
from ..forms import LaTeXFormatForm
from ..models import Exam, ExamFile

################################################################
################################################################


class ExamMixin(object):
    queryset = Exam.objects.public().prefetch_related("sections")


################################################################


class ExamDetailView(ExamMixin, DetailView):
    pass


exam_detail = ExamDetailView.as_view()

################################################################


class ExamListView(ExamMixin, ListView):
    pass


exam_list = ExamListView.as_view()

################################################################


class ExamListFutureView(ExamMixin, ListView):
    def get_queryset(self, *args, **kwargs):
        """
        Do this in get_queryset to prevent caching stale dates.
        """
        qs = super().get_queryset(*args, **kwargs)
        return qs.future()


exam_list_future = ExamListFutureView.as_view()

################################################################
################################################################


class ExamFileMixin(object):
    queryset = (
        ExamFile.objects.all()
        .filter(active=True, exam__active=True, exam__public=True)
        .released()
    )


################################################################


class ExamFileListView(ExamFileMixin, ListView):
    pass


examfile_list = ExamFileListView.as_view()

################################################################


class ExamFileDetailView(ExamFileMixin, DetailView):
    pass


examfile_detail = ExamFileDetailView.as_view()

################################################################


class ExamFileListForCourse(ListView):
    template_name = "exams/examfile_list_for_course.html"

    def _get_course(self):
        if not hasattr(self, "_course"):
            course_slug = self.kwargs.get("slug", None)
            self._course = get_object_or_404(Course, slug=course_slug)
        return self._course

    def get_queryset(self):
        course = self._get_course()
        qs = utils.old_examfiles_for_course(course)
        qs = qs.order_by("verbose_name", "exam")
        return qs

    def get_context_data(self, *args, **kwargs):
        context = super(ExamFileListForCourse, self).get_context_data(*args, **kwargs)
        course = self._get_course()
        context.update({"course": course})
        return context


examfile_list_for_course = ExamFileListForCourse.as_view()

################################################################
################################################################


class ExamPrintDetailView(LaTeXDetailView):
    """
    Base class for exam print-views
    """

    queryset = Exam.objects.active()

    def get_filename(self, latex_doc):
        """
        Give the filename as the exam slug.
        """
        return self.fix_filename_extension(self.object.slug)


################################################################

signin_sheet = permission_required("exams.change_exam")(
    ExamPrintDetailView.as_view(
        template_name="exams/print/signin_sheet.tex", as_attachment=False
    )
)

signin_sheet_src = permission_required("exams.change_exam")(
    ExamPrintDetailView.as_view(
        template_name="exams/print/signin_sheet.tex", as_source=True
    )
)

################################################################

signature_sheet = permission_required("exams.change_exam")(
    ExamPrintDetailView.as_view(
        template_name="exams/print/signature_sheet.tex", as_attachment=False
    )
)

signature_sheet_src = permission_required("exams.change_exam")(
    ExamPrintDetailView.as_view(
        template_name="exams/print/signature_sheet.tex", as_source=True
    )
)

################################################################

room_poster = ExamPrintDetailView.as_view(
    template_name="exams/print/exam_rooms.tex", as_attachment=False
)

room_poster_src = ExamPrintDetailView.as_view(
    template_name="exams/print/exam_rooms.tex", as_source=True
)

################################################################
################################################################


class ExamRoomPosterFormatFormView(LaTeXResponseMixin, FormView):
    """
    For generating room posters.
    """

    form_class = LaTeXFormatForm
    login_required = True
    template_name = "admin/exams/exam/room_poster_form.html"
    as_attachment = False

    def __init__(self, *args, **kwargs):
        self.object = None
        return super(ExamRoomPosterFormatFormView, self).__init__(*args, **kwargs)

    def get_object(self):
        if self.object is not None:
            return self.object
        pk = self.kwargs.get("pk", None)
        self.object = get_object_or_404(Exam, pk=pk)
        return self.object

    def get_initial(self):
        """
        Returns initial data for the form (a dictionary).
        """
        return {
            "pk": self.kwargs.get("pk", None),
            "paper_size": "tabloid",
            "landscape": False,
            "download_source": False,
        }

    def get_filename(self, latex_doc=None):
        filename = self.get_object().slug
        return self.fix_filename_extension(filename)

    def form_valid(self, form):
        """
        If the form is valid, redirect to the supplied URL.
        """
        # modify the template name for this instance now that the form is valid.
        self.template_name = "exams/print/exam_rooms_format.tex"
        return LaTeXResponseMixin.render_to_response(
            self, self.get_context_data(formdata=form.cleaned_data)
        )

    def form_invalid(self, form):
        """
        If the form is invalid, re-render the context data with the
        data-filled form and errors.
        """
        return FormView.render_to_response(self, self.get_context_data(form=form))

    def get(self, request, *args, **kwargs):
        """
        Handles GET requests and instantiates a blank version of the form.
        """
        return FormView.render_to_response(self, self.get_context_data())

    def get_context_data(self, **kwargs):
        context = super(ExamRoomPosterFormatFormView, self).get_context_data(**kwargs)
        exam = self.get_object()
        context.update(
            {
                "app_label": "exams",
                "opts": {
                    "app_label": "exams",
                    "app_config": {"verbose_name": "Exams and tests"},
                    "verbose_name_plural": "Exams",
                    "module_name": "exams_admin_room_poster",
                },
                "has_change_permission": True,
                "form_desc": "Room Poster",
                "original": exam,
                "object": exam,
                "exam": exam,
            }
        )
        return context


admin_room_poster = permission_required("exams.change_exam")(
    ExamRoomPosterFormatFormView.as_view()
)

################################################################


def exam_calendar(request):
    """
    An iCal feed for *public* *future* exams.
    """
    return generic_queryset_icalendar(
        request, Exam.objects.public().future(), include_set_events=False
    )


################################################################
