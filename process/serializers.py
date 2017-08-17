from rest_framework import serializers
import backend.serializers as bserializers
import process.models as pmodels

class ProcessSerializer(serializers.HyperlinkedModelSerializer):
    frozen_by = serializers.HyperlinkedRelatedField(read_only=True, view_name="persons-detail")
    approved_by = serializers.HyperlinkedRelatedField(read_only=True, view_name="persons-detail")

    class Meta:
        model = pmodels.Process
        fields = (
            'id', 'person', 'applying_for', 'started',
            'frozen_by', 'frozen_time',
            'approved_by', 'approved_time',
            'closed',
            'fd_comment',
            'rt_request', 'rt_ticket')


    def __init__(self, *args, **kw):
        super().__init__(*args, **kw)

        self.fields['person'] = bserializers.PersonSerializer(context=self.context)

        # See https://stackoverflow.com/questions/33459501/django-rest-framework-change-serializer-or-add-field-based-on-authentication
        fields = set((
            'id', 'person', 'applying_for', 'started',
            'frozen_by', 'frozen_time',
            'approved_by', 'approved_time',
            'closed', 'rt_ticket'))

        request = kw["context"].get("request")
        if request is not None and not request.user.is_anonymous:
            if request.user.is_admin:
                fields.update(('fd_comment', 'rt_request'))

        for field_name in self.fields.keys() - fields:
            self.fields.pop(field_name)
