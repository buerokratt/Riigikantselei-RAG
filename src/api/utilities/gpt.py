import logging
import os
import re
from typing import List, Optional, Tuple

import django
import openai
from django.utils.translation import gettext as _
from rest_framework.exceptions import APIException

from core.models import CoreVariable

logger = logging.getLogger(__name__)


# pylint: disable=too-many-instance-attributes


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
        self.raw_message = message
        self.model = model
        self.user_input = user_input

        self.input_tokens = input_tokens
        self.response_tokens = response_tokens
        self.headers = headers

        self.__message: str = ''
        self.__information_found: Optional[bool] = None
        self.__used_references: List[int] = []

    @property
    def message(self) -> str:
        if not self.__message:
            try:
                # Excpects the raw message in the following format:
                # <message>\n\n<sources>
                self.__message = self.raw_message.rsplit('\n\n', 1)[0]
            except Exception:  # pylint: disable=broad-exception-caught
                self.__message = self.raw_message
        return self.__message

    @property
    def information_found(self) -> bool:
        if self.__information_found is None:
            no_information_text = CoreVariable.get_core_setting('OPENAI_MISSING_CONTEXT_MESSAGE')
            if re.search(no_information_text.lower(), self.raw_message, re.IGNORECASE):
                self.__information_found = False
            else:
                self.__information_found = True
        return self.__information_found

    @property
    def used_references(self) -> List[int]:
        if not self.__used_references:
            try:
                if self.information_found:
                    sources_text = CoreVariable.get_core_setting('OPENAI_SOURCES_TEXT')
                    sources = self.raw_message.rsplit('\n\n', 1)[-1].strip()
                    cleaned_sources = re.sub(rf'{sources_text}\s*', '', sources)
                    references = [
                        int(reference.strip()) for reference in cleaned_sources.split(',')
                    ]
                    self.__used_references = references
            except Exception:  # pylint: disable=broad-exception-caught
                logger.exception('Error while getting used references')

        return self.__used_references

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
        return self.input_tokens * CoreVariable.get_core_setting(
            'EURO_COST_PER_INPUT_TOKEN'
        ) + self.response_tokens * CoreVariable.get_core_setting('EURO_COST_PER_OUTPUT_TOKEN')

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
        api_key = api_key or CoreVariable.get_core_setting('OPENAI_API_KEY')
        timeout = timeout or CoreVariable.get_core_setting('OPENAI_API_TIMEOUT')
        max_retries = max_retries or CoreVariable.get_core_setting('OPENAI_API_MAX_RETRIES')

        self.model = model or CoreVariable.get_core_setting('OPENAI_API_CHAT_MODEL')

        if api_key is not None:
            self.gpt = openai.OpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)
        else:
            logger.warning('No OpenAI API key found, this better be testing!')
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
        temperature = CoreVariable.get_core_setting('OPENAI_API_TEMPERATURE')

        if self.gpt is None:
            message = _("No OpenAI API key given, can't query API!")
            raise APIException(message)

        try:
            response = self.gpt.chat.completions.with_raw_response.create(
                model=self.model, stream=False, messages=messages, temperature=temperature
            )

            headers = dict(response.headers)
            response_dict = response.parse().to_dict()
            status_code = response.status_code
            return headers, response_dict, status_code

        except openai.AuthenticationError as exception:
            logger.exception("Couldn't authenticate with OpenAI API!")
            message = _("Couldn't authenticate with OpenAI API!")
            raise APIException(message) from exception

        except openai.BadRequestError as exception:
            logger.exception('Sent invalid request towards OpenAI API!')
            message = _('OpenAI request is not correct!')
            raise APIException(message) from exception

        except openai.InternalServerError as exception:
            logger.exception('Issues on OpenAI server!')
            raise exception

        except openai.NotFoundError as exception:
            logger.exception('Could not find resource in OpenAI API! (is the model correct?)')
            message = _('Requested resource was not found! Is the right model configured?')
            raise APIException(message) from exception

        except openai.PermissionDeniedError as exception:
            logger.exception('Permissions denied by OpenAI API!')
            message = _('Requested resource was denied!')
            raise APIException(message) from exception

        except openai.RateLimitError as exception:
            logger.warning('Hitting OpenAI API rate limits!')
            raise exception from exception

        except openai.UnprocessableEntityError as exception:
            logger.exception('Unable to process the request despite the format being correct!')
            raise exception from exception

        except openai.APITimeoutError as exception:
            logger.warning('Hitting OpenAI API timeouts!')
            raise exception

        except openai.APIConnectionError as exception:
            logger.exception('Unable to connect to OpenAI API!')
            message = _("Couldn't connect to the OpenAI API!")
            raise APIException(message) from exception

        except Exception as exception:
            logger.exception('Unhandled exception when connecting to OpenAI API!')
            message = _("Couldn't connect to the OpenAI API!")
            raise APIException(message) from exception

    def chat(self, messages: List[dict]) -> LLMResponse:
        user_input = messages[-1]['content']
        headers, response, _ = self._commit_api(messages=messages)
        llm_result = self._parse_results(user_input=user_input, response=response, headers=headers)
        return llm_result


if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
    django.setup()

    gpt = ChatGPT()
    gpt_response = gpt.chat([{'response': 'Hello there!'}])

    logger.info(gpt_response)
