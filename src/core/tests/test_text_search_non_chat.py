from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from api.utilities.core_settings import get_core_setting
from api.utilities.testing import IsDatetime, IsString
from core.models import TextSearchConversation
from user_profile.utilities import create_test_user_with_user_profile


class TestTextSearchNonChat(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.create_endpoint_url = reverse('text_search-list')
        cls.list_endpoint_url = reverse('text_search-list')
        cls.base_create_input = {
            'user_input': 'input question',
            'min_year': 2000,
            'max_year': 2024,
            'document_types': ['a'],
        }
        cls.base_set_title_input = {
            'title': 'Asking about a topic',
        }

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )
        self.accepted_auth_user_2 = create_test_user_with_user_profile(
            self, 'tester2', 'tester2@email.com', 'password', is_manager=False
        )
        self.not_accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester3', 'tester3@email.com', 'password', is_manager=False
        )
        not_accepted_user_profile = self.not_accepted_auth_user.user_profile
        not_accepted_user_profile.is_accepted = False
        not_accepted_user_profile.save()

    # success

    def test_create_retrieve_list(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # List (empty)
        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data, [])

        # Create
        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)

        conversation_id = response.data['id']
        shared_expected_data = {
            'id': conversation_id,
            'title': self.base_create_input['user_input'],
            'created_at': IsString(),
            'min_year': self.base_create_input['min_year'],
            'max_year': self.base_create_input['max_year'],
            'document_types': self.base_create_input['document_types'],
        }
        response_only_expected_data = {'query_results': []}  # type: ignore
        model_only_expected_data = {
            'created_at': IsDatetime(),
            'auth_user': self.accepted_auth_user,
            'system_input': get_core_setting('OPENAI_SYSTEM_MESSAGE'),
        }

        response_expected_data = shared_expected_data | response_only_expected_data
        model_expected_data = shared_expected_data | model_only_expected_data

        self.assertEqual(response.data, response_expected_data)

        conversation = TextSearchConversation.objects.get(id=conversation_id)

        for attribute, value in model_expected_data.items():
            self.assertEqual(getattr(conversation, attribute), value)

        # Retrieve
        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': conversation_id})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data, response_expected_data)

        # List
        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data, [response_expected_data])

    def test_set_title(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create

        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set
        set_title_endpoint_url = reverse('text_search-set-title', kwargs={'pk': conversation_id})

        response = self.client.post(set_title_endpoint_url, data=self.base_set_title_input)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        conversation = TextSearchConversation.objects.get(id=conversation_id)
        self.assertEqual(conversation.title, self.base_set_title_input['title'])

        # Retrieve

        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': conversation_id})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['title'], self.base_set_title_input['title'])

    # create fails

    def test_create_fails_because_not_authed(self) -> None:
        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_fails_because_not_accepted(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # retrieve fails

    def test_retrieve_fails_because_not_authed(self) -> None:
        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': 1})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_fails_because_not_accepted(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': 1})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': 999})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_fails_because_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Retrieve

        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': conversation_id})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # list fails

    def test_list_fails_because_not_authed(self) -> None:
        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_fails_because_not_accepted(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # set title fails

    def test_set_title_fails_because_not_authed(self) -> None:
        set_title_endpoint_url = reverse('text_search-set-title', kwargs={'pk': 1})

        response = self.client.post(set_title_endpoint_url, data=self.base_set_title_input)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_set_title_fails_because_not_accepted(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        set_title_endpoint_url = reverse('text_search-set-title', kwargs={'pk': 1})

        response = self.client.post(set_title_endpoint_url, data=self.base_set_title_input)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_set_title_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        set_title_endpoint_url = reverse('text_search-set-title', kwargs={'pk': 999})

        response = self.client.post(set_title_endpoint_url, data=self.base_set_title_input)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_set_title_fails_because_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set title
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        set_title_endpoint_url = reverse('text_search-set-title', kwargs={'pk': conversation_id})
        response = self.client.post(set_title_endpoint_url, data=self.base_set_title_input)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_set_title_fails_because_bad_title(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set title
        set_title_endpoint_url = reverse('text_search-set-title', kwargs={'pk': conversation_id})
        data = {'title': 'asdf\0'}
        response = self.client.post(set_title_endpoint_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
