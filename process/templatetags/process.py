from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def process_status(process, view):
    from process.mixins import compute_process_status
    return compute_process_status(process, view.visitor, view.visit_perms)
