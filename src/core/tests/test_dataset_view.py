from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from core.models import Dataset
from user_profile.utilities import create_test_user_with_user_profile


class TestDatasetView(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.dataset_endpoint_url = reverse('v1:dataset-list')

    def setUp(self) -> None:  # pylint: disable=invalid-name
        Dataset(name='a', type='', index='a_*', description='').save()
        Dataset(name='b', type='', index='b_*', description='').save()

    def test_dataset_view(self) -> None:
        accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )

        token, _ = Token.objects.get_or_create(user=accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.dataset_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_response = [
            {
                'id': 1,
                'name': 'a',
                'type': '',
                'index': 'a_*',
                'description': '',
            },
            {
                'id': 2,
                'name': 'b',
                'type': '',
                'index': 'b_*',
                'description': '',
            },
        ]

        self.assertEqual(response.data, expected_response)

    def test_dataset_view_fails_because_not_accepted(self) -> None:
        non_accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )

        non_accepted_auth_user_profile = non_accepted_auth_user.user_profile
        non_accepted_auth_user_profile.is_accepted = False
        non_accepted_auth_user_profile.save()

        token, _ = Token.objects.get_or_create(user=non_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.dataset_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
