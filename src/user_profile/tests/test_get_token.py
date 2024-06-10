from base64 import b64encode

from rest_framework import HTTP_HEADER_ENCODING, status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from user_profile.utilities import create_test_user_with_user_profile


class TestGetToken(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.admin_auth_user = create_test_user_with_user_profile(
            self, 'admin', 'admin@email.com', 'password', is_superuser=True
        )
        self.token_endpoint_url = reverse('get_token')

    def test_get_existing_token(self) -> None:
        admin_token, created = Token.objects.get_or_create(user=self.admin_auth_user)
        self.assertTrue(created)

        encoded_credentials = b64encode('admin:password'.encode(HTTP_HEADER_ENCODING)).decode(
            HTTP_HEADER_ENCODING
        )
        self.client.credentials(HTTP_AUTHORIZATON=f'Basic {encoded_credentials}')
        # TODO here: fix auth usage in tests and remove
        self.client.force_authenticate(user=self.admin_auth_user)

        response = self.client.get(self.token_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['token'], admin_token.key)

    def test_get_new_token(self) -> None:
        encoded_credentials = b64encode('admin:password'.encode(HTTP_HEADER_ENCODING)).decode(
            HTTP_HEADER_ENCODING
        )
        self.client.credentials(HTTP_AUTHORIZATON=f'Basic {encoded_credentials}')
        # TODO here: fix auth usage in tests and remove
        self.client.force_authenticate(user=self.admin_auth_user)

        response = self.client.get(self.token_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        admin_token, created = Token.objects.get_or_create(user=self.admin_auth_user)
        self.assertFalse(created)

        self.assertEqual(response.data['token'], admin_token.key)
