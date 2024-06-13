from django.db.models import QuerySet
from rest_framework import viewsets

from user_profile.permissions import IsManagerPermission  # type: ignore

from .models import CoreVariable
from .serializers import CoreVariableSerializer


class CoreVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = CoreVariableSerializer
    permission_classes = (IsManagerPermission,)

    def get_queryset(self) -> QuerySet:
        return CoreVariable.objects.all()
