import logging
import os
from typing import Optional, Tuple

import django
import openai
from openai import OpenAI
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotFound,
    PermissionDenied,
    ValidationError,
)

from api.utilities.core_settings import get_core_setting

logger = logging.getLogger(__name__)


# TODO Maybe replace this with an actual DB model later on
#  but for now it's a good enough abstraction for GPT responses.
class LLMResponse:
    def __init__(
        self,
        message: str,
        model: str,
        system_input: str,
        user_input: str,
        input_tokens: int,
        response_tokens: int,
        headers: dict,
    ):  # pylint: disable=too-many-arguments
        self.message = message
        self.system_input = system_input
        self.user_input = user_input

        self.model = model
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

    def __str__(self) -> str:
        return f'{self.message} / {self.total_tokens} tokens used'


class ContentFilteredException(Exception):
    pass


class ChatGPT:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.api_key = api_key or get_core_setting('OPENAI_API_KEY')
        self.timeout = timeout or get_core_setting('OPENAI_API_TIMEOUT')
        self.max_retries = max_retries or get_core_setting('OPENAI_API_MAX_RETRIES')

        self.model = model or get_core_setting('OPENAI_API_CHAT_MODEL')
        self.gpt = OpenAI(api_key=self.api_key, timeout=self.timeout, max_retries=self.max_retries)

    def _parse_message(self, response: dict, user_input: str) -> str:
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

    def parse_results(
        self, system_input: str, user_input: str, response: dict, headers: dict
    ) -> LLMResponse:
        message = self._parse_message(response, user_input)

        return LLMResponse(
            message=message,
            system_input=system_input,
            user_input=user_input,
            model=response.get('model', self.model),
            input_tokens=response.get('usage', {}).get('prompt_tokens'),
            response_tokens=response.get('usage', {}).get('completion_tokens'),
            headers=headers,
        )

    def commit_api(self, system_input: str, user_input: str) -> Tuple[dict, dict, int]:
        try:
            response = self.gpt.chat.completions.with_raw_response.create(
                model=self.model,
                stream=False,
                messages=[
                    {'role': 'system', 'content': system_input},
                    {'role': 'user', 'content': user_input},
                ],
            )

            headers = dict(response.headers)
            response = response.parse().to_dict()
            status_code = response.status_code
            return headers, response, status_code

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

    def chat(self, user_input: str, system_input: Optional[str] = None) -> LLMResponse:
        system_input = system_input or get_core_setting('OPENAI_SYSTEM_MESSAGE')
        headers, response, _ = self.commit_api(system_input, user_input)
        llm_result = self.parse_results(
            system_input=system_input, user_input=user_input, response=response, headers=headers
        )
        return llm_result


if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
    django.setup()

    gpt = ChatGPT()
    gpt_response = gpt.chat('Hello there!')

    logger.info(gpt_response)
