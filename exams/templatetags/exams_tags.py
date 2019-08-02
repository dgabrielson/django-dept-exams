################################################################

from __future__ import print_function, unicode_literals

from django import template

from .. import utils
from ..context_processors import get_queryset

################################################################

register = template.Library()

################################################################


@register.filter
def old_examfiles(course):
    """
    course|old_examfiles
    """
    return utils.old_examfiles_for_course(course)


################################################################


@register.filter
def all_examfiles(course):
    """
    course|all_examfiles
    """
    return utils.all_examfiles_for_course(course)


################################################################


@register.simple_tag(takes_context=True)
def get_upcoming_exams(context, save_as=None, days=None, max_count=None):
    """
    {% get_upcoming_exams %} -> qs
    {% get_upcoming_exams 'upcoming_exams_qs' %}
    """
    qs = get_queryset(days=days, max_count=max_count)
    if save_as is not None:
        context[save_as] = qs
        return ""
    return qs


################################################################
