from celery.result import AsyncResult
from django.db.models import QuerySet
from django.urls import reverse
from rest_framework import views, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from api.utilities.core_settings import get_core_setting
from user_profile.permissions import IsManagerPermission  # type: ignore

from .models import ChatGPTConversation, CoreVariable
from .serializers import (
    ChatGPTConversationSerializer,
    CoreVariableSerializer,
    OpenAISerializer,
)
from .tasks import commit_openai_api_call


# TODO here: Change the permissions
class AsyncResultView(views.APIView):
    permission_classes = (AllowAny,)

    # pylint: disable=unused-argument

    def get(self, request: Request, task_id: str) -> Response:
        result = AsyncResult(task_id)

        response = {'id': result.id, 'status': result.status, 'result': result.result}

        if response['status'] == 'FAILURE' or response['status'] == 'RETRY':
            # During errors the result of the task will be a Python exception
            # so to make it JSON serializable as an output we convert it to a string.
            response['error_type'] = type(response['result']).__name__
            response['result'] = str(response['result'])

        return Response(response)


class GPTConversationViewset(viewsets.ModelViewSet):
    permission_classes = (
        AllowAny,
        # IsAuthenticated
    )
    serializer_class = ChatGPTConversationSerializer

    # pylint: disable=invalid-name

    def perform_create(self, serializer: ChatGPTConversationSerializer) -> None:
        system_text = serializer.validated_data['system_input']
        system_text = system_text or get_core_setting('OPENAI_SYSTEM_MESSAGE')
        serializer.save(author=self.request, system_input=system_text)

    @action(methods=['POST'], detail=True, serializer_class=OpenAISerializer)
    def chat(self, request: Request, pk: int) -> Response:
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        input_text: str = serializer.validated_data['input_text']
        model: str = serializer.validated_data['model']

        task: AsyncResult = commit_openai_api_call.s(input_text, pk, model).apply_async()
        relative_path = reverse('async_result', kwargs={'task_id': task.task_id})
        response = {'url': request.build_absolute_uri(relative_path), 'task_id': task.task_id}
        return Response(response)

    # TODO: Remove this.
    def get_queryset(self) -> QuerySet:
        user = self.request.user
        if user.is_authenticated:
            return ChatGPTConversation.objects.filter(author=user)
        return ChatGPTConversation.objects.all()

    class Meta:
        model = ChatGPTConversation


class CoreVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = CoreVariableSerializer
    permission_classes = (IsManagerPermission,)

    def get_queryset(self) -> QuerySet:
        return CoreVariable.objects.all()
