# pylint: disable=unused-argument
from typing import Any, Dict

from rest_framework import status, views
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from health.utils import get_elastic_status, get_redis_status, get_version


@permission_classes((AllowAny,))
class HealthView(views.APIView):
    def get(self, request: Request) -> Response:
        """Returns health statistics about host machine and running services."""
        api_status: Dict[str, Any] = {'services': {}, 'api': {}}
        api_status['services']['elastic'] = get_elastic_status()
        api_status['services']['redis'] = get_redis_status()
        api_status['api']['version'] = get_version()

        return Response(api_status, status=status.HTTP_200_OK)
