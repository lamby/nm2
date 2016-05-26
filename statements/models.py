# coding: utf-8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django.db import models
from django.utils.translation import ugettext_lazy as _
from backend.fields import FingerprintField
from backend.models import Person, Fingerprint

# Types of signed statements used by the site
STATEMENT_TYPES = [
    ("sc_dmup", "SC/DFSG/DMUP agreement"),
    ("advocacy", "Advocacy"),
]


class Statement(models.Model):
    """
    A signed statement
    """
    fpr = models.ForeignKey(Fingerprint, help_text=_("Fingerprint used to verify the statement"))
    type = models.CharField(verbose_name=_("Statement type"), max_length=16, choices=STATEMENT_TYPES)
    statement = models.TextField(verbose_name=_("Signed statement"), blank=True)
    statement_verified = models.DateTimeField(null=True, help_text=_("When the statement has been verified to have valid wording (NULL if it has not)"))
    uploaded_by = models.ForeignKey(Person, null=True, help_text=_("Person who uploaded the statement"))

    def __unicode__(self):
        return "{}:{}".format(self.fpr, self.type)

    @property
    def status(self):
        if self.statement_verified: return "verified"
        if self.statement: return "unverified"
        return "missing"

    def get_key(self):
        from keyring.models import Key
        return Key.objects.get_or_download(self.fpr.fpr)
