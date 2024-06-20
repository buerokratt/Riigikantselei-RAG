from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from api.utilities.testing import IsDatetime, IsString
from user_profile.utilities import create_test_user_with_user_profile


class TestTextSearchChat(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.create_endpoint_url = reverse('text_search-list')
        cls.base_create_input = {
            'user_input': 'input question',
        }
        cls.base_chat_input = {
            'min_year': 2020,
            'max_year': 2024,
            'document_types': ['a', 'c'],
            'user_input': 'Asking about a topic',
        }

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.allowed_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )
        self.allowed_auth_user_2 = create_test_user_with_user_profile(
            self, 'tester2', 'tester2@email.com', 'password', is_manager=False
        )

        self.not_allowed_auth_user = create_test_user_with_user_profile(
            self, 'tester3', 'tester3@email.com', 'password', is_manager=False
        )
        not_allowed_user_profile = self.not_allowed_auth_user.user_profile
        not_allowed_user_profile.is_allowed_to_spend_resources = False
        not_allowed_user_profile.save()

    def test_create_retrieve_list(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create

        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Chat

        # TODO here: mock async_call_celery_task_chain() and make it return a fake async object
        #  that makes you wait the first time and returns the second

        # AsyncResult

        # Repeat

        # Retrieve

        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': conversation_id})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_data = {  # type: ignore
            'id': conversation_id,
            'title': self.base_create_input['user_input'],
            'created_at': IsString(),
            # TODO here: enter expected data
            'query_results': [
                {
                    'min_year': '',
                    'max_year': '',
                    'user_input': '',
                    'response': '',
                    'total_cost': '',
                    'created_at': IsDatetime(),
                }
            ],
        }

        self.assertEqual(response.data, expected_data)

    def test_chat_fails_because_not_authed(self) -> None:
        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chat_fails_because_not_allowed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_chat_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 999})

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chat_fails_because_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create

        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set title

        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': conversation_id})

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chat_fails_because_bad_document_types(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create

        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set title

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': conversation_id})

        data = {
            'min_year': 2020,
            'max_year': 2024,
            'document_types': ['a', 'c', 'xyz'],
            'user_input': 'Asking about a topic',
        }

        response = self.client.post(chat_endpoint_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
