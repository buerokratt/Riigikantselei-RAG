import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import django
import openai
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from api.utilities.core_settings import get_core_setting

logger = logging.getLogger(__name__)


MOCK_RESPONSE = 'Hello! How can I assist you today?'


MOCK_HEADERS = {
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
        'path=/; '
        'expires=Wed, 05-Jun-24 13:29:36 GMT; '
        'domain=.api.openai.com; '
        'HttpOnly; '
        'Secure; '
        'SameSite=None, '
        '_cfuvid=_9iq19utMBYd3JjR8OQZ2OVFHI16qkFU4GPF6FLNSRo-1717592376822-0.0.1.1-'
        '604800000; '
        'path=/; '
        'domain=.api.openai.com; '
        'HttpOnly; '
        'Secure; '
        'SameSite=None'
    ),
    'server': 'cloudflare',
    'cf-ray': '88f0573e1a507125-TLL',
    'content-encoding': 'gzip',
    'alt-svc': 'h3=":443"; ma=86400',
}
MOCK_RESPONSE_DICT: Dict[str, Any] = {
    'id': 'chatcmpl-9WkWmu5OQwhsYRJvFArNzDwlBuhAa',
    'choices': [
        {
            'finish_reason': 'stop',
            'index': 0,
            'logprobs': None,
            'message': {
                'content': MOCK_RESPONSE,
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
MOCK_STATUS_CODE = 200


class LLMResponse:
    def __init__(
        self,
        message: str,
        model: str,
        user_input: str,
        input_tokens: int,
        response_tokens: int,
        headers: dict,
    ):  # pylint: disable=too-many-arguments
        self.message = message
        self.model = model
        self.user_input = user_input

        self.input_tokens = input_tokens
        self.response_tokens = response_tokens
        self.headers = headers

    @property
    def ratelimit_requests(self) -> int:
        return int(str(self.headers.get('x-ratelimit-limit-requests')))

    @property
    def ratelimit_tokens(self) -> int:
        return int(str(self.headers.get('x-ratelimit-limit-tokens')))

    @property
    def remaining_requests(self) -> int:
        return int(str(self.headers.get('x-ratelimit-remaining-requests')))

    @property
    def remaining_tokens(self) -> int:
        return int(str(self.headers.get('x-ratelimit-remaining-tokens')))

    @property
    def reset_requests_at_ms(self) -> str:
        return str(self.headers.get('x-ratelimit-reset-requests'))

    @property
    def reset_tokens_at_ms(self) -> str:
        return str(self.headers.get('x-ratelimit-reset-tokens'))

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.response_tokens

    @property
    def total_cost(self) -> float:
        return self.input_tokens * get_core_setting(
            'EURO_COST_PER_INPUT_TOKEN'
        ) + self.response_tokens * get_core_setting('EURO_COST_PER_OUTPUT_TOKEN')

    def __str__(self) -> str:
        return f'{self.message} / {self.total_tokens} tokens used'


class ContentFilteredException(Exception):
    pass


def _parse_message(response: dict, user_input: str) -> str:
    # This will be stop if the model hit a natural stop point or a provided stop sequence,
    # length if the maximum number of tokens specified in the request was reached,
    # content_filter if content was omitted due to a flag from our content filters
    message = None

    for choice in response.get('choices', []):
        finish_reason = choice.get('finish_reason', 'N/A')
        if finish_reason == 'content_filter':
            message = f'Input {user_input} was filtered by OpenAI API!'
            raise ContentFilteredException(message)

        if finish_reason == 'stop':
            message = choice.get('message', {}).get('content', None)

    if message is None:
        raise RuntimeError

    return message


def construct_messages_for_testing(system_input: str, user_input: str) -> List[dict]:
    return [
        {'role': 'system', 'content': system_input},
        {'role': 'user', 'content': user_input},
    ]


class ChatGPT:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        api_key = api_key or get_core_setting('OPENAI_API_KEY')
        timeout = timeout or get_core_setting('OPENAI_API_TIMEOUT')
        max_retries = max_retries or get_core_setting('OPENAI_API_MAX_RETRIES')

        self.model = model or get_core_setting('OPENAI_API_CHAT_MODEL')

        if api_key is not None:
            self.gpt = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
        else:
            logger.warning('No OpenAI API key found, using mocked API connection to allow testing!')
            self.gpt = None

    def _parse_results(self, user_input: str, response: dict, headers: dict) -> LLMResponse:
        message = _parse_message(response, user_input)

        return LLMResponse(
            message=message,
            model=response.get('model', self.model),
            user_input=user_input,
            input_tokens=response.get('usage', {}).get('prompt_tokens'),
            response_tokens=response.get('usage', {}).get('completion_tokens'),
            headers=headers,
        )

    def _commit_api(self, messages: List[dict]) -> Tuple[dict, dict, int]:
        if self.gpt is None:
            return MOCK_HEADERS, MOCK_RESPONSE_DICT, MOCK_STATUS_CODE

        try:
            response = self.gpt.chat.completions.with_raw_response.create(
                model=self.model, stream=False, messages=messages
            )

            headers = dict(response.headers)
            response_dict = response.parse().to_dict()
            status_code = response.status_code
            return headers, response_dict, status_code

        except openai.AuthenticationError as exception:
            raise AuthenticationFailed("Couldn't authenticate with OpenAI API!") from exception

        except openai.BadRequestError as exception:
            raise ValidationError('OpenAI request is not correct!') from exception

        # TODO: We will be handling this exception with retries later,
        #  either through Celery or something else.
        except openai.InternalServerError as exception:
            logger.exception('Issues on OpenAI server!')
            raise exception

        except openai.NotFoundError as exception:
            raise NotFound(
                'Requested resource was not found! Is the right model configured?'
            ) from exception

        except openai.PermissionDeniedError as exception:
            raise PermissionDenied('Requested resource was denied!') from exception

        # TODO: We will be handling this exception with retries later,
        #  either through Celery or something else.
        except openai.RateLimitError as exception:
            raise exception from exception

        # TODO: We will be handling this exception with retries later,
        #  either through Celery or something else.
        except openai.UnprocessableEntityError as exception:
            logger.exception('Unable to process the request despite the format being correct!')
            raise exception from exception

        # TODO: We will be handling this exception with retries later,
        #  either through Celery or something else.
        except openai.APITimeoutError as exception:
            raise exception

        except openai.APIConnectionError as exception:
            raise APIException("Couldn't connect to the OpenAI API!") from exception

        except Exception as exception:
            raise APIException("Couldn't connect to the OpenAI API!") from exception

    def chat(self, messages: List[dict]) -> LLMResponse:
        user_input = messages[-1]['content']
        headers, response, _ = self._commit_api(messages)
        llm_result = self._parse_results(user_input=user_input, response=response, headers=headers)
        return llm_result


if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
    django.setup()

    gpt = ChatGPT()
    gpt_response = gpt.chat([{'response': 'Hello there!'}])

    logger.info(gpt_response)
