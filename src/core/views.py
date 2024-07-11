from django.db.models import QuerySet
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response

from api.utilities.core_settings import get_core_setting
from api.utilities.elastic import ElasticCore
from core.models import CoreVariable, TextSearchConversation, DocumentSearchConversation
from core.serializers import (
    ConversationSetTitleSerializer,
    CoreVariableSerializer,
    TextSearchConversationBulkDeleteSerializer,
    TextSearchConversationCreateSerializer,
    TextSearchConversationReadOnlySerializer,
    TextSearchQuerySubmitSerializer, DocumentSearchConversationSerializer, EmptySerializer, DocumentSearchDocumentTypeSerializer,
)
from core.tasks import vectorize_and_aggregate, generate_doc_search_context
from user_profile.permissions import (  # type: ignore
    CanSpendResourcesPermission,
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


class TextSearchConversationViewset(viewsets.ViewSet):
    permission_classes = (IsAcceptedPermission,)
    serializer_class = TextSearchConversationCreateSerializer

    # pylint: disable=unused-argument,invalid-name

    # create() uses user_input to name the conversation, but does not query the LLM.
    # After creating the conversation, the frontend must still call chat() with the input.
    def create(self, request: Request) -> Response:
        request_serializer = TextSearchConversationCreateSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        conversation = request_serializer.save(auth_user=request.user)

        response_serializer = TextSearchConversationReadOnlySerializer(conversation)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    # Since the destroy() function for the viewset only takes a single id for an
    # argument it's better to make deletion through an extra action as you can do
    # single and multiple deletes in one go.
    @action(
        detail=False,
        methods=['DELETE'],
        serializer_class=TextSearchConversationBulkDeleteSerializer,
    )
    def bulk_destroy(self, request: Request) -> Response:
        serializer = TextSearchConversationBulkDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data['ids']
        TextSearchConversation.objects.filter(auth_user=request.user, id__in=ids).delete()

        return Response({'detail': 'Deleted chosen objects!'}, status=status.HTTP_204_NO_CONTENT)

    def retrieve(self, request: Request, pk: int) -> Response:
        queryset = TextSearchConversation.objects.filter(auth_user=request.user)
        conversation = get_object_or_404(queryset, id=pk)

        serializer = TextSearchConversationReadOnlySerializer(conversation)
        return Response(serializer.data)

    def list(self, request: Request) -> Response:
        conversations = TextSearchConversation.objects.filter(auth_user=request.user)

        serializer = TextSearchConversationReadOnlySerializer(conversations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def set_title(self, request: Request, pk: int) -> Response:
        # Prevent anyone from changing other users' data.
        # We do it here, not self.check_object_permissions, because we want to return 404, not 403,
        # because 403 implies that the resource exists and a non-manager should not know even that.
        queryset = TextSearchConversation.objects.filter(auth_user=request.user)
        conversation = get_object_or_404(queryset, id=pk)

        serializer = ConversationSetTitleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        conversation.title = serializer.validated_data['title']
        conversation.save()

        return Response()

    @action(
        detail=True,
        methods=['post'],
        permission_classes=(CanSpendResourcesPermission,),
        serializer_class=TextSearchQuerySubmitSerializer,
    )
    def chat(self, request: Request, pk: int) -> Response:
        # Prevent anyone from changing other users' data.
        # We do it here, not self.check_object_permissions, because we want to return 404, not 403,
        # because 403 implies that the resource exists and a non-manager should not know even that.
        queryset = TextSearchConversation.objects.filter(auth_user=request.user)
        get_object_or_404(queryset, id=pk)

        request_serializer = TextSearchQuerySubmitSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_serializer.save(conversation_id=pk)

        # Mostly needed for tests but helpful to fetch a more updated task instance.
        conversation = TextSearchConversation.objects.get(pk=pk)
        data = TextSearchConversationReadOnlySerializer(conversation).data
        return Response(data)


class DocumentSearchConversationViewSet(viewsets.ModelViewSet):
    permission_classes = (IsAcceptedPermission,)
    serializer_class = DocumentSearchConversationSerializer

    def get_queryset(self):
        user = self.request.user
        return DocumentSearchConversation.objects.filter(auth_user=user)

    def perform_create(self, serializer):
        serializer.save(auth_user=self.request.user)

    @action(detail=True, methods=['POST'], serializer_class=EmptySerializer)
    def aggregate_documents(self, request: Request, pk: int) -> Response:
        instance: DocumentSearchConversation = self.get_object()

        document_type_field = get_core_setting('ELASTICSEARCH_DOCUMENT_TYPE_FIELD')
        year_field = get_core_setting('ELASTICSEARCH_YEAR_FIELD')
        vector_field = get_core_setting('ELASTICSEARCH_VECTOR_FIELD')

        async_task = vectorize_and_aggregate.s(
            pk,
            vector_field,
            document_type_field,
            year_field
        ).apply_async()

        instance.refresh_from_db()
        return Response(DocumentSearchConversationSerializer(instance).data)

    @action(detail=True, methods=['POST'], permission_classes=(CanSpendResourcesPermission,), serializer_class=DocumentSearchDocumentTypeSerializer)
    def commit_openai_search(self, request: Request, pk: int) -> Response:
        serializer = DocumentSearchDocumentTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        document_type = serializer.validated_data['document_type']
        async_task = generate_doc_search_context.s(pk, document_type).apply_async()

        instance = DocumentSearchConversation.objects.get(pk=pk)
        response = DocumentSearchConversationSerializer(instance).data
        return Response(response)
