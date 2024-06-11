import logging
from typing import List

import openai
from openai import OpenAI
from rest_framework.exceptions import AuthenticationFailed, ValidationError, NotFound, PermissionDenied, APIException

from api.utilities.core_settings import get_core_setting

logger = logging.getLogger("chatgpt")


# TODO Maybe replace this with an actual DB model later on but for now it's a good enough abstraction for GPT responses.
class LLMResponse:
    def __init__(self, message: str, model: str, user_input: str, input_tokens: int, response_tokens: int, headers: dict):
        self.message = message
        self.user_input = user_input

        self.model = model
        self.input_tokens = input_tokens
        self.response_tokens = response_tokens
        self.headers = headers

    @property
    def ratelimit_requests(self):
        return int(self.headers.get("x-ratelimit-limit-requests"))

    @property
    def ratelimit_tokens(self):
        return int(self.headers.get("x-ratelimit-limit-tokens"))

    @property
    def remaining_requests(self):
        return int(self.headers.get("x-ratelimit-remaining-requests"))

    @property
    def remaining_tokens(self):
        return int(self.headers.get("x-ratelimit-remaining-tokens"))

    @property
    def reset_requests_at_ms(self):
        return self.headers.get("x-ratelimit-reset-requests")

    @property
    def reset_tokens_at_ms(self):
        return self.headers.get("x-ratelimit-reset-tokens")

    @property
    def total_tokens(self):
        return self.input_tokens + self.response_tokens

    def __str__(self):
        return f"{self.message} / {self.total_tokens} tokens used"


class ContentFilteredException(Exception):
    pass


class ChatGPT:

    def __init__(self, api_key=None, model=None, timeout=None, max_retries=None):
        self.api_key = api_key or get_core_setting("OPENAI_API_KEY")
        self.timeout = timeout or get_core_setting("OPENAI_API_TIMEOUT")
        self.max_retries = max_retries or get_core_setting("OPENAI_API_MAX_RETRIES")

        self.model = model or get_core_setting("OPENAI_API_CHAT_MODEL")
        self.gpt = OpenAI(api_key=self.api_key, timeout=self.timeout, max_retries=self.max_retries)

    def _parse_message(self, response: dict, user_input: str) -> str:
        # This will be stop if the model hit a natural stop point or a provided stop sequence,
        # length if the maximum number of tokens specified in the request was reached,
        # content_filter if content was omitted due to a flag from our content filters
        message = None

        for choice in response.get("choices", []):
            finish_reason = choice.get("finish_reason", "N/A")
            if finish_reason == "content_filter":
                message = f"Input {user_input} was filtered by OpenAI API!"
                logger.warning(message)
                raise ContentFilteredException(message)

            if finish_reason == "stop":
                message = choice.get("message", {}).get("content", None)

        return message

    def parse_results(self, user_input: str, response: dict, headers: dict):
        message = self._parse_message(response, user_input)

        return LLMResponse(
            message=message,
            user_input=user_input,
            model=response.get("model", self.model),
            input_tokens=response.get("usage", {}).get("prompt_tokens"),
            response_tokens=response.get("usage", {}).get("completion_tokens"),
            headers=headers
        )

    def commit_api(self, messages: List[dict]) -> (dict, dict, int):
        try:
            response = self.gpt.chat.completions.with_raw_response.create(
                model=self.model,
                stream=False,
                messages=messages
            )

            headers = dict(response.headers)
            status_code = response.status_code
            response = response.parse().to_dict()
            return headers, response, status_code

        except openai.AuthenticationError as e:
            logger.exception(f"Couldn't authenticate with OpenAI API! Status: {e.status_code} Response: {e.response.text}")
            raise AuthenticationFailed("Couldn't authenticate with OpenAI API!")

        except openai.BadRequestError as e:
            logger.exception(f"OpenAI request is malformed! Status: {e.status_code} Response: {e.response.text}")
            raise ValidationError("OpenAI request is not correct!")

        # TODO: We will be handling this exception with retries later, either through Celery or something else.
        except openai.InternalServerError as e:
            logger.exception(f"Issues on OpenAI server! Status: {e.status_code} Response: {e.response.text}")
            raise e

        except openai.NotFoundError as e:
            logger.exception(f"Requested resource was not found! Status: {e.status_code} Response: {e.response.text}")
            raise NotFound("Requested resource was not found! Is the right model configured?")

        except openai.PermissionDeniedError as e:
            logger.exception(f"Requested resource was denied! Status: {e.status_code} Response: {e.response.text}")
            raise PermissionDenied("Requested resource was denied!")

        # TODO: We will be handling this exception with retries later, either through Celery or something else.
        except openai.RateLimitError as e:
            logger.warning(f"Requested resource was rate-limited! Status: {e.status_code} Response: {e.response.text}")
            raise e

        # TODO: We will be handling this exception with retries later, either through Celery or something else.
        except openai.UnprocessableEntityError as e:
            logger.exception(f"Unable to process the request despite the format being correct! Status: {e.status_code} Response: {e.response.text}")
            raise e

        # TODO: We will be handling this exception with retries later, either through Celery or something else.
        except openai.APITimeoutError as e:
            logger.warning(f"OpenAI API timed out!")
            raise e

        except openai.APIConnectionError as e:
            logger.exception(f"Couldn't connect to the OpenAI API")
            raise APIException("Couldn't connect to the OpenAI API!")

        except Exception as e:
            logger.exception(f"Couldn't connect to the OpenAI API")
            raise APIException("Couldn't connect to the OpenAI API!")

    def chat(self, user_input: str, messages: List[dict]):
        headers, response, status_code = self.commit_api(messages)
        llm_result = self.parse_results(user_input=user_input, response=response, headers=headers)
        return llm_result


if __name__ == '__main__':
    import os, django

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
    django.setup()

    gpt = ChatGPT()
    response = gpt.chat("Hello there!")
    pass
