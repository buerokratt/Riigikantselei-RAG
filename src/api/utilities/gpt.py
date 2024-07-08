import logging
import os
from typing import List, Optional, Tuple

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

from .gpt_mocks import MOCK_HEADERS, MOCK_RESPONSE_DICT, MOCK_STATUS_CODE

logger = logging.getLogger(__name__)


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
