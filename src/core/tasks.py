from typing import List, Optional

import openai
from django.conf import settings

from api.celery_handler import app
from api.utilities.elastic import ElasticCore
from api.utilities.gpt import ChatGPT, LLMResponse
from api.utilities.vectorizer import Vectorizer
from core.models import ChatGPTConversation, LLMResult

# TODO: Revisit the retry parameters, or do it by hand, probably using the headers information about timeout expirations would be useful.


@app.task(name='get_rag_context', max_retries=5, bind=True)
def get_rag_context(
    self, input_text: str, indices: List[str], vector_field: str, content_field: str
):
    """
    Task for fetching the RAG context from pre-processed vectors in ElasticSearch.

    :param self: Contains access to the Celery Task instance.
    :param input_text: User sent input to vectorise and search from Elasticsearch.
    :param indices: Which indices to search from Elasticsearch.
    :param vector_field: Which field in the indices contains the pre-vectorized information to search from.
    :param content_field: Which field in the indices contains the textual information we need to send to OpenAI.
    :return:
    """
    ec = ElasticCore()
    vectorizer = Vectorizer(
        model_name=settings.VECTORIZATION_MODEL_NAME,
        system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
        inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
        model_directory=settings.MODEL_DIRECTORY,
    )

    input_vectors = vectorizer.vectorize([input_text])['vectors'][0]
    indices = ','.join(indices)
    matching_documents = ec.search_vector(
        indices=indices, vector=input_vectors, comparison_field=vector_field
    )

    container = []
    for hit in matching_documents['hits']['hits']:
        content = hit['_source'].get(content_field, None)
        if content:
            container.append(content)

    context = '\n\n'.join(container)
    template = (
        f''
        f'Answer the following question using the provided context from below! '
        f'Question: ```{input_text}```\n\n'
        f'Context: ```{context}```'
    )

    return template


# Using bind sets the Celery Task object to the first argument, in this case self.
@app.task(
    name='commit_openai_api_call',
    autoretry_for=(
        openai.InternalServerError,
        openai.RateLimitError,
        openai.UnprocessableEntityError,
        openai.APITimeoutError,
    ),
    max_retries=5,
    bind=True,
)
def commit_openai_api_call(self, user_text: str, conversation_pk: int, model: Optional[str]):
    conversation = ChatGPTConversation.objects.get(pk=conversation_pk)

    messages = conversation.messages + [{'role': 'user', 'content': user_text}]

    gpt = ChatGPT(model=model)
    llm_response: LLMResponse = gpt.chat(messages=messages)

    orm: LLMResult = LLMResult.objects.create(
        conversation=conversation,
        celery_task_id=self.request.id,
        response=llm_response.message,
        user_input=llm_response.user_input,
        model=llm_response.model,
        input_tokens=llm_response.input_tokens,
        output_tokens=llm_response.response_tokens,
        headers=llm_response.headers,
    )

    return {
        'response': orm.response,
        'input_tokens': orm.input_tokens,
        'output_tokens': orm.output_tokens,
    }
