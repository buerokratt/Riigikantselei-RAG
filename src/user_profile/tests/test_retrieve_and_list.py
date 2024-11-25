from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_profile.utilities import create_test_user_with_user_profile


class TestUserProfileRetrieveAndList(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.list_endpoint_url = reverse('v1:user_profile-list')

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.manager_auth_user = create_test_user_with_user_profile(
            self, 'manager', 'manager@email.com', 'password', is_manager=True
        )
        self.non_manager_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )
        self.superuser = create_test_user_with_user_profile(
            self, 'superman', 'superman@email.com', 'password', is_admin=True
        )
        self.retrieve_endpoint_url_manager = reverse(
            'v1:user_profile-detail', kwargs={'pk': self.manager_auth_user.id}
        )
        self.retrieve_endpoint_url_non_manager = reverse(
            'v1:user_profile-detail', kwargs={'pk': self.non_manager_auth_user.id}
        )

        self.deleted_auth_user = create_test_user_with_user_profile(
            self, 'tester2', 'tester2@email.com', 'password', is_manager=False
        )
        deleted_user_profile = self.deleted_auth_user.user_profile
        deleted_user_profile.is_deleted = True
        deleted_user_profile.save()

    def test_retrieve(self) -> None:
        # Manager should be able to access other user, non-manager should be able to access self
        for user in [self.manager_auth_user, self.non_manager_auth_user]:
            token, _ = Token.objects.get_or_create(user=user)
            self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

            response = self.client.get(self.retrieve_endpoint_url_non_manager)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            expected_data = {
                'username': 'tester',
                'email': 'tester@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'is_superuser': False,
                'id': self.non_manager_auth_user.id,
                'is_manager': False,
                'is_reviewed': True,
                'is_accepted': True,
                'is_allowed_to_spend_resources': True,
                'custom_usage_limit_euros': None,
                'usage_limit': 50.0,
                'used_cost': 0.0,
            }
            self.assertEqual(response.data, expected_data)

    def test_retrieve_fails_because_not_authed(self) -> None:
        response = self.client.get(self.retrieve_endpoint_url_manager)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_without_user_being_accepted_is_allowed(self) -> None:
        non_accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester3', 'tester3@email.com', 'password', is_manager=False
        )
        non_accepted_user_profile = non_accepted_auth_user.user_profile
        non_accepted_user_profile.is_accepted = False
        non_accepted_user_profile.save()

        token, _ = Token.objects.get_or_create(user=non_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        url = reverse('v1:user_profile-detail', kwargs={'pk': non_accepted_auth_user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_fails_because_non_manager_user_asking_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.retrieve_endpoint_url_manager)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        retrieve_endpoint_url = reverse('v1:user_profile-detail', kwargs={'pk': 999})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_data = [
            {
                'username': 'manager',
                'email': 'manager@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'is_superuser': False,
                'id': self.manager_auth_user.id,
                'is_manager': True,
                'is_reviewed': True,
                'is_accepted': True,
                'is_allowed_to_spend_resources': True,
                'custom_usage_limit_euros': None,
                'usage_limit': 50.0,
                'used_cost': 0.0,
            },
            {
                'username': 'tester',
                'email': 'tester@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'is_superuser': False,
                'id': self.non_manager_auth_user.id,
                'is_manager': False,
                'is_reviewed': True,
                'is_accepted': True,
                'is_allowed_to_spend_resources': True,
                'custom_usage_limit_euros': None,
                'usage_limit': 50.0,
                'used_cost': 0.0,
            },
            {
                'username': 'superman',
                'email': 'superman@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'is_superuser': True,
                'id': self.superuser.id,
                'is_manager': False,
                'is_reviewed': True,
                'is_accepted': True,
                'is_allowed_to_spend_resources': True,
                'custom_usage_limit_euros': None,
                'usage_limit': 50.0,
                'used_cost': 0.0,
            },
        ]
        self.assertEqual(response.data, expected_data)

    def test_list_fails_because_not_authed(self) -> None:
        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_fails_because_not_manager(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_superuser_status_is_visible(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.superuser)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        users = response.data
        # Check that it matches three users.
        self.assertEqual(len(users), 3)
        superusers = [user for user in users if user['is_superuser'] is True]
        self.assertEqual(len(superusers), 1)
