from typing import List
from unittest import mock

from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITransactionTestCase

from api.utilities.core_settings import get_core_setting
from api.utilities.elastic import ElasticCore
from core.choices import TaskStatus
from core.models import Task, TextSearchConversation, TextSearchQueryResult
from core.tests.test_settings import (
    BASE_CREATE_INPUT,
    CONTINUE_CONVERSATION_INPUT,
    EQUAL_DATES_INPUT,
    FIRST_CONVERSATION_START_INPUT,
    INVALID_MAX_YEAR_INPUT,
    INVALID_MIN_YEAR_INPUT,
    INVALID_YEAR_DIFFERENCE_INPUT,
    FirstChatInConversationMockResults,
    SecondChatInConversationMockResults,
)
from user_profile.utilities import create_test_user_with_user_profile

# pylint: disable=invalid-name


# We use APITransactionTestCase here because we're running a Celery task chain synchronously.
class TestTextSearchChat(APITransactionTestCase):
    def _create_test_indices(self, indices: List[str]) -> None:
        core = ElasticCore()
        for index in indices:
            core.elasticsearch.indices.create(index=index, ignore=[400, 404])

    def _clear_indices(self, indices: List[str]) -> None:
        core = ElasticCore()
        for index in indices:
            core.elasticsearch.indices.delete(index, ignore=[400, 404])

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.create_endpoint_url = reverse('text_search-list')

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

        self.indices = [
            'a_1',
            'a_2',
            'b',
            'c_1',
            'c_2',
        ]
        self._create_test_indices(indices=self.indices)

    def tearDown(self) -> None:
        self._clear_indices(self.indices)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_chat_and_used_cost_and_usage_permission(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create conversation to start chatting.
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']
        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': conversation_id})

        # Assert used cost is solidly at 0.
        self.assertEqual(self.allowed_auth_user.user_profile.used_cost, 0.0)

        first_response = FirstChatInConversationMockResults()
        second_response = SecondChatInConversationMockResults()
        with mock.patch('core.tasks.ChatGPT.chat', return_value=first_response):
            # Start conversing with OpenAI
            response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
            results = response.data['query_results']
            first_celery_status = results[-1]['celery_task']['status']
            self.assertEqual(len(results), 1)
            self.assertEqual(first_celery_status, TaskStatus.SUCCESS)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        with mock.patch('core.tasks.ChatGPT.chat', return_value=second_response):
            # Continue the conversation.
            response = self.client.post(chat_endpoint_url, data=CONTINUE_CONVERSATION_INPUT)
            results = response.data['query_results']
            second_celery_status = results[-1]['celery_task']['status']
            self.assertEqual(second_celery_status, TaskStatus.SUCCESS)
            self.assertEqual(len(results), 2)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Retrieve the conversation instance.
        retrieve_endpoint_url = reverse('text_search-detail', kwargs={'pk': conversation_id})
        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Used cost after communicating with the OpenAI API.
        expected_used_cost = first_response.total_cost + second_response.total_cost
        self.assertEqual(self.allowed_auth_user.user_profile.used_cost, expected_used_cost)

        # Ensure that with lower usage restrictions, an exception is thrown to the user.
        user_profile = self.allowed_auth_user.user_profile
        user_profile.custom_usage_limit_euros = expected_used_cost - 0.5
        user_profile.save()
        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_that_only_successful_results_are_passed_into_openai(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        conversation_id = response.data['id']

        failure_instance = TextSearchQueryResult.objects.create(
            conversation_id=conversation_id, user_input='Why are you like this?'
        )
        Task.objects.create(
            result=failure_instance, status=TaskStatus.FAILURE, error='Something went wrong!'
        )

        success_input = 'What is your purpose?'
        response_message = 'This is the OpenAPI response etc etc.'
        success_instance = TextSearchQueryResult.objects.create(
            conversation_id=conversation_id, user_input=success_input, response=response_message
        )
        Task.objects.create(result=success_instance, status=TaskStatus.SUCCESS)

        # Check the context that the conversation instance creates.
        conversation = TextSearchConversation.objects.get(pk=conversation_id)
        messages = conversation.messages
        # System message, question message for success, response message.
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]['content'], get_core_setting('OPENAI_SYSTEM_MESSAGE'))

        self.assertEqual(messages[1]['role'], 'user')
        self.assertEqual(messages[1]['content'], success_input)

        self.assertEqual(messages[2]['content'], response_message)
        self.assertEqual(messages[2]['role'], 'assistant')

    def test_that_the_max_years_above_current_year_are_not_allowed_as_inputs(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        conversation_response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(conversation_response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', conversation_response.data)
        conversation_id = conversation_response.data['id']
        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': conversation_id})

        # Check validation for max_year
        response = self.client.post(chat_endpoint_url, data=INVALID_MAX_YEAR_INPUT)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check validation for min_year
        response = self.client.post(chat_endpoint_url, data=INVALID_MIN_YEAR_INPUT)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check validation for min_year being bigger than max_year
        response = self.client.post(chat_endpoint_url, data=INVALID_YEAR_DIFFERENCE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        with mock.patch(
            'core.tasks.ChatGPT.chat', return_value=FirstChatInConversationMockResults()
        ):
            with mock.patch(
                'core.tasks.Vectorizer.vectorize',
                return_value={'vectors': [[[0.0352351, 0.3141515, 0.12541241]]]},
            ):
                # Just check equal values being respected.
                response = self.client.post(chat_endpoint_url, data=EQUAL_DATES_INPUT)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_chat_fails_because_not_authed(self) -> None:
        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chat_fails_because_not_allowed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_chat_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': 999})

        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chat_fails_because_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set title

        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        chat_endpoint_url = reverse('text_search-chat', kwargs={'pk': conversation_id})

        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chat_fails_because_bad_document_types(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
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
