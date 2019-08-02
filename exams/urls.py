"""
URL patterns for exams app.
"""
from __future__ import print_function, unicode_literals

from django.conf.urls import url

from . import views

urlpatterns = [
    url(r"^$", views.exam_list_future, name="exams-list"),
    url(r"^all/$", views.exam_list, name="exams-list-all"),
    url(r"^old/$", views.examfile_list, name="exams-examfile-list"),
    url(
        r"^old/(?P<slug>[\w-]+)/$",
        views.examfile_list_for_course,
        name="exams-examfiles-forcourse",
    ),
    url(
        r"^signin-sheets/(?P<slug>[\w-]+)/src$",
        views.signin_sheet_src,
        name="exams-signin-sheet-src",
    ),
    url(
        r"^signin-sheets/(?P<slug>[\w-]+)/$",
        views.signin_sheet,
        name="exams-signin-sheet",
    ),
    url(
        r"^signature-sheets/(?P<slug>[\w-]+)/src$",
        views.signature_sheet_src,
        name="exams-signature-sheet-src",
    ),
    url(
        r"^signature-sheets/(?P<slug>[\w-]+)/$",
        views.signature_sheet,
        name="exams-signature-sheet",
    ),
    url(
        r"^room-poster/(?P<slug>[\w-]+)/src/$",
        views.room_poster_src,
        name="exams-room-poster-src",
    ),
    url(
        r"^room-poster/(?P<slug>[\w-]+)/$", views.room_poster, name="exams-room-poster"
    ),
    url(r"^calendar/$", views.exam_calendar, name="exams-calendar"),
    url(r"^(?P<slug>[\w-]+)/$", views.exam_detail, name="exams-detail"),
]
