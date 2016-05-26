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
