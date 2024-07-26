from django.db import transaction
from django.db.models import QuerySet
from django.http import FileResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response

from core.models import CoreVariable, Dataset
from core.pdf import pdf_file_bytes_from_conversation
from core.serializers import ConversationSetTitleSerializer
from document_search.models import (
    AggregationTask,
    DocumentAggregationResult,
    DocumentSearchConversation,
    DocumentSearchQueryResult,
    DocumentTask,
)
from document_search.serializers import (
    DocumentSearchChatSerializer,
    DocumentSearchConversationSerializer,
)
from document_search.tasks import (
    generate_aggregations,
    generate_openai_prompt,
    save_openai_results_for_doc,
    send_document_search,
)
from user_profile.permissions import (  # type: ignore
    CanSpendResourcesPermission,
    IsAcceptedPermission,
)

# TODO: this file and its text_search sibling
#  differ in unnecessary ways (code that does the same thing is written differently)
#  and is way too similar in other ways (duplicated code).
#  Unify the unnecessarily different code and then refactor all shared code out.
#  Otherwise we will end up with different behaviour between workflows
#  and bugs will happen more easily.


class DocumentSearchConversationViewset(viewsets.ModelViewSet):
    queryset = DocumentSearchConversation.objects.all()
    permission_classes = (IsAcceptedPermission,)
    serializer_class = DocumentSearchConversationSerializer

    # pylint: disable=invalid-name

    def get_queryset(self) -> QuerySet:
        return DocumentSearchConversation.objects.filter(auth_user=self.request.user)

    def perform_create(self, serializer: DocumentSearchConversationSerializer) -> None:
        system_input = serializer.validated_data['system_input']
        user_input = serializer.validated_data['user_input']

        system_input = system_input or CoreVariable.get_core_setting('OPENAI_SYSTEM_MESSAGE')
        title = user_input[0].upper() + user_input[1:]
        instance = serializer.save(
            title=title, auth_user=self.request.user, system_input=system_input
        )

        result = DocumentAggregationResult.objects.create(conversation=serializer.instance)
        AggregationTask.objects.create(result=result)

        with transaction.atomic():
            transaction.on_commit(
                lambda: generate_aggregations.s(instance.pk, user_input, result.uuid).apply_async()
            )

    @action(
        detail=True,
        methods=['POST'],
        serializer_class=DocumentSearchChatSerializer,
        permission_classes=(CanSpendResourcesPermission,),
    )
    def chat(self, request: Request, pk: int) -> Response:
        serializer = DocumentSearchChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        instance: DocumentSearchConversation = self.get_object()

        user_input = serializer.validated_data['user_input']
        min_year = serializer.validated_data['min_year']
        max_year = serializer.validated_data['max_year']

        instance.min_year = min_year
        instance.max_year = max_year
        instance.save()

        result = DocumentSearchQueryResult.objects.create(
            conversation=instance, user_input=user_input
        )
        DocumentTask.objects.create(result=result)

        dataset_name = serializer.validated_data['dataset_name']
        dataset = get_object_or_404(Dataset.objects.all(), name=dataset_name)
        dataset_index_query = dataset.index

        prompt_task = generate_openai_prompt.s(pk, [dataset_index_query])
        gpt_task = send_document_search.s(pk, user_input, result.uuid)
        save_task = save_openai_results_for_doc.s(pk, result.uuid, dataset_name)

        with transaction.atomic():
            chain = prompt_task | gpt_task | save_task
            transaction.on_commit(chain.apply_async)

        instance.refresh_from_db()
        data = DocumentSearchConversationSerializer(instance).data
        return Response(data)

    @action(detail=True, methods=['post'])
    def set_title(self, request: Request, pk: int) -> Response:
        # Prevent anyone from changing other users' data.
        # We do it here, not self.check_object_permissions, because we want to return 404, not 403,
        # because 403 implies that the resource exists and a non-manager should not know even that.
        queryset = DocumentSearchConversation.objects.filter(auth_user=request.user)
        conversation = get_object_or_404(queryset, id=pk)

        serializer = ConversationSetTitleSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Ensure only the first letter is capitalized.
        title = serializer.validated_data['title']
        conversation.title = title[0].upper() + title[1:]
        conversation.save()

        return Response()

    @action(detail=True, methods=['get'])
    def pdf(self, request: Request, pk: int) -> FileResponse:
        # Prevent anyone from changing other users' data.
        # We do it here, not self.check_object_permissions, because we want to return 404, not 403,
        # because 403 implies that the resource exists and a non-manager should not know even that.
        queryset = DocumentSearchConversation.objects.filter(auth_user=request.user)
        conversation = get_object_or_404(queryset, id=pk)

        filename = f'riigikantselei_vestlus_{pk}.pdf'
        pdf_file_bytes = pdf_file_bytes_from_conversation(conversation)

        return FileResponse(pdf_file_bytes, as_attachment=True, filename=filename)
