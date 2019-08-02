"""
Signals for the exams app.
"""
from __future__ import print_function, unicode_literals

from django.db.utils import IntegrityError
from django.template.defaultfilters import slugify

################################################################

################################################################


def exam_m2m_changed_handler(
    sender, instance, action, reverse, model, pk_set, **kwargs
):
    """
    This could be better, but works for now.

    * ``pre_add`` checks for an exam with the same name and
        (overlapping) sections.
        See also ``ExamForm`` for validation, rather than the
        integrity check.
    * ``post_add`` fixes up slugs.
    """
    if action == "pre_add":
        for section_pk in pk_set:
            qs = instance.__class__.objects.filter(
                verbose_name=instance.verbose_name, sections__pk=section_pk
            )
            if instance.pk:
                qs.exclude(pk=instance.pk)
            if qs.count():
                raise IntegrityError(
                    "An exam with the name {0!r} already exists for this section: {1!r}".format(
                        instance.verbose_name, qs[0].course
                    )
                )

    if action == "post_add":
        if instance.slug and not instance.slug.startswith("-save-fix-"):
            return
        # there is no slug or a save fix is indicated.
        instance.slug = instance.course
        instance.slug += " "
        section_list = instance.sections.all()
        if len(section_list) == 1:
            instance.slug += section_list.get().section_name + " "
        instance.slug += instance.verbose_name
        instance.slug += " "
        instance.slug += "{}".format(section_list[0].term)
        instance.slug = slugify(instance.slug)
        base_slug = instance.slug
        n = 1
        while True:
            if not instance._meta.model.objects.filter(slug=instance.slug).exists():
                break
            instance.slug = base_slug + "-{}".format(n)
            n += 1
        # print('Updated slug to %r' % instance.slug)
        instance.save()


################################################################
