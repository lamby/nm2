# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.db import models
import re


class FingerprintField(models.CharField):
    description = "CharField that holds hex digits, without spaces, in uppercase"
    re_spaces = re.compile(r"\s+")
    re_invalid = re.compile(r"[^0-9A-Fa-f]+")

    @classmethod
    def clean_fingerprint(cls, value):
        # Refuse all non-strings
        if not isinstance(value, basestring): return None
        # Remove spaces
        value = cls.re_spaces.sub("", value)
        # Convert empty strings to None
        if not value: return None
        # Refuse strings with non-hex characters
        if cls.re_invalid.search(value): return None
        # Refuse hex strings whose length does not match a fingerprint
        if len(value) != 32 and len(value) != 40: return None
        # Uppercase the result
        return value.upper()

    ## not really useful, because in Person this is blank=True which not cleaned / validated
    def to_python(self, value):
        """
        Converts a value from the database to a python object
        """
        value = super(FingerprintField, self).to_python(value)
        return self.clean_fingerprint(value)

    def get_prep_value(self, value):
        """
        Converts a value from python to the DB
        """
        value = super(FingerprintField, self).get_prep_value(value)
        return self.clean_fingerprint(value)

    def formfield(self, **kwargs):
        # bypass our parent to fix "maxlength" attribute in widget: fingerprint
        # with spaces are 50 chars to allow easy copy-and-paste
        if 'max_length' not in kwargs:
            kwargs.update({'max_length': 50})
        return super(FingerprintField, self).formfield(**kwargs)


# Implementation notes
#
#  * Multiple NULL values in UNIQUE fields
#    They are supported in sqlite, postgresql and mysql, and that is good
#    enough.
#    See http://www.sqlite.org/nulls.html
#    See http://stackoverflow.com/questions/454436/unique-fields-that-allow-nulls-in-django
#        for possible Django gotchas
#  * Denormalised fields
#    Some limited redundancy is tolerated for convenience, but it is
#    checked/enforced/recomputed during daily maintenance procedures
#
#
# See http://stackoverflow.com/questions/454436/unique-fields-that-allow-nulls-in-django
#
# This is used for uid fields, that need to be enforced to be unique EXCEPT
# when they are empty
#
class CharNullField(models.CharField):
    description = "CharField that stores NULL but returns ''"

    # this is the value right out of the db, or an instance
    def to_python(self, value):
       if isinstance(value, models.CharField): # if an instance, just return the instance
           return value
       if value is None:
           # if the db has a NULL, convert it into the Django-friendly '' string
           return ""
       else:
           # otherwise, return just the value
           return value

    # catches value right before sending to db
    def get_db_prep_value(self, value, connection, prepared=False):
       if value=="":
           # if Django tries to save '' string, send the db None (NULL)
           return None
       else:
           # otherwise, just pass the value
           return value

