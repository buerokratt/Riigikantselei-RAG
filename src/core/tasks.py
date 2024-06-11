from typing import Optional

import openai

from api.celery_handler import app
from api.utilities.gpt import ChatGPT, LLMResponse
from core.models import LLMResult, ChatGPTConversation


# TODO: Revisit the retry parameters, or do it by hand, probably using the headers information about timeout expirations would be useful.


# Using bind sets the Celery Task object to the first argument, in this case self.
@app.task(name="commit_openai_api_call", autoretry_for=(openai.InternalServerError, openai.RateLimitError, openai.UnprocessableEntityError, openai.APITimeoutError), max_retries=5, bind=True)
def commit_openai_api_call(self, conversation_pk, user_text: str, model: Optional[str]):
    conversation = ChatGPTConversation.objects.get(pk=conversation_pk)

    messages = conversation.messages + [{"role": "user", "content": user_text}]

    gpt = ChatGPT(model=model)
    llm_response: LLMResponse = gpt.chat(user_input=user_text, messages=messages)

    orm: LLMResult = LLMResult.objects.create(
        conversation=conversation,
        celery_task_id=self.request.id,
        response=llm_response.message,
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
