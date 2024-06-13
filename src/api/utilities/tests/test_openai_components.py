from typing import Any, Dict
from unittest import mock

from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APITestCase

from api.utilities.gpt import ChatGPT, ContentFilteredException


class ChatGPTTestCase(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.api_response: Dict[str, Any] = {
            'id': 'chatcmpl-9WkWmu5OQwhsYRJvFArNzDwlBuhAa',
            'choices': [
                {
                    'finish_reason': 'stop',
                    'index': 0,
                    'logprobs': None,
                    'message': {
                        'content': 'Hello! How can I assist you today?',
                        'role': 'assistant',
                    },
                }
            ],
            'created': 1717592376,
            'model': 'gpt-4o-2024-05-13',
            'object': 'chat.completion',
            'system_fingerprint': 'fp_319be4768e',
            'usage': {'completion_tokens': 9, 'prompt_tokens': 20, 'total_tokens': 29},
        }
        self.api_response_headers = {
            'date': 'Wed, 05 Jun 2024 12:59:36 GMT',
            'content-type': 'application/json',
            'transfer-encoding': 'chunked',
            'connection': 'keep-alive',
            'openai-organization': 'texta-o',
            'openai-processing-ms': '500',
            'openai-version': '2020-10-01',
            'strict-transport-security': 'max-age=15724800; includeSubDomains',
            'x-ratelimit-limit-requests': '500',
            'x-ratelimit-limit-tokens': '30000',
            'x-ratelimit-remaining-requests': '499',
            'x-ratelimit-remaining-tokens': '29972',
            'x-ratelimit-reset-requests': '120ms',
            'x-ratelimit-reset-tokens': '56ms',
            'x-request-id': 'req_b74e6ad94b04367098b39f1c3acf54b2',
            'cf-cache-status': 'DYNAMIC',
            'set-cookie': (
                '__cf_bm=LDZOZXQfvCDzOrqomiWkkMMZ4eqrPsvPSpM2M9NYKZs-1717592376-1.0.1.1-60MKAcfYU'
                'o50.hDcIfIfgz8zR4psKcCnGCMwGyOBWwJv1OgmRUHEuL4puwiuUb_2JeMy3d_fn0fvmKsxKxXmbA; '
                'path=/; expires=Wed, 05-Jun-24 13:29:36 GMT; domain=.api.openai.com; HttpOnly; '
                'Secure; SameSite=None, '
                '_cfuvid=_9iq19utMBYd3JjR8OQZ2OVFHI16qkFU4GPF6FLNSRo-1717592376822-0.0.1.1-'
                '604800000; '
                'path=/; domain=.api.openai.com; HttpOnly; Secure; SameSite=None'
            ),
            'server': 'cloudflare',
            'cf-ray': '88f0573e1a507125-TLL',
            'content-encoding': 'gzip',
            'alt-svc': 'h3=":443"; ma=86400',
        }

        self.api_status_code = 200

    def test_simple_chat_completion(self) -> None:
        with mock.patch(
            'api.utilities.gpt.ChatGPT.commit_api',
            return_value=(self.api_response_headers, self.api_response, self.api_status_code),
        ):
            gpt = ChatGPT(api_key='None')
            llm_result = gpt.chat(user_input='hello there')

            # Asser the model is the full name instead of the simple gpt-4o we give in.
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

    def test_errors_being_caught_with_api_exceptions(self) -> None:
        with self.assertRaises(AuthenticationFailed):
            gpt = ChatGPT(api_key='None')
            _ = gpt.chat(user_input='hello there')

    def test_exceptions_being_triggered_on_content_filter(self) -> None:
        self.api_response['choices'][0]['finish_reason'] = 'content_filter'
        with self.assertRaises(ContentFilteredException):
            with mock.patch(
                'api.utilities.gpt.ChatGPT.commit_api',
                return_value=(self.api_response_headers, self.api_response, self.api_status_code),
            ):
                gpt = ChatGPT(api_key='None')
                _ = gpt.chat(user_input='hello there')
