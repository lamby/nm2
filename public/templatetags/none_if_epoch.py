from django import template
from django.utils.timezone import utc
import datetime

register = template.Library()

@register.filter
def none_if_epoch(value):
    epoch = datetime.datetime(1970, 1, 1, tzinfo=utc)
    if value == epoch:
        return None
    else:
        return value
