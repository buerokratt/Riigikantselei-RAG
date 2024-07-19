from typing import Tuple
from unittest import mock

from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITransactionTestCase

from core.models import Dataset
from text_search.models import TextSearchConversation, TextSearchQueryResult
from text_search.tests.test_settings import (
    BASE_CREATE_INPUT,
    CHAT_CHAIN_EXPECTED_ARGUMENTS_1,
    CHAT_CHAIN_EXPECTED_ARGUMENTS_2,
    CHAT_CHAIN_EXPECTED_QUERY_RESULTS_1,
    CHAT_CHAIN_EXPECTED_QUERY_RESULTS_2,
    CHAT_INPUT_1,
    CHAT_INPUT_2,
    chat_chain_side_effect_1,
    chat_chain_side_effect_2,
)
from user_profile.utilities import create_test_user_with_user_profile


# We use APITransactionTestCase here because we're running a Celery task chain synchronously.
class TestTextSearchChat(APITransactionTestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.create_endpoint_url = reverse('v1:text_search-list')

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

        self.low_limit_auth_user = create_test_user_with_user_profile(
            self, 'tester4', 'tester4@email.com', 'password', is_manager=False
        )
        low_limit_user_profile = self.low_limit_auth_user.user_profile
        low_limit_user_profile.custom_usage_limit_euros = 0.1
        low_limit_user_profile.save()

        Dataset(name='a', type='', index='a_*', description='').save()
        Dataset(name='b', type='', index='b_*', description='').save()
        Dataset(name='c', type='', index='c_*', description='').save()

    def _create_successful_conversation(self) -> Tuple[str, str]:
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        conversation_id = response.data['id']
        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': conversation_id})

        return conversation_id, chat_endpoint_url

    # Chat success

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_chat(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create conversation to start chatting.
        conversation_id, chat_endpoint_url = self._create_successful_conversation()

        # Start conversing with OpenAI
        with mock.patch(
            'text_search.serializers.async_call_celery_task_chain',
            side_effect=chat_chain_side_effect_1,
        ) as mock_chain:
            response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_1)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            mock_chain.assert_called_once_with(**CHAT_CHAIN_EXPECTED_ARGUMENTS_1)

        query_results = response.data['query_results']
        self.assertEqual(query_results, [CHAT_CHAIN_EXPECTED_QUERY_RESULTS_1])

        # Continue the conversation.
        with mock.patch(
            'text_search.serializers.async_call_celery_task_chain',
            side_effect=chat_chain_side_effect_2,
        ) as mock_chain:
            response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_2)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

            mock_chain.assert_called_once_with(**CHAT_CHAIN_EXPECTED_ARGUMENTS_2)

        query_results = response.data['query_results']
        self.assertEqual(
            query_results,
            [CHAT_CHAIN_EXPECTED_QUERY_RESULTS_1, CHAT_CHAIN_EXPECTED_QUERY_RESULTS_2],
        )

        # Retrieve the conversation instance.
        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': conversation_id})
        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # Chat failure

    def test_chat_fails_because_not_authed(self) -> None:
        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_1)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chat_fails_because_not_allowed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        _, chat_endpoint_url = self._create_successful_conversation()

        response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_chat_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': 999})

        response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_1)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chat_fails_because_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        _, chat_endpoint_url = self._create_successful_conversation()

        # Chat
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_1)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_chat_fails_because_usage_limit(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.low_limit_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        self.assertEqual(self.low_limit_auth_user.user_profile.used_cost, 0.0)

        _, chat_endpoint_url = self._create_successful_conversation()

        with mock.patch(
            'text_search.serializers.async_call_celery_task_chain',
            side_effect=chat_chain_side_effect_1,
        ):
            response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_1)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.low_limit_auth_user.refresh_from_db()
        self.assertEqual(self.low_limit_auth_user.user_profile.used_cost, 0.05)

        with mock.patch(
            'text_search.serializers.async_call_celery_task_chain',
            side_effect=chat_chain_side_effect_2,
        ):
            response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_2)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.low_limit_auth_user.refresh_from_db()
        self.assertAlmostEqual(self.low_limit_auth_user.user_profile.used_cost, 0.15)
        self.assertGreater(
            self.low_limit_auth_user.user_profile.used_cost,
            self.low_limit_auth_user.user_profile.custom_usage_limit_euros,
        )

        response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # Delete

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_delete(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        conversation_id, chat_endpoint_url = self._create_successful_conversation()

        # Start conversing with OpenAI
        with mock.patch(
            'text_search.serializers.async_call_celery_task_chain',
            side_effect=chat_chain_side_effect_1,
        ):
            response = self.client.post(chat_endpoint_url, data=CHAT_INPUT_1)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        results = response.data['query_results']
        self.assertEqual(len(results), 1)

        # Delete and assert nothing remains.
        delete_uri = reverse('v1:text_search-bulk-destroy')
        response = self.client.delete(delete_uri, data={'ids': [conversation_id]})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(TextSearchConversation.objects.filter(id=conversation_id).exists())
        self.assertFalse(
            TextSearchQueryResult.objects.filter(conversation__id=conversation_id).exists()
        )

    def test_delete_fails_because_other_user(self) -> None:
        # Create the first conversation which should be protected from deletion.
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        protected_conversation_id, _ = self._create_successful_conversation()

        # User making the deletion.
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        to_delete_conversation_id, _ = self._create_successful_conversation()

        # Delete and assert that only one of them has been destroyed.
        delete_uri = reverse('v1:text_search-bulk-destroy')
        data = {'ids': [protected_conversation_id, to_delete_conversation_id]}

        response = self.client.delete(delete_uri, data=data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(
            TextSearchConversation.objects.filter(id=to_delete_conversation_id).exists()
        )
        self.assertTrue(
            TextSearchConversation.objects.filter(id=protected_conversation_id).exists()
        )
