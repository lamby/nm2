



from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe

register = template.Library()

@register.filter
def process_status(process, view):
    from process.mixins import compute_process_status
    perms = getattr(view, "visit_perms", None)
    return compute_process_status(process, view.visitor, perms)
