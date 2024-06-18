from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_profile.utilities import create_test_user_with_user_profile


class TestGetToken(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.username = 'manager'
        self.password = 'password'
        self.manager_auth_user = create_test_user_with_user_profile(
            self, self.username, 'manager@email.com', self.password, is_manager=True
        )
        self.token_endpoint_url = reverse('get_token')

    def test_get_existing_token(self) -> None:
        manager_token, created = Token.objects.get_or_create(user=self.manager_auth_user)
        self.assertTrue(created)

        response = self.client.post(
            self.token_endpoint_url,
            data={"username": self.username, "password": self.password}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['token'], manager_token.key)

    def test_get_new_token(self) -> None:
        response = self.client.post(
            self.token_endpoint_url,
            data={"username": self.username, "password": self.password}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        manager_token, created = Token.objects.get_or_create(user=self.manager_auth_user)
        self.assertFalse(created)

        self.assertEqual(response.data['token'], manager_token.key)
