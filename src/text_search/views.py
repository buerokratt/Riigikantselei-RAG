from django.db.models import QuerySet
from django.http import FileResponse
from django.utils.translation import gettext as _
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response

from core.pdf import get_conversation_pdf_file_bytes
from core.serializers import (
    ConversationBulkDeleteSerializer,
    ConversationSetTitleSerializer,
)
from text_search.models import TextSearchConversation
from text_search.serializers import (
    TextSearchConversationCreateSerializer,
    TextSearchConversationReadOnlySerializer,
    TextSearchQuerySubmitSerializer,
)
from user_profile.permissions import (  # type: ignore
    CanSpendResourcesPermission,
    IsAcceptedPermission,
)


class TextSearchConversationViewset(viewsets.ViewSet):
    permission_classes = (IsAcceptedPermission,)
    serializer_class = TextSearchConversationCreateSerializer

    # pylint: disable=unused-argument,invalid-name

    def get_queryset(self) -> QuerySet:
        # Never return conversations that are deleted or that are someone else's.
        # 404 will be returned in both situations,
        # as no user should know about the existence of these conversations
        # (403 would imply that it exists).
        return TextSearchConversation.objects.filter(auth_user=self.request.user, is_deleted=False)

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
        serializer_class=ConversationBulkDeleteSerializer,
    )
    def bulk_destroy(self, request: Request) -> Response:
        serializer = ConversationBulkDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ids = serializer.validated_data['ids']
        self.get_queryset().filter(id__in=ids).update(is_deleted=True)

        return Response({'detail': _('Deleted chosen objects!')}, status=status.HTTP_204_NO_CONTENT)

    def retrieve(self, request: Request, pk: int) -> Response:
        conversation = get_object_or_404(self.get_queryset(), id=pk)

        serializer = TextSearchConversationReadOnlySerializer(conversation)
        return Response(serializer.data)

    def list(self, request: Request) -> Response:
        serializer = TextSearchConversationReadOnlySerializer(self.get_queryset(), many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def set_title(self, request: Request, pk: int) -> Response:
        conversation = get_object_or_404(self.get_queryset(), id=pk)

        serializer = ConversationSetTitleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Ensure only the first letter is capitalized.
        title = serializer.validated_data['title']
        conversation.title = title[0].upper() + title[1:]
        conversation.save()

        return Response()

    @action(
        detail=True,
        methods=['post'],
        permission_classes=(CanSpendResourcesPermission,),
        serializer_class=TextSearchQuerySubmitSerializer,
    )
    def chat(self, request: Request, pk: int) -> Response:
        get_object_or_404(self.get_queryset(), id=pk)

        request_serializer = TextSearchQuerySubmitSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        request_serializer.save(conversation_id=pk)

        # Mostly needed for tests but helpful to fetch a more updated task instance.
        conversation = self.get_queryset().get(id=pk)
        data = TextSearchConversationReadOnlySerializer(conversation).data
        return Response(data)

    @action(detail=True, methods=['get'])
    def pdf(self, request: Request, pk: int) -> FileResponse:
        conversation = get_object_or_404(self.get_queryset(), id=pk)

        filename = f'riigikantselei_vestlus_{pk}.pdf'
        pdf_file_bytes = get_conversation_pdf_file_bytes(conversation)

        return FileResponse(pdf_file_bytes, as_attachment=True, filename=filename)
