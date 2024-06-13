from base64 import b64encode

from rest_framework import HTTP_HEADER_ENCODING, status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_profile.utilities import create_test_user_with_user_profile


class TestGetToken(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.manager_auth_user = create_test_user_with_user_profile(
            self, 'manager', 'manager@email.com', 'password', is_manager=True
        )
        self.token_endpoint_url = reverse('get_token')

    def test_get_existing_token(self) -> None:
        manager_token, created = Token.objects.get_or_create(user=self.manager_auth_user)
        self.assertTrue(created)

        encoded_credentials = b64encode('manager:password'.encode(HTTP_HEADER_ENCODING)).decode(
            HTTP_HEADER_ENCODING
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Basic {encoded_credentials}')

        response = self.client.get(self.token_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['token'], manager_token.key)

    def test_get_new_token(self) -> None:
        encoded_credentials = b64encode('manager:password'.encode(HTTP_HEADER_ENCODING)).decode(
            HTTP_HEADER_ENCODING
        )
        self.client.credentials(HTTP_AUTHORIZATION=f'Basic {encoded_credentials}')

        response = self.client.get(self.token_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        manager_token, created = Token.objects.get_or_create(user=self.manager_auth_user)
        self.assertFalse(created)

        self.assertEqual(response.data['token'], manager_token.key)
