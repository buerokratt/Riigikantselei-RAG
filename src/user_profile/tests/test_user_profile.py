from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from api.utilities.testing import create_test_user
from user_profile.models import UserProfile


class TestUserProfileCreate(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.admin_auth_user = create_test_user('admin', 'admin@email.com', 'pw', is_superuser=True)
        cls.create_endpoint_url = reverse('user_profile-list')

    def test_create(self) -> None:
        base_input = {
            'username': 'tester',
            'email': 'tester@email.com',
            'first_name': 'tester',
            'last_name': 'tester',
        }
        input_with_password = base_input | {'password': 'pw'}

        response = self.client.post(self.create_endpoint_url, data=input_with_password)
        auth_user_id = response.data['id']

        model_data = {
            'is_admin': False,
            'reviewed': False,
            'accepted': False,
            'allowed_to_spend_resources': False,
            'usage_limit_is_default': True,
            'custom_usage_limit_euros': None,
        }
        expected_data = base_input | model_data | {'id': auth_user_id}

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data, expected_data)

        user_profile = UserProfile.objects.get(auth_user=auth_user_id)
        for attribute, value in model_data.items():
            self.assertEqual(getattr(user_profile, attribute), value)

        # TODO here: tests
        # Create fails because authed
        # Create fails because not valid input


# TODO here: tests
# Retireve succeeds
# Retrieve fails because not authed
# Retrieve fails because not admin asking other
# Retrieve fails because not exists
# List succeeds
# List fails because not authed
# List fails because not admin
