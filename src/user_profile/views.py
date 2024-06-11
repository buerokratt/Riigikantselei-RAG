from django.conf import settings
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from rest_framework import status, viewsets
from rest_framework.authentication import BasicAuthentication, TokenAuthentication
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ParseError
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.renderers import TemplateHTMLRenderer
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from user_profile.models import PasswordResetToken, UserProfile
from user_profile.permissions import UserProfilePermission  # type: ignore
from user_profile.serializers import (
    EmailSerializer,
    LimitSerializer,
    PasswordResetSerializer,
    PasswordSerializer,
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
    authentication_classes = (TokenAuthentication,)
    permission_classes = (UserProfilePermission,)

    # pylint: disable=unused-argument,invalid-name

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

    def retrieve(self, request: Request, pk: int) -> Response:
        auth_user = get_object_or_404(User.objects.all(), pk=pk)
        user_profile = auth_user.user_profile

        self.check_object_permissions(request, user_profile)

        serializer = UserProfileReadOnlySerializer(user_profile)
        return Response(serializer.data)

    def list(self, request: Request) -> Response:
        user_profiles = UserProfile.objects.all()

        serializer = UserProfileReadOnlySerializer(user_profiles, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def accept(self, request: Request, pk: int) -> Response:
        return _set_acceptance(pk, True)

    @action(detail=True, methods=['post'])
    def decline(self, request: Request, pk: int) -> Response:
        return _set_acceptance(pk, False)

    @action(detail=True, methods=['post'])
    def ban(self, request: Request, pk: int) -> Response:
        auth_user = get_object_or_404(User.objects.all(), pk=pk)
        user_profile = auth_user.user_profile

        user_profile.is_allowed_to_spend_resources = False
        user_profile.save()

        return Response()

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

    @action(detail=False, methods=['post'])
    def change_password(self, request: Request) -> Response:
        serializer = PasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        auth_user = request.user
        auth_user.set_password(serializer.validated_data['password'])
        auth_user.save()

        return Response()

    @action(detail=False, methods=['post'])
    def request_password_reset(self, request: Request) -> Response:
        serializer = EmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data['email']

        auth_user = User.objects.get(email=email)
        token = PasswordResetToken(auth_user=auth_user)
        token.save()

        password_reset_endpoint = reverse(
            'user_profile-confirm-password-reset', kwargs={'pk': token.key}
        )
        password_reset_url = settings.BASE_URL + password_reset_endpoint
        content = render_to_string(
            'password_reset_email.txt',
            context={
                'service_name': settings.SERVICE_NAME,
                'password_reset_url': password_reset_url,
            },
        )

        result = send_mail(
            subject=f'{settings.SERVICE_NAME} parooli lähtestamine',
            message=content,
            recipient_list=(email,),
            from_email=settings.DEFAULT_FROM_EMAIL,
        )
        if result != 1:
            raise APIException('Sending email failed.')

        return Response()

    # TODO here: test manually
    @action(
        detail=True,
        methods=['get'],
        renderer_classes=(TemplateHTMLRenderer,),
    )
    def confirm_password_reset(self, request: Request, pk: int) -> Response:
        token = get_object_or_404(PasswordResetToken.objects.all(), key=pk)
        return Response({'token': token.key}, template_name='password_reset_page.html')

    @action(detail=False, methods=['post'])
    def reset_password(self, request: Request) -> Response:
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        token = get_object_or_404(
            PasswordResetToken.objects.all(), key=serializer.validated_data['token']
        )
        auth_user = token.auth_user
        auth_user.set_password(serializer.validated_data['password'])
        auth_user.save()

        PasswordResetToken.objects.filter(auth_user=auth_user).delete()

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
