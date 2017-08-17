from rest_framework import serializers
import backend.models as bmodels

class PersonSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = bmodels.Person
        fields = (
            'username', 'is_staff',
            'cn', 'mn', 'sn',
            'email', 'email_ldap',
            'bio',
            'uid',
            'status',
            'status_changed',
            'fd_comment',
        )
