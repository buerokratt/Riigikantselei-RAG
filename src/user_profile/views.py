from django.contrib.auth.models import User
from rest_framework import status, viewsets
from rest_framework.authentication import BasicAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from user_profile.models import UserProfile
from user_profile.permissions import UserProfilePermission  # type: ignore
from user_profile.serializers import (
    LimitSerializer,
    UserCreateSerializer,
    UserProfileReadOnlySerializer,
)


class GetTokenView(APIView):
    authentication_classes = (BasicAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request: Request) -> Response:
        token, _ = Token.objects.get_or_create(user=request.user)
        content = {'token': token.key}
        return Response(content)


class UserProfileViewSet(viewsets.ViewSet):
    # TODO here: pagination_class?
    authentication_classes = (TokenAuthentication,)
    permission_classes = (UserProfilePermission,)

    def create(self, request: Request) -> Response:
        request_serializer = UserCreateSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        auth_user = User.objects.create_user(
            username=request_serializer.validated_data['username'],
            password=request_serializer.validated_data['password'],
            email=request_serializer.validated_data['email'],
            first_name=request_serializer.validated_data['first_name'],
            last_name=request_serializer.validated_data['last_name'],
        )
        user_profile = UserProfile(auth_user=auth_user)
        user_profile.save()

        response_serializer = UserProfileReadOnlySerializer(user_profile)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    # pylint: disable=invalid-name
    def retrieve(self, request: Request, pk: int) -> Response:
        auth_user = get_object_or_404(User.objects.all(), pk=pk)
        user_profile = auth_user.user_profile

        self.check_object_permissions(request, user_profile)

        serializer = UserProfileReadOnlySerializer(user_profile)
        return Response(serializer.data)

    # pylint: disable=unused-argument
    def list(self, request: Request) -> Response:
        user_profiles = UserProfile.objects.all()

        serializer = UserProfileReadOnlySerializer(user_profiles, many=True)
        return Response(serializer.data)

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True, methods=['post'])
    def accept(self, request: Request, pk: int) -> Response:
        return _set_acceptance(pk, True)

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True, methods=['post'])
    def decline(self, request: Request, pk: int) -> Response:
        return _set_acceptance(pk, False)

    # pylint: disable=unused-argument,invalid-name
    @action(detail=True, methods=['post'])
    def ban(self, request: Request, pk: int) -> Response:
        auth_user = get_object_or_404(User.objects.all(), pk=pk)
        user_profile = auth_user.user_profile

        user_profile.is_allowed_to_spend_resources = False
        user_profile.save()

        return Response()

    # pylint: disable=invalid-name
    @action(detail=True, methods=['post'])
    def set_limit(self, request: Request, pk: int) -> Response:
        serializer = LimitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        auth_user = get_object_or_404(User.objects.all(), pk=pk)
        user_profile = auth_user.user_profile

        user_profile.usage_limit_is_default = False
        user_profile.custom_usage_limit_euros = serializer.validated_data['limit']
        user_profile.save()

        return Response()


# pylint: disable=invalid-name
def _set_acceptance(pk: int, to_accept: bool) -> Response:
    auth_user = get_object_or_404(User.objects.all(), pk=pk)
    user_profile = auth_user.user_profile

    if user_profile.is_reviewed:
        raise ParseError('Can not set acceptance for an already accepted user.')

    user_profile.is_reviewed = True
    user_profile.is_accepted = to_accept
    user_profile.is_allowed_to_spend_resources = to_accept
    user_profile.save()

    return Response()


# TODO here: something to change and reset password?
