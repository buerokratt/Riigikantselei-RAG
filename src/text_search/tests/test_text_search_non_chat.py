from datetime import datetime

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from api.utilities.core_settings import get_core_setting
from api.utilities.testing import IsType
from core.choices import TaskStatus
from core.models import Dataset
from text_search.models import TextSearchConversation, TextSearchQueryResult, TextTask
from text_search.tests.test_settings import (
    BASE_CREATE_INPUT,
    BASE_SET_TITLE_INPUT,
    EQUAL_DATES_CREATE_INPUT,
    INVALID_DATASET_NAME_CREATE_INPUT,
    INVALID_MAX_YEAR_CREATE_INPUT,
    INVALID_MIN_YEAR_CREATE_INPUT,
    INVALID_YEAR_DIFFERENCE_CREATE_INPUT,
    NEITHER_DATE_CREATE_INPUT,
)
from user_profile.utilities import create_test_user_with_user_profile


# pylint: disable=too-many-public-methods
class TestTextSearchNonChat(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.create_endpoint_url = reverse('v1:text_search-list')
        cls.list_endpoint_url = reverse('v1:text_search-list')

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

        Dataset(name='a', type='', index='a_*', description='').save()
        Dataset(name='b', type='', index='b_*', description='').save()
        Dataset(name='c', type='', index='c_*', description='').save()

    # success

    def test_create_retrieve_list(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # List (empty)
        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data, [])

        # Create
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)

        conversation_id = response.data['id']
        shared_expected_data = {
            'id': conversation_id,
            'title': BASE_CREATE_INPUT['user_input'],
            'created_at': IsType(str),
            'min_year': BASE_CREATE_INPUT['min_year'],
            'max_year': BASE_CREATE_INPUT['max_year'],
            'dataset_names': BASE_CREATE_INPUT['dataset_names'],
        }
        response_only_expected_data = {'query_results': []}  # type: ignore
        model_only_expected_data = {
            'created_at': IsType(datetime),
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
        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': conversation_id})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data, response_expected_data)

        # List
        response = self.client.get(self.list_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data, [response_expected_data])

    def test_create_uses_default_datasets(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        default_dataset_input = dict(BASE_CREATE_INPUT)
        del default_dataset_input['dataset_names']

        # Create
        response = self.client.post(self.create_endpoint_url, data=default_dataset_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Retrieve
        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': conversation_id})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['dataset_names'], ['a', 'b', 'c'])

    def test_set_title(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set
        set_title_endpoint_url = reverse('v1:text_search-set-title', kwargs={'pk': conversation_id})

        response = self.client.post(set_title_endpoint_url, data=BASE_SET_TITLE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        conversation = TextSearchConversation.objects.get(id=conversation_id)
        self.assertEqual(conversation.title, BASE_SET_TITLE_INPUT['title'])

        # Retrieve

        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': conversation_id})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(response.data['title'], BASE_SET_TITLE_INPUT['title'])

    def test_messages_only_uses_successful_results(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        conversation_id = response.data['id']

        failed_result = TextSearchQueryResult.objects.create(
            conversation_id=conversation_id, user_input='Why are you like this?'
        )
        TextTask.objects.create(
            result=failed_result, status=TaskStatus.FAILURE, error='Something went wrong!'
        )

        success_input = 'What is your purpose?'
        response_message = 'This is the OpenAPI response etc etc.'
        success_instance = TextSearchQueryResult.objects.create(
            conversation_id=conversation_id, user_input=success_input, response=response_message
        )
        TextTask.objects.create(result=success_instance, status=TaskStatus.SUCCESS)

        # Check the context that the conversation instance creates.
        conversation = TextSearchConversation.objects.get(id=conversation_id)
        messages = conversation.messages

        # System message, question message for success, response message.
        expected_messages = [
            {
                'role': 'system',
                'content': get_core_setting('OPENAI_SYSTEM_MESSAGE'),
            },
            {
                'role': 'user',
                'content': success_input,
            },
            {
                'role': 'assistant',
                'content': response_message,
            },
        ]
        self.assertEqual(messages, expected_messages)

    # create fails

    def test_create_fails_because_not_authed(self) -> None:
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_fails_because_not_accepted(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_fails_because_bad_dataset_names(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(
            self.create_endpoint_url,
            data=INVALID_DATASET_NAME_CREATE_INPUT,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_year_validation(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=INVALID_MIN_YEAR_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(self.create_endpoint_url, data=INVALID_MAX_YEAR_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(
            self.create_endpoint_url, data=INVALID_YEAR_DIFFERENCE_CREATE_INPUT
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        response = self.client.post(self.create_endpoint_url, data=EQUAL_DATES_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(self.create_endpoint_url, data=NEITHER_DATE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # retrieve fails

    def test_retrieve_fails_because_not_authed(self) -> None:
        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': 1})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_fails_because_not_accepted(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': 1})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': 999})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_fails_because_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Retrieve

        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': conversation_id})

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
        set_title_endpoint_url = reverse('v1:text_search-set-title', kwargs={'pk': 1})

        response = self.client.post(set_title_endpoint_url, data=BASE_SET_TITLE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_set_title_fails_because_not_accepted(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        set_title_endpoint_url = reverse('v1:text_search-set-title', kwargs={'pk': 1})

        response = self.client.post(set_title_endpoint_url, data=BASE_SET_TITLE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_set_title_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        set_title_endpoint_url = reverse('v1:text_search-set-title', kwargs={'pk': 999})

        response = self.client.post(set_title_endpoint_url, data=BASE_SET_TITLE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_set_title_fails_because_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set title
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        set_title_endpoint_url = reverse('v1:text_search-set-title', kwargs={'pk': conversation_id})
        response = self.client.post(set_title_endpoint_url, data=BASE_SET_TITLE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_set_title_fails_because_bad_title(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set title
        set_title_endpoint_url = reverse('v1:text_search-set-title', kwargs={'pk': conversation_id})
        data = {'title': 'asdf\0'}
        response = self.client.post(set_title_endpoint_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
