from typing import Optional

from django.contrib.auth.models import User
from rest_framework import status, viewsets
from rest_framework.generics import get_object_or_404
from rest_framework.request import Request
from rest_framework.response import Response

from user_profile.models import UserProfile
from user_profile.permissions import UserProfilePermission  # type: ignore
from user_profile.serializers import UserCreateSerializer, UserProfileReadOnlySerializer


class UserProfileViewSet(viewsets.ViewSet):
    # TODO here: pagination_class?
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

    # pylint: disable=invalid-name,unused-argument
    def retrieve(self, request: Request, pk: Optional[int] = None) -> Response:
        auth_user = get_object_or_404(User.objects.all(), pk=pk)
        user = auth_user.user_profile

        self.check_object_permissions(request, user)

        serializer = UserProfileReadOnlySerializer(user)
        return Response(serializer.data)

    # pylint: disable=unused-argument
    def list(self, request: Request) -> Response:
        users = UserProfile.objects.all()

        serializer = UserProfileReadOnlySerializer(users, many=True)
        return Response(serializer.data)


# TODO here: more views
# @action(detail=True, methods=['post'])
# Admin saab kindlat kasutajat muuta (kinnitada või tagasi lükata, kasutust keelata, limiiti seada)
# Admin saab vaikimisi kasutuslimiiti muuta

# TODO here: something to change and reset password?
