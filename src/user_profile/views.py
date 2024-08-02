from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.translation import gettext as _
from rest_framework import status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    ParseError,
    ValidationError,
)
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from user_profile.models import PasswordResetToken, UserProfile
from user_profile.permissions import UserProfilePermission  # type: ignore
from user_profile.serializers import (
    EmailSerializer,
    LimitSerializer,
    LoginSerializer,
    PasswordResetSerializer,
    PasswordSerializer,
    UserCreateSerializer,
    UserProfileReadOnlySerializer,
)

# pylint: disable=unused-variable


class GetTokenView(APIView):
    permission_classes = (AllowAny,)
    serializer_class = LoginSerializer

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        username = serializer.validated_data['username']
        password = serializer.validated_data['password']

        if authenticate(request=request, username=username, password=password):
            user = User.objects.get(username=username)
            token, is_created = Token.objects.get_or_create(user=user)

            # TODO: Remove this later.
            if settings.DEBUG:
                login(request, user)

            response = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'token': token.key,
            }
            return Response(response, status=status.HTTP_200_OK)

        message = _('User and password do not match!')
        raise AuthenticationFailed(message)


class LogOutView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request: Request) -> Response:
        Token.objects.filter(user=request.user).delete()
        return Response()


class UserProfileViewSet(viewsets.ViewSet):
    permission_classes = (UserProfilePermission,)

    # pylint: disable=unused-argument,invalid-name

    def create(self, request: Request) -> Response:
        request_serializer = UserCreateSerializer(data=request.data)
        if not request_serializer.is_valid():
            return Response(request_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        auth_user = request_serializer.save()

        response_serializer = UserProfileReadOnlySerializer(auth_user.user_profile)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk: int) -> Response:
        # Prevent non-manager user from accessing other users' data.
        # We do it here, not self.check_object_permissions, because we want to return 404, not 403,
        # because 403 implies that the resource exists and a non-manager should not know even that.
        queryset = User.objects.all()
        if not request.user.user_profile.is_manager:
            queryset = User.objects.filter(id=request.user.id)

        auth_user = get_object_or_404(queryset, id=pk)
        user_profile = auth_user.user_profile

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

    @action(detail=True, methods=['post'], permission_classes=(IsAdminUser,))
    def set_superuser(self, request: Request, pk: int) -> Response:
        auth_user = get_object_or_404(User.objects.all(), id=pk)

        if auth_user == request.user:
            message = _('You can not change your own status!')
            raise ValidationError(message)

        # Ensure the two are equal and not mismatched.
        auth_user.is_staff = not auth_user.is_staff
        auth_user.is_superuser = auth_user.is_staff

        auth_user.save()

        # Since the IsAdminUser looks for is_staff it's the more relevant one out of these.
        # hence we display mostly it.
        response = {
            'detail': f'Set user {auth_user.username} admin status to {auth_user.is_staff}!',
            'state': auth_user.is_staff,
        }
        return Response(response)

    @action(detail=True, methods=['post'], permission_classes=(IsAdminUser,))
    def set_manager(self, request: Request, pk: int) -> Response:
        auth_user = get_object_or_404(User.objects.all(), id=pk)
        user_profile = auth_user.user_profile
        # We just switch whatever the state is.
        user_profile.is_manager = not user_profile.is_manager
        user_profile.save()
        response = {
            'detail': f'Set user {auth_user.username} manager status to {user_profile.is_manager}!',
            'state': user_profile.is_manager,
        }
        return Response(response)

    @action(detail=True, methods=['post'])
    def ban(self, request: Request, pk: int) -> Response:
        auth_user = get_object_or_404(User.objects.all(), id=pk)
        user_profile = auth_user.user_profile

        user_profile.is_allowed_to_spend_resources = False
        user_profile.save()

        return Response()

    @action(detail=True, methods=['post'])
    def set_limit(self, request: Request, pk: int) -> Response:
        serializer = LimitSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        auth_user = get_object_or_404(User.objects.all(), id=pk)
        user_profile = auth_user.user_profile

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

    @action(detail=False, methods=['post'], permission_classes=(AllowAny,))
    def request_password_reset(self, request: Request) -> Response:
        serializer = EmailSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Existence is checked in the serializer.
        email = serializer.validated_data['email']
        auth_user = User.objects.get(email=email)

        token = PasswordResetToken(auth_user=auth_user)
        token.save()

        password_reset_url = settings.BASE_URL + '/' + f'parooli-taastamine/{token.key}'
        content = render_to_string(
            template_name='password_reset_email.txt',
            context={
                'service_name': settings.SERVICE_NAME,
                'password_reset_url': password_reset_url,
            },
        )

        result = send_mail(
            subject='Parooli lähtestamine',
            message=content,
            recipient_list=(email,),
            from_email=f'{settings.EMAIL_DISPLAY_NAME} <{settings.DEFAULT_FROM_EMAIL}>',
        )
        if result != 1:
            message = _('Sending email failed.')
            raise APIException(message)

        return Response()

    @action(detail=False, methods=['post'], permission_classes=(AllowAny,))
    def confirm_password_reset(self, request: Request) -> Response:
        serializer = PasswordResetSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Its existence is already checked in the serializer.
        token = serializer.validated_data['token']
        token = PasswordResetToken.objects.get(key=token)

        auth_user = token.auth_user
        auth_user.set_password(serializer.validated_data['password'])
        auth_user.save()

        PasswordResetToken.objects.filter(auth_user=auth_user).delete()

        message = _('Your password has been reset!')
        return Response({'detail': message})


# pylint: disable=invalid-name
def _set_acceptance(pk: int, to_accept: bool) -> Response:
    auth_user = get_object_or_404(User.objects.all(), id=pk)
    user_profile = auth_user.user_profile

    if user_profile.is_reviewed:
        message = _('Can not set acceptance for an already accepted user.')
        raise ParseError(message)

    user_profile.is_reviewed = True
    user_profile.is_accepted = to_accept
    user_profile.is_allowed_to_spend_resources = to_accept
    user_profile.save()

    return Response()
