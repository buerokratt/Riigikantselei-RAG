from django.db.models import QuerySet
from rest_framework import views, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from api.utilities.elastic import ElasticCore
from core.models import CoreVariable
from core.serializers import CoreVariableSerializer
from user_profile.permissions import (  # type: ignore
    IsAcceptedPermission,
    IsManagerPermission,
)


class ElasticDocumentDetailView(views.APIView):
    permission_classes = (IsAcceptedPermission,)

    def get(
        self, request: Request, index: str, document_id: str  # pylint: disable=unused-argument
    ) -> Response:
        elastic_core = ElasticCore()
        text = elastic_core.get_document_content(index, document_id)
        return Response({'text': text})


class CoreVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = CoreVariableSerializer
    permission_classes = (IsManagerPermission,)

    def get_queryset(self) -> QuerySet:
        return CoreVariable.objects.all()
