from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from api.utilities.testing import create_test_user
from user_profile.models import UserProfile


class TestUserProfileCreate(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.admin_auth_user = create_test_user(
            'admin', 'admin@email.com', 'password', is_superuser=True
        )
        cls.non_admin_auth_user = create_test_user(
            'tester1', 'tester1@email.com', 'password', is_superuser=False
        )
        cls.create_endpoint_url = reverse('v1:user_profile-list')
        cls.base_input = {
            'username': 'tester',
            'email': 'tester@email.com',
            'first_name': 'tester',
            'last_name': 'tester',
        }
        cls.input_with_password = cls.base_input | {'password': 'password'}

    def test_create(self) -> None:
        response = self.client.post(self.create_endpoint_url, data=self.input_with_password)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)

        auth_user_id = response.data['id']
        model_data = {
            'is_manager': False,
            'is_reviewed': False,
            'is_accepted': False,
            'is_allowed_to_spend_resources': False,
            'custom_usage_limit_euros': None,
            'usage_limit': 50.0,
            'used_cost': 0.0,
        }
        added_auth_user_data = {
            'id': auth_user_id,
            'is_superuser': False,
        }
        expected_data = self.base_input | model_data | added_auth_user_data

        self.assertEqual(response.data, expected_data)

        auth_user = User.objects.get(id=auth_user_id)
        user_profile = UserProfile.objects.get(auth_user=auth_user_id)

        self.assertEqual(auth_user, user_profile.auth_user)
        self.assertEqual(user_profile, auth_user.user_profile)

        for attribute, value in model_data.items():
            self.assertEqual(getattr(user_profile, attribute), value)

    def test_create_fails_because_authed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_admin_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=self.input_with_password)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_fails_because_invalid_input(self) -> None:
        inputs = [
            # missing field
            {
                'username': 'tester',
                'email': 'tester@email.com',
                'last_name': 'tester',
                'password': 'password',
            },
            # duplicate username
            {
                'username': 'admin',
                'email': 'tester@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'password': 'password',
            },
            # duplicate email
            {
                'username': 'tester',
                'email': 'admin@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'password': 'password',
            },
            # bad username
            {
                'username': 'tester\0',
                'email': 'tester@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'password': 'password',
            },
            # bad password
            {
                'username': 'tester',
                'email': 'tester@email.com',
                'first_name': 'tester',
                'last_name': 'tester',
                'password': 'password' * 100,
            },
            # bad email
            {
                'username': 'tester',
                'email': 'tester@email',
                'first_name': 'tester',
                'last_name': 'tester',
                'password': 'password',
            },
        ]

        for _input in inputs:
            response = self.client.post(self.create_endpoint_url, data=_input)
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
