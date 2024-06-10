from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_profile.utilities import create_test_user_with_user_profile


# pylint: disable=too-many-instance-attributes
class TestUserProfileEdit(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.admin_auth_user = create_test_user_with_user_profile(
            self, 'admin', 'admin@email.com', 'password', is_superuser=True
        )
        self.non_admin_reviewed_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_superuser=False
        )
        self.non_admin_unreviewed_auth_user = create_test_user_with_user_profile(
            self, 'tester2', 'tester2@email.com', 'password', is_superuser=False
        )

        non_admin_unreviewed_user_profile = self.non_admin_unreviewed_auth_user.user_profile
        non_admin_unreviewed_user_profile.is_reviewed = False
        non_admin_unreviewed_user_profile.is_accepted = False
        non_admin_unreviewed_user_profile.is_allowed_to_spend_resources = False
        non_admin_unreviewed_user_profile.save()

        self.accept_reviewed_endpoint_url = reverse(
            'user_profile-accept', kwargs={'pk': self.non_admin_reviewed_auth_user.id}
        )
        self.accept_unreviewed_endpoint_url = reverse(
            'user_profile-accept', kwargs={'pk': self.non_admin_unreviewed_auth_user.id}
        )
        self.decline_reviewed_endpoint_url = reverse(
            'user_profile-decline', kwargs={'pk': self.non_admin_reviewed_auth_user.id}
        )
        self.decline_unreviewed_endpoint_url = reverse(
            'user_profile-decline', kwargs={'pk': self.non_admin_unreviewed_auth_user.id}
        )

        self.ban_endpoint_url = reverse(
            'user_profile-ban', kwargs={'pk': self.non_admin_reviewed_auth_user.id}
        )
        self.set_limit_endpoint_url = reverse(
            'user_profile-set-limit', kwargs={'pk': self.non_admin_reviewed_auth_user.id}
        )

        self.input_data = {'limit': 20.5}

    # Accept

    def test_accept(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.accept_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_accept_fails_because_not_authed(self) -> None:
        response = self.client.post(self.accept_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_accept_fails_because_not_admin(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_admin_reviewed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.accept_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_accept_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        accept_endpoint_url = reverse('user_profile-accept', kwargs={'pk': 999})

        response = self.client.post(accept_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_accept_fails_because_already_reviewed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.accept_reviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Decline

    def test_decline(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.decline_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_decline_fails_because_not_authed(self) -> None:
        response = self.client.post(self.decline_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_decline_fails_because_not_admin(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_admin_reviewed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.decline_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_decline_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        decline_endpoint_url = reverse('user_profile-decline', kwargs={'pk': 999})

        response = self.client.post(decline_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_decline_fails_because_already_reviewed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.decline_reviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Ban

    def test_ban(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.ban_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ban_fails_because_not_authed(self) -> None:
        response = self.client.post(self.ban_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ban_fails_because_not_admin(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_admin_reviewed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.ban_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ban_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        ban_endpoint_url = reverse('user_profile-ban', kwargs={'pk': 999})

        response = self.client.post(ban_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # set limit

    def test_set_limit(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.set_limit_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_set_limit_fails_because_not_authed(self) -> None:
        response = self.client.post(self.set_limit_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_set_limit_fails_because_not_admin(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_admin_reviewed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.set_limit_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_set_limit_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        set_limit_endpoint_url = reverse('user_profile-set-limit', kwargs={'pk': 999})

        response = self.client.post(set_limit_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_set_limit_fails_because_bad_limit(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        input_data = {'limit': 10_000.0}

        response = self.client.post(self.set_limit_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
