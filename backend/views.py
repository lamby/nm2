from rest_framework import viewsets
from .serializers import PersonSerializer
from . import models as bmodels

class PersonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Export process information
    """
    queryset = bmodels.Person.objects.all().order_by("uid")
    serializer_class = PersonSerializer
