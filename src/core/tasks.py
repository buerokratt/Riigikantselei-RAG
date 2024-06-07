from typing import Optional

import openai

from api.celery_handler import app
from api.utilities.gpt import ChatGPT, LLMResponse
from core.models import LLMResult


# TODO: Revisit the retry parameters, or do it by hand, probably using the headers information about timeout expirations would be useful.


# Using bind sets the Celery Task object to the first argument, in this case self.
@app.task(name="commit_openai_api_call", autoretry_for=(openai.InternalServerError, openai.RateLimitError, openai.UnprocessableEntityError, openai.APITimeoutError), max_retries=5, bind=True)
def commit_openai_api_call(self, system_text: Optional[str], user_text: str, model: Optional[str]):
    gpt = ChatGPT(model=model)
    llm_response: LLMResponse = gpt.chat(user_input=user_text, system_input=system_text)

    orm: LLMResult = LLMResult.objects.create(
        celery_task_id=self.request.id,
        response=llm_response.message,
        system_input=llm_response.system_input,
        user_input=llm_response.user_input,
        model=llm_response.model,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.response_tokens,
        headers=llm_response.headers
    )

    return {
        "response": orm.response,
        "input_tokens": orm.input_tokens,
        "output_tokens": orm.output_tokens
    }
