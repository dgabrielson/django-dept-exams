"""
The DEFAULT configuration is loaded when the CONFIG_NAME dictionary
is not present in your settings.

All valid application settings must have a default value.
"""
from __future__ import print_function, unicode_literals

from django.conf import settings

CONFIG_NAME = "EXAMS_CONFIG"  # must be uppercase!

DEFAULT = {
    # current sections grace period.
    "grace_days": 21,
    # 'upload_to' is the variable portion of the path where files are stored.
    # (optional; default: '%Y/%m/%d')
    "upload_to": "%Y/%m/%d",
    # 'admin_contact' : who to contact for extra support.
    # if ADMINS is defined, this default becomes ADMINS[0]
    "admin_contact": ("Admin Name", "nobody@example.com"),
    # 'upcoming_days' defines the number of days to look
    #   ahead for upcoming exams.
    "upcoming_days": 14,
    # 'upcoming_max_count' defines a cap on the number of
    #   upcoming exams returned.
    #   set to None or 0 to not cap the number of exams.
    "upcoming_max_count": 4,
    # Exams and ExamLocations do a few expensive things with
    # classlists queries.  Django's cache framework API is used
    # to deal with these.  Classlists are not expected to change
    # frequenty by the time exams are set
    "cache_enabled": False,
    "cache_timeout": 7200,
    # by default, staff (not superusers) only see exams in the future
    # set this to False to change.
    "staff_sees_only_future": True,
    # restrict the exams change page to advertised sections only
    "exam_sections:restrict_advertised": True,
    # The number of days that must pass between the date of an exam,
    # and when attached files get published as "old exams"
    "old_exams_holding_days": 180,
    # Default url for the exams_from_json management command.
    "from_json:default_url": "https://example.com/exam-schedule.json",
    # Default meaning of 'all sections', by section type code.
    # This should line up with your clases configuration.
    "from_json:all_section_types": ["cl", "on"],
    # Use for reasonable time validation:
    "exams:dtstart:reasonable-time:earliest": [8, 0, 0],
    "exams:dtstart:reasonable-time:latest": [20, 0, 0],
}

if hasattr(settings, "ADMINS"):
    DEFAULT["admin_contact"] = getattr(settings, "ADMINS")[0]


def get(setting):
    """
    get(setting) -> value

    setting should be a string representing the application settings to
    retrieve.
    """
    assert setting in DEFAULT, "the setting %r has no default value" % setting
    app_settings = getattr(settings, CONFIG_NAME, DEFAULT)
    return app_settings.get(setting, DEFAULT[setting])
