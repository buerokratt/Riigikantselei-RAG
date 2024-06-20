from celery.result import AsyncResult
from django.db.models import QuerySet
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response

from core.models import CoreVariable, TextSearchConversation, TextSearchQueryResult
from core.serializers import (
    ConversationSetTitleSerializer,
    CoreVariableSerializer,
    TextSearchConversationCreateSerializer,
    TextSearchConversationReadOnlySerializer,
    TextSearchQuerySubmitSerializer,
)
from user_profile.permissions import (  # type: ignore
    CanSpendResourcesPermission,
    IsAcceptedPermission,
    IsManagerPermission,
)


class CoreVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = CoreVariableSerializer
    permission_classes = (IsManagerPermission,)

    def get_queryset(self) -> QuerySet:
        return CoreVariable.objects.all()


class AsyncResultView(views.APIView):
    permission_classes = (CanSpendResourcesPermission,)

    # pylint: disable=unused-argument

    # Since checking on others' async results is not harmful on a prototype level,
    # we don't bother checking if celery_task_id refers to the user's own task
    def get(self, request: Request, celery_task_id: str) -> Response:
        async_result = AsyncResult(celery_task_id)

        response = {'status': async_result.status}

        if async_result.status == 'FAILURE':
            # During errors the result of the task will be a Python exception
            # so to make it JSON serializable as an output we convert it to a string.
            response['result'] = str(async_result.result)
            response['error_type'] = type(async_result.result).__name__
            # TODO: should we display failed queries in the frontend "chat history"
            #  on later visits as well? If yes, we should save a TextSearchQueryResult here.
            #  If yes, also, should we prevent them from being sent to the LLM?
            return Response(response)

        response['error_type'] = None

        if async_result.status == 'SUCCESS':
            # On success the result of the task will be the output of the Celery task chain.
            # The output is a dict of all the input data needed to create a TextSearchQueryResult.
            # To separate testing of view and model logic from testing of RAG logic,
            # the TextSearchQueryResult is created here.
            query_result_parameters = async_result.result
            query_result_parameters['conversation'] = TextSearchConversation.objects.get(
                id=query_result_parameters['conversation']
            )

            query_result = TextSearchQueryResult.objects.create(**query_result_parameters)
            response['result'] = query_result.response

        else:
            response['result'] = None

        return Response(response)


class TextSearchConversationViewset(viewsets.ViewSet):
    permission_classes = (IsAcceptedPermission,)

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

    @action(detail=True, methods=['post'], permission_classes=(CanSpendResourcesPermission,))
    def chat(self, request: Request, pk: int) -> Response:
        # Prevent anyone from changing other users' data.
        # We do it here, not self.check_object_permissions, because we want to return 404, not 403,
        # because 403 implies that the resource exists and a non-manager should not know even that.
        queryset = TextSearchConversation.objects.filter(auth_user=request.user)
        get_object_or_404(queryset, id=pk)

        request_serializer = TextSearchQuerySubmitSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        response = request_serializer.save(conversation_id=pk)
        return Response(response)
