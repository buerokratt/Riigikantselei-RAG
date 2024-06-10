from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_profile.utilities import create_test_user_with_user_profile


class TestUserProfileRetrieveAndList(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.list_endpoint_url = reverse('user_profile-list')

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.admin_auth_user = create_test_user_with_user_profile(
            self, 'admin', 'admin@email.com', 'password', is_superuser=True
        )
        self.non_admin_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_superuser=False
        )
        self.retrieve_endpoint_url_admin = reverse(
            'user_profile-detail', kwargs={'pk': self.admin_auth_user.id}
        )
        self.retrieve_endpoint_url_non_admin = reverse(
            'user_profile-detail', kwargs={'pk': self.non_admin_auth_user.id}
        )

    def test_retrieve(self) -> None:
        # Admin should be able to access other user, non-admin should be able to access self
        for user in [self.admin_auth_user, self.non_admin_auth_user]:
            token, _ = Token.objects.get_or_create(user=user)
            self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

            response = self.client.get(self.retrieve_endpoint_url_non_admin)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            expected_data = {
                'username': 'tester',
                'email': 'tester@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'id': self.non_admin_auth_user.id,
                'is_admin': False,
                'is_reviewed': True,
                'is_accepted': True,
                'is_allowed_to_spend_resources': True,
                'usage_limit_is_default': True,
                'custom_usage_limit_euros': None,
            }
            self.assertEqual(response.data, expected_data)

    def test_retrieve_fails_because_not_authed(self) -> None:
        response = self.client.get(self.retrieve_endpoint_url_admin)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_fails_because_not_accepted(self) -> None:
        non_accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester2', 'tester2@email.com', 'password', is_superuser=False
        )
        non_accepted_user_profile = non_accepted_auth_user.user_profile
        non_accepted_user_profile.is_accepted = False
        non_accepted_user_profile.save()

        token, _ = Token.objects.get_or_create(user=non_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.retrieve_endpoint_url_admin)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_fails_because_non_admin_user_asking_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.retrieve_endpoint_url_admin)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        retrieve_endpoint_url = reverse('user_profile-detail', kwargs={'pk': 999})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_data = [
            {
                'username': 'admin',
                'email': 'admin@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'id': self.admin_auth_user.id,
                'is_admin': True,
                'is_reviewed': True,
                'is_accepted': True,
                'is_allowed_to_spend_resources': True,
                'usage_limit_is_default': True,
                'custom_usage_limit_euros': None,
            },
            {
                'username': 'tester',
                'email': 'tester@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'id': self.non_admin_auth_user.id,
                'is_admin': False,
                'is_reviewed': True,
                'is_accepted': True,
                'is_allowed_to_spend_resources': True,
                'usage_limit_is_default': True,
                'custom_usage_limit_euros': None,
            },
        ]
        self.assertEqual(response.data, expected_data)

    def test_list_fails_because_not_authed(self) -> None:
        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_fails_because_not_admin(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
