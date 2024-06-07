from typing import Optional

from celery.result import AsyncResult
from django.urls import reverse
from rest_framework import viewsets, views
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import CoreVariable
from .serializers import CoreVariableSerializer, OpenAISerializer
from .tasks import commit_openai_api_call


# TODO: Change the permissions schema, left at AllowAny to allow for easy demo and rapid prototyping.

class AsyncResultView(views.APIView):
    permission_classes = (AllowAny,)

    def get(self, request, task_id: str):
        result = AsyncResult(task_id)

        response = {
            "id": result.id,
            "status": result.status,
            "result": result.result
        }

        if response["status"] == "FAILURE" or response["status"] == "RETRY":
            # During errors the result of the task will be a Python exception so to make it JSON serializable as an output we convert it to a string.
            response["error_type"] = type(response["result"]).__name__
            response["result"] = str(response["result"])

        return Response(response)


class OpenAIView(views.APIView):
    serializer_class = OpenAISerializer
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        input_text: str = serializer.validated_data['input_text']
        system_text: Optional[str] = serializer.validated_data['system_text']
        model: str = serializer.validated_data['model']

        task: AsyncResult = commit_openai_api_call.s(system_text, input_text, model).apply_async()
        relative_path = reverse("async_result", kwargs={"task_id": task.task_id})
        return Response(
            {
                "url": request.build_absolute_uri(relative_path),
                "task_id": task.task_id
            }
        )


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
