from celery.result import AsyncResult
from django.urls import reverse
from rest_framework import views, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.utilities.core_settings import get_core_setting

from .models import ChatGPTConversation, CoreVariable
from .serializers import (
    ChatGPTConversationSerializer,
    CoreVariableSerializer,
    OpenAISerializer,
)
from .tasks import commit_openai_api_call

# TODO: Change the permissions schema, left at AllowAny to allow for easy demo and rapid prototyping.


class AsyncResultView(views.APIView):
    permission_classes = (AllowAny,)

    def get(self, request, task_id: str):
        result = AsyncResult(task_id)

        response = {'id': result.id, 'status': result.status, 'result': result.result}

        if response['status'] == 'FAILURE' or response['status'] == 'RETRY':
            # During errors the result of the task will be a Python exception so to make it JSON serializable as an output we convert it to a string.
            response['error_type'] = type(response['result']).__name__
            response['result'] = str(response['result'])

        return Response(response)


class GPTConversationViewset(viewsets.ModelViewSet):
    permission_classes = (
        AllowAny,
        # IsAuthenticated
    )
    serializer_class = ChatGPTConversationSerializer

    def perform_create(self, serializer):
        system_text = serializer.validated_data['system_input']
        system_text = system_text or get_core_setting('OPENAI_SYSTEM_MESSAGE')
        serializer.save(author=self.request, system_input=system_text)

    @action(methods=['POST'], detail=True, serializer_class=OpenAISerializer)
    def chat(self, request, pk: int):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        input_text: str = serializer.validated_data['input_text']
        model: str = serializer.validated_data['model']

        task: AsyncResult = commit_openai_api_call.s(pk, input_text, model).apply_async()
        relative_path = reverse('async_result', kwargs={'task_id': task.task_id})
        response = {'url': request.build_absolute_uri(relative_path), 'task_id': task.task_id}
        return Response(response)

    # TODO: Remove this.
    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return ChatGPTConversation.objects.filter(author=user)
        else:
            return ChatGPTConversation.objects.all()

    class Meta:
        model = ChatGPTConversation


class CoreVariableViewSet(viewsets.ModelViewSet):
    pagination_class = None
    serializer_class = CoreVariableSerializer

    # TODO: Changed this after authentication is set up.
    permission_classes = (
        AllowAny,
        # IsAdminUser,
    )

    def get_queryset(self):
        return CoreVariable.objects.all()
