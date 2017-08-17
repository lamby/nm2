from rest_framework import serializers
import backend.models as bmodels

class PersonSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = bmodels.Person
        fields = (
            'id', 'username', 'is_staff',
            'cn', 'mn', 'sn', 'fullname',
            'email', 'email_ldap',
            'bio',
            'uid',
            'status',
            'status_changed',
            'fd_comment',
            'fpr',
        )

    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        # See https://stackoverflow.com/questions/33459501/django-rest-framework-change-serializer-or-add-field-based-on-authentication
        fields = set((
            'id', 'cn', 'mn', 'sn', 'fullname',
            'bio', 'uid',
            'status', 'status_changed',
            'fpr'))

        request = kw["context"].get("request")
        if request is not None and not request.user.is_anonymous:
            if request.user.is_dd:
                fields.update((
                    'username', 'is_staff',
                    'email'))
                
            if request.user.is_admin:
                fields.update(('email_ldap', 'fd_comment'))

        for field_name in self.fields.keys() - fields:
            self.fields.pop(field_name)
