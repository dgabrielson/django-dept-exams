from __future__ import print_function, unicode_literals

import shouts
from django.urls import reverse_lazy

from .context_processors import get_queryset

##
## NOTE:
##  * You cannot use reverse() url matching here, since autodiscover()
##      is typically called in the url conf, and thus patterns may not
##      be loaded yet. [UNLESS shouts.autodiscover() is **last**.]
##

shouts.sources.register(
    "Upcoming Exam",
    get_queryset,
    # verbose_name=..., # default
    template_name="exams/shouts/%s.html",
    url=reverse_lazy("exams-list"),
)
