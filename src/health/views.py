# pylint: disable=unused-argument,var-annotated,no-untyped-def
from rest_framework import status, views
from rest_framework.decorators import permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .utils import get_elastic_status, get_redis_status, get_version


@permission_classes((AllowAny,))
class HealthView(views.APIView):
    def get(self, request) -> Response:
        """Returns health statistics about host machine and running services."""
        # API status
        api_status = {'services': {}, 'api': {}}
        api_status['services']['elastic'] = get_elastic_status()
        api_status['services']['redis'] = get_redis_status()
        api_status['api']['version'] = get_version()

        return Response(api_status, status=status.HTTP_200_OK)
