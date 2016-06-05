# coding: utf8
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from django import forms


class StatementForm(forms.Form):
    statement = forms.CharField(label="Signed statement", widget=forms.Textarea(attrs={"rows": 25, "cols": 80}))

    def __init__(self, *args, **kw):
        self.fpr = kw.pop("fpr")
        super(StatementForm, self).__init__(*args, **kw)

    def clean_statement(self):
        from keyring.models import Key
        text = self.cleaned_data["statement"]

        try:
            key = Key.objects.get_or_download(self.fpr)
        except RuntimeError as e:
            raise forms.ValidationError("Cannot download the key: " + unicode(e))

        try:
            plaintext = key.verify(text)
        except RuntimeError as e:
            raise forms.ValidationError("Cannot verify the signature: " + unicode(e))

        return (text, plaintext)
