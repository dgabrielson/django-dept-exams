"""
Sitemap for exam app.
"""
from __future__ import print_function, unicode_literals

from django.contrib.sitemaps import GenericSitemap

from .models import Exam

Exam_Sitemap = GenericSitemap({"queryset": Exam.objects.public()})
