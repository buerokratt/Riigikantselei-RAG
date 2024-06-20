from typing import Any, Dict
from unittest import mock

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from api.utilities.testing import IsString
from user_profile.utilities import create_test_user_with_user_profile


class TestTextSearchChat(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.create_endpoint_url = reverse('text_search-list')
        cls.base_create_input = {
            'user_input': 'input question',
        }
        cls.base_chat_input_1 = {
            'min_year': 2020,
            'max_year': 2024,
            'document_types': ['a', 'c'],
            'user_input': 'Asking about a topic',
        }
        cls.base_chat_input_2 = {
            'min_year': 2022,
            'max_year': 2023,
            'document_types': ['c', 'b'],
            'user_input': 'Asking about a topic for the second time',
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

    def test_chat_and_used_cost_and_usage_permission(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create

        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']
        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': conversation_id})

        # Used cost before

        self.assertEqual(self.allowed_auth_user.user_profile.used_cost, 0.0)

        # Mocking

        mock_llm_response_1 = 'Answering on the topic'
        mock_llm_response_2 = 'Answering on the topic for a second time'
        mock_async_result_1_dict = {
            'status': 'STARTED',
            'result': None,
            'error_type': None,
        }
        mock_async_result_2_dict = {
            'status': 'SUCCESS',
            'result': mock_llm_response_1,
            'error_type': None,
        }
        mock_async_result_3_dict = {
            'status': 'SUCCESS',
            'result': mock_llm_response_2,
            'error_type': None,
        }

        mock_celery_task_id = 'abc'
        mock_query_result_parameters_1 = {
            'conversation': conversation_id,
            'celery_task_id': mock_celery_task_id,
            'model': 'model_name',
            'min_year': self.base_chat_input_1['min_year'],
            'max_year': self.base_chat_input_1['max_year'],
            'document_types_string': ','.join(self.base_chat_input_1['document_types']),
            'user_input': self.base_chat_input_1['user_input'],
            'response': mock_llm_response_1,
            'input_tokens': 1000,
            'output_tokens': 200,
            'total_cost': 1.0,
            'response_headers': {},
        }
        mock_query_result_parameters_2 = {
            'conversation': conversation_id,
            'celery_task_id': mock_celery_task_id,
            'model': 'model_name',
            'min_year': self.base_chat_input_2['min_year'],
            'max_year': self.base_chat_input_2['max_year'],
            'document_types_string': ','.join(self.base_chat_input_2['document_types']),
            'user_input': self.base_chat_input_2['user_input'],
            'response': mock_llm_response_2,
            'input_tokens': 1800,
            'output_tokens': 250,
            'total_cost': 1.5,
            'response_headers': {},
        }

        mock_statuses = ['STARTED', 'SUCCESS', 'SUCCESS']
        mock_results = [None, mock_query_result_parameters_1, mock_query_result_parameters_2]

        class MockAsyncInfo:
            # pylint: disable=unused-argument
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.task_id = mock_celery_task_id

        class MockAsyncResult:
            # pylint: disable=unused-argument
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                self.status = mock_statuses.pop(0)
                self.result = mock_results.pop(0)

        with mock.patch('core.serializers.async_call_celery_task_chain', new=MockAsyncInfo):
            with mock.patch('core.views.AsyncResult', new=MockAsyncResult):
                # Chat 1

                response = self.client.post(chat_endpoint_url, data=self.base_chat_input_1)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

                self.assertIn('celery_task_id', response.data)
                mock_celery_task_id = response.data['celery_task_id']

                expected_data = {'celery_task_id': mock_celery_task_id}
                self.assertEqual(response.data, expected_data)

                # AsyncResult 1

                async_result_endpoint_url = reverse(
                    'async_result', kwargs={'celery_task_id': mock_celery_task_id}
                )

                response = self.client.get(async_result_endpoint_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

                self.assertEqual(response.data, mock_async_result_1_dict)

                response = self.client.get(async_result_endpoint_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

                self.assertEqual(response.data, mock_async_result_2_dict)

                # Chat 2

                response = self.client.post(chat_endpoint_url, data=self.base_chat_input_2)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

                self.assertIn('celery_task_id', response.data)
                mock_celery_task_id = response.data['celery_task_id']

                expected_data = {'celery_task_id': mock_celery_task_id}
                self.assertEqual(response.data, expected_data)

                # AsyncResult 2

                async_result_endpoint_url = reverse(
                    'async_result', kwargs={'celery_task_id': mock_celery_task_id}
                )

                response = self.client.get(async_result_endpoint_url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

                self.assertEqual(response.data, mock_async_result_3_dict)

        # Retrieve

        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': conversation_id})

        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        expected_retrieve_data: Dict[str, Any] = {
            'id': conversation_id,
            'title': self.base_create_input['user_input'],
            'created_at': IsString(),
            'query_results': [
                {
                    'min_year': self.base_chat_input_1['min_year'],
                    'max_year': self.base_chat_input_1['max_year'],
                    'user_input': self.base_chat_input_1['user_input'],
                    'response': mock_llm_response_1,
                    'total_cost': mock_query_result_parameters_1['total_cost'],
                    'created_at': IsString(),
                    'document_types': self.base_chat_input_1['document_types'],
                },
                {
                    'min_year': self.base_chat_input_2['min_year'],
                    'max_year': self.base_chat_input_2['max_year'],
                    'user_input': self.base_chat_input_2['user_input'],
                    'response': mock_llm_response_2,
                    'total_cost': mock_query_result_parameters_2['total_cost'],
                    'created_at': IsString(),
                    'document_types': self.base_chat_input_2['document_types'],
                },
            ],
        }

        self.assertEqual(response.data, expected_retrieve_data)

        # Used cost after

        expected_used_cost = (
            mock_query_result_parameters_1['total_cost']
            + mock_query_result_parameters_2['total_cost']
        )
        self.assertEqual(self.allowed_auth_user.user_profile.used_cost, expected_used_cost)

        # Usage-based permissions

        user_profile = self.allowed_auth_user.user_profile
        user_profile.custom_usage_limit_euros = expected_used_cost - 0.5
        user_profile.save()

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input_1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_chat_fails_because_not_authed(self) -> None:
        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input_1)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chat_fails_because_not_allowed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=self.base_create_input)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input_1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_chat_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 999})

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input_1)
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

        response = self.client.post(chat_endpoint_url, data=self.base_chat_input_1)
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
