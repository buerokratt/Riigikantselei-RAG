from rest_framework import viewsets
from rest_framework.permissions import AllowAny

from .models import CoreVariable
from .serializers import CoreVariableSerializer


class CoreVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = CoreVariableSerializer

    # TODO here: Change this after authentication is set up.
    permission_classes = (
        AllowAny,
        # IsAdminUser,
    )

    def get_queryset(self):
        return CoreVariable.objects.all()
