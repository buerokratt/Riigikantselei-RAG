from typing import List

from django.db.models import QuerySet
from django.http import FileResponse, HttpResponseBase
from rest_framework import status, views, viewsets
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from api.utilities.elastic import ElasticCore
from core.models import CoreVariable, Dataset
from core.pdf import get_statistics_pdf_file_bytes
from core.serializers import (
    CoreVariableSerializer,
    DatasetSerializer,
    StatisticsSerializer,
)
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


class DatasetViewset(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = DatasetSerializer
    permission_classes = (IsAcceptedPermission,)

    def get_permissions(self) -> List:
        if self.action in ('create', 'update', 'partial_update'):
            self.permission_classes = [IsAdminUser, IsAcceptedPermission]  # type: ignore

        return super().get_permissions()

    def get_queryset(self) -> QuerySet:
        return Dataset.objects.all()


class StatisticsView(views.APIView):
    permission_classes = (IsAdminUser,)
    serializer_class = StatisticsSerializer

    def post(self, request: Request) -> HttpResponseBase:  # pylint: disable=unused-argument
        serializer = StatisticsSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        year = serializer.validated_data['year']
        month = serializer.validated_data['month']

        filename = f'statistics_{year}_{str(month).zfill(2)}.pdf'
        pdf_file_bytes = get_statistics_pdf_file_bytes(year, month)

        return FileResponse(pdf_file_bytes, as_attachment=True, filename=filename)
