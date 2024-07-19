from copy import deepcopy
from typing import Any, Dict
from unittest import mock

from rest_framework.exceptions import APIException
from rest_framework.test import APITestCase

from api.utilities.gpt import (
    ChatGPT,
    ContentFilteredException,
    construct_messages_for_testing,
)
from api.utilities.tests.test_settings import (
    GPT_HEADERS,
    GPT_RESPONSE,
    GPT_RESPONSE_DICT,
    GPT_STATUS_CODE,
)


class ChatGPTTestCase(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.api_response_headers = GPT_HEADERS
        self.api_response: Dict[str, Any] = GPT_RESPONSE_DICT
        self.api_status_code = GPT_STATUS_CODE

        self.user_input = 'hello there'
        self.messages = construct_messages_for_testing(
            'You are a helpful assistant.', self.user_input
        )

    def test_simple_chat_completion(self) -> None:
        return_values = (self.api_response_headers, self.api_response, self.api_status_code)
        with mock.patch(
            'api.utilities.gpt.ChatGPT._commit_api', return_value=return_values
        ) as mock_gpt:
            gpt = ChatGPT(api_key=None)
            llm_result = gpt.chat(messages=self.messages)

            mock_gpt.assert_called_once_with(messages=self.messages)

        self.assertEqual(llm_result.user_input, self.user_input)
        self.assertEqual(llm_result.message, GPT_RESPONSE)

        # Assert the model is the full name instead of the simple gpt-4o we give in.
        self.assertEqual(llm_result.model, 'gpt-4o-2024-05-13')

        self.assertEqual(llm_result.input_tokens, 20)
        self.assertEqual(llm_result.response_tokens, 9)
        self.assertEqual(llm_result.total_tokens, 29)

        self.assertEqual(llm_result.ratelimit_tokens, 30000)
        self.assertEqual(llm_result.ratelimit_requests, 500)
        self.assertEqual(llm_result.remaining_requests, 499)
        self.assertEqual(llm_result.remaining_tokens, 29972)
        self.assertEqual(llm_result.reset_requests_at_ms, '120ms')
        self.assertEqual(llm_result.reset_tokens_at_ms, '56ms')

        self.assertAlmostEqual(llm_result.total_cost, 0.000235)

    def test_errors_being_caught_with_api_exceptions(self) -> None:
        with self.assertRaises(APIException):
            gpt = ChatGPT(api_key='foo')
            _ = gpt.chat(messages=self.messages)

    def test_exceptions_being_triggered_on_content_filter(self) -> None:
        api_response = deepcopy(self.api_response)
        api_response['choices'][0]['finish_reason'] = 'content_filter'

        with self.assertRaises(ContentFilteredException):
            return_values = (self.api_response_headers, api_response, self.api_status_code)
            with mock.patch('api.utilities.gpt.ChatGPT._commit_api', return_value=return_values):
                gpt = ChatGPT(api_key=None)
                _ = gpt.chat(messages=self.messages)
