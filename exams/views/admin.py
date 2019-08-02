"""
Admin only views
"""
##########################################################################

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic.edit import FormView

from ..forms import DoRoomSplitForm
from ..models import Exam

##########################################################################


class AdminSiteViewMixin(object):
    """
    Use this for generic CBVs in the admin.
    Still need to check permissions and hook into admin urls appropriately.
    """

    def get_admin_options(self):
        return self.kwargs.get("admin_options", None)

    def get_context_data(self, **kwargs):
        """
        Extend the context so the admin template works properly.
        """
        context = super(AdminSiteViewMixin, self).get_context_data(**kwargs)
        admin_options = self.get_admin_options()
        context.update(
            admin_options.admin_site.each_context(self.request),
            model=admin_options.model,
            opts=admin_options.model._meta,
            app_label=admin_options.model._meta.app_label,
        )
        return context


################################################################


class AdminFormMixin(object):

    model = None
    _obj_cache = None

    def get_original_obj(self):
        if self._obj_cache is not None:
            return self._obj_cache
        pk = self.kwargs.get("pk", None)
        if self.model is None:
            raise ImplementationError("AdminFormMixin requires the model attribute.")
        obj = get_object_or_404(self.model, pk=pk)
        self._obj_cache = obj
        return obj

    def get_success_url(self):
        """
        Note that this requires the underlying model to define the
        ``admin_change_link()`` method.
        """
        obj = self.get_original_obj()
        return obj.admin_change_link()

    def get_context_data(self, **kwargs):
        """
        Extend the context so the admin template works properly.
        """
        context = super(AdminFormMixin, self).get_context_data(**kwargs)
        context.update(original=self.get_original_obj())
        return context


################################################################


class DoRoomSplitsFormView(AdminSiteViewMixin, AdminFormMixin, FormView):
    """
    A view to bulk upload files.
    """

    model = Exam
    template_name = "admin/exams/exam/extra_form.html"
    form_class = DoRoomSplitForm

    def get_initial(self):
        """
        Get initial data for the form.
        """
        initial = super(DoRoomSplitsFormView, self).get_initial()
        initial["exam"] = self.get_original_obj()
        initial["min_ratio"] = 0.3
        initial["max_ratio"] = 0.5
        initial["max_tries"] = 1000
        return initial

    def form_valid(self, form):
        """
        Process successful form submission.
        """
        try:
            form.save(commit=True)
        except ValidationError as e:
            error = e.message
            error += " You may be able to adjust the split options and try again."
            messages.error(self.request, error, fail_silently=True)
            return super(DoRoomSplitsFormView, self).form_invalid(form)
        else:
            messages.success(self.request, "Room split complete", fail_silently=True)
            return super(DoRoomSplitsFormView, self).form_valid(form)

    def get_success_url(self):
        obj = self.get_original_obj()
        return reverse_lazy("admin:exams_exam_change", args=[obj.pk])

    def get_context_data(self, **kwargs):
        """
        Extend the context so the admin template works properly.
        """
        context = super(DoRoomSplitsFormView, self).get_context_data(**kwargs)
        context.update(
            page_header="Room split options", submit_button_label="Split rooms"
        )
        return context


################################################################
