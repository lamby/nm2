from rest_framework import serializers
import backend.serializers as bserializers
import process.models as pmodels

class ProcessSerializer(serializers.HyperlinkedModelSerializer):
    person = serializers.HyperlinkedRelatedField(read_only=True, view_name="persons-detail")
    frozen_by = serializers.HyperlinkedRelatedField(read_only=True, view_name="persons-detail")
    approved_by = serializers.HyperlinkedRelatedField(read_only=True, view_name="persons-detail")

    class Meta:
        model = pmodels.Process
        fields = (
            'person', 'applying_for', 'started',
            'frozen_by', 'frozen_time',
            'approved_by', 'approved_time',
            'closed',
            'fd_comment',
            'rt_request', 'rt_ticket')
