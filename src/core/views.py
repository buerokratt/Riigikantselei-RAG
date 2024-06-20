from celery.result import AsyncResult
from django.db.models import QuerySet
from rest_framework import status, views, viewsets
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.reverse import reverse

from core.models import CoreVariable, TextSearchConversation
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

    # Since checking on others' async results is not harmful,
    # we don't bother checking if task_id refers to the user's own task
    def get(self, request: Request, task_id: str) -> Response:
        result = AsyncResult(task_id)

        response = {'id': result.id, 'status': result.status, 'result': result.result}

        if response['status'] == 'FAILURE' or response['status'] == 'RETRY':
            # During errors the result of the task will be a Python exception
            # so to make it JSON serializable as an output we convert it to a string.
            response['error_type'] = type(response['result']).__name__
            response['result'] = str(response['result'])

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

        async_task = request_serializer.save(conversation_id=pk)

        relative_path = reverse('async_result', kwargs={'task_id': async_task.task_id})
        response = {
            'url': request.build_absolute_uri(relative_path),
            'task_id': async_task.task_id,
        }
        return Response(response)
