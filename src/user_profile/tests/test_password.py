from datetime import timedelta

from django.contrib.auth.models import User
from django.core import mail
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase, override_settings

from user_profile.models import PasswordResetToken
from user_profile.utilities import create_test_user_with_user_profile


# pylint: disable=too-many-instance-attributes
class TestUserProfilePassword(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.non_manager_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )

        self.change_password_endpoint_url = reverse('v1:user_profile-change-password')
        self.request_password_reset_endpoint_url = reverse('v1:user_profile-request-password-reset')
        self.confirm_password_reset_endpoint_url = reverse('v1:user_profile-confirm-password-reset')

        self.password_input_data = {'password': 'password2'}
        self.email_input_data = {'email': 'tester@email.com'}

    # Change

    def test_change_password(self) -> None:
        old_hash = self.non_manager_auth_user.password

        token, _ = Token.objects.get_or_create(user=self.non_manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(
            self.change_password_endpoint_url, data=self.password_input_data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        updated_auth_user = User.objects.get(id=self.non_manager_auth_user.id)
        self.assertNotEqual(old_hash, updated_auth_user.password)

    def test_change_password_fails_because_not_authed(self) -> None:
        response = self.client.post(self.change_password_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_change_password_fails_because_bad_password(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        input_data = {'password': 'password\0'}

        response = self.client.post(self.change_password_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Password reset

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_password_reset(self) -> None:
        self.assertEqual(
            PasswordResetToken.objects.filter(auth_user=self.non_manager_auth_user).count(), 0
        )
        self.assertEqual(len(mail.outbox), 0)

        # Request reset
        response = self.client.post(
            self.request_password_reset_endpoint_url, data=self.email_input_data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            PasswordResetToken.objects.filter(auth_user=self.non_manager_auth_user).count(), 1
        )
        self.assertEqual(len(mail.outbox), 1)

        # Parse URL
        confirm_password_reset_endpoint_url = ''
        email_lines = mail.outbox[0].body.splitlines()
        for line in email_lines:
            if line.startswith('http'):
                confirm_password_reset_endpoint_url = line
                break
        self.assertGreater(len(confirm_password_reset_endpoint_url), 0)

    def test_password_reset_fails_because_not_exists(self) -> None:
        response = self.client.post(
            self.request_password_reset_endpoint_url, data={'email': 'manager@email.com'}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        password_token_input_data = self.password_input_data | {'token': '0'}
        response = self.client.post(
            self.confirm_password_reset_endpoint_url, data=password_token_input_data
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_password_reset_fails_because_bad_input(self) -> None:
        response = self.client.post(
            self.request_password_reset_endpoint_url, data={'email': 'tester@email'}
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        test_token = 'jmdolamldkaldkala165a1d65as65d'
        PasswordResetToken.objects.create(key=test_token, auth_user=self.non_manager_auth_user)

        password_token_input_data = {'password': 'password\0', 'token': test_token}
        response = self.client.post(
            self.confirm_password_reset_endpoint_url, data=password_token_input_data
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_password_confirm_after_expire_date_throws_exception(self) -> None:
        key = 'fa,mlkömfgafa65f4af4a65f'
        token = PasswordResetToken.objects.create(key=key, auth_user=self.non_manager_auth_user)
        token.created_at = token.created_at + timedelta(weeks=10)
        token.save()

        response = self.client.post(
            self.confirm_password_reset_endpoint_url,
            data={'token': key, 'password': 'daaököFAF@41'},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
