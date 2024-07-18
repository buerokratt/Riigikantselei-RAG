from django.db import transaction
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from api.utilities.core_settings import get_core_setting
from document_search.models import DocumentSearchConversation, DocumentSearchQueryResult, DocumentTask, DocumentAggregationResult, AggregationTask
from document_search.serializers import DocumentSearchConversationSerializer, DocumentSearchChatSerializer
from document_search.tasks import generate_aggregations, generate_openeai_prompt, send_document_search, save_openai_results_for_doc
from user_profile.permissions import IsAcceptedPermission, CanSpendResourcesPermission


# Create your views here.
class DocumentSearchConversationViewset(viewsets.ModelViewSet):
    queryset = DocumentSearchConversation.objects.all()
    permission_classes = (IsAcceptedPermission,)
    serializer_class = DocumentSearchConversationSerializer

    def get_queryset(self):
        return DocumentSearchConversation.objects.filter(auth_user=self.request.user)

    def perform_create(self, serializer):
        system_input = serializer.validated_data['system_input']
        user_input = serializer.validated_data['user_input']

        system_input = system_input or get_core_setting('OPENAI_SYSTEM_MESSAGE')
        instance = serializer.save(title=user_input.capitalize(), auth_user=self.request.user, system_input=system_input)

        result = DocumentAggregationResult.objects.create(conversation=serializer.instance)
        aggregation_task = AggregationTask.objects.create(result=result)

        with transaction.atomic():
            transaction.on_commit(lambda: generate_aggregations.s(instance.pk, user_input, result.uuid).apply_async())

    @action(detail=True, methods=['POST'], serializer_class=DocumentSearchChatSerializer, permission_classes=(CanSpendResourcesPermission,))
    def chat(self, request, pk=None):
        serializer = DocumentSearchChatSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        index = serializer.validated_data['index']

        instance = self.get_object()
        user_input = instance.user_input
        result = DocumentSearchQueryResult.objects.create(conversation=instance, user_input=user_input)
        DocumentTask.objects.create(result=result)

        prompt_task = generate_openeai_prompt.s(pk, index)
        gpt_task = send_document_search.s(pk, user_input, result.uuid)
        save_task = save_openai_results_for_doc.s(pk, result.uuid)

        with transaction.atomic():
            chain = (prompt_task | gpt_task | save_task)
            transaction.on_commit(lambda: chain.apply_async())

        instance.refresh_from_db()
        data = DocumentSearchConversationSerializer(instance).data
        return Response(data)
