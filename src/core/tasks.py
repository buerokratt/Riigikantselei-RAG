from typing import List

import openai
from celery import Task
from celery.result import AsyncResult
from django.conf import settings

from api.celery_handler import app
from api.utilities.core_settings import get_core_setting
from api.utilities.elastic import ElasticCore
from api.utilities.gpt import ChatGPT
from api.utilities.vectorizer import Vectorizer
from core.models import TextSearchConversation

# pylint: disable=unused-argument,too-many-arguments

# TODO: Revisit the retry parameters, or do it by hand,
#   probably using the headers information about timeout expirations would be useful.

# TODO: add real RAG logic to the tasks when it is ready and unit test them


def async_call_celery_task_chain(
    min_year: int,
    max_year: int,
    user_input: str,
    document_indices: List[str],
    conversation_id: int,
    document_types_string: str,
) -> AsyncResult:
    task_chain = query_and_format_rag_context.s(
        min_year=min_year,
        max_year=max_year,
        user_input=user_input,
        document_indices=document_indices,
    ) | call_openai_api.s(
        conversation_id=conversation_id,
        min_year=min_year,
        max_year=max_year,
        document_types_string=document_types_string,
        user_input=user_input,
    )

    return task_chain.apply_async()


@app.task(name='query_and_format_rag_context', max_retries=5, bind=True)
def query_and_format_rag_context(
    self: Task, min_year: int, max_year: int, user_input: str, document_indices: List[str]
) -> str:
    """
    Task for fetching the RAG context from pre-processed vectors in ElasticSearch.

    :param self: Contains access to the Celery Task instance.
    :param min_year: Earliest year to consider documents from.
    :param max_year: Latest year to consider documents from.
    :param user_input: User sent input to add context to.
    :param document_indices: Which indices to search from Elasticsearch.
    :return: Text containing user input and relevant context documents.
    """
    vectorizer = Vectorizer(
        model_name=settings.VECTORIZATION_MODEL_NAME,
        system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
        inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
        model_directory=settings.MODEL_DIRECTORY,
    )
    input_vectors = vectorizer.vectorize([user_input])['vectors'][0]

    elastic_core = ElasticCore()
    indices_string = ','.join(document_indices)
    # TODO here: use year range to filter documents
    # TODO here: unit test index and year filtering
    matching_documents = elastic_core.search_vector(
        indices=indices_string,
        vector=input_vectors,
        comparison_field=get_core_setting('ELASTICSEARCH_VECTOR_FIELD'),
    )

    content_field = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')
    context_documents_contents = []
    for hit in matching_documents['hits']['hits']:
        content = hit['_source'].get(content_field, None)
        if content:
            context_documents_contents.append(content)

    context = '\n\n'.join(context_documents_contents)
    query_with_context = (
        'Answer the following question using the provided context from below! '
        f'Question: ```{user_input}```'
        '\n\n'
        f'Context: ```{context}```'
    )

    return query_with_context


# Using bind sets the Celery Task object to the first argument, in this case self.
@app.task(
    name='call_openai_api',
    autoretry_for=(
        openai.InternalServerError,
        openai.RateLimitError,
        openai.UnprocessableEntityError,
        openai.APITimeoutError,
    ),
    max_retries=5,
    bind=True,
)
def call_openai_api(
    self: Task,
    user_input_with_context: str,
    conversation_id: int,
    min_year: int,
    max_year: int,
    document_types_string: str,
    user_input: str,
) -> dict:
    """
    Task for fetching the RAG context from pre-processed vectors in ElasticSearch.

    :param self: Contains access to the Celery Task instance.
    :param user_input_with_context: Text containing user input and relevant context documents.
    :param conversation_id: ID of the conversation this API call is a part of.
    :param min_year: Earliest year to consider documents from.
    :param max_year: Latest year to consider documents from.
    :param document_types_string: Which indices to search from Elasticsearch.
    :param user_input: User sent input to send to the LLM.
    :return: Dict needed to build a TextSearchQueryResult.
    """
    conversation = TextSearchConversation.objects.get(id=conversation_id)

    messages = conversation.messages + [{'role': 'user', 'content': user_input_with_context}]

    chat_gpt = ChatGPT()
    llm_response = chat_gpt.chat(messages=messages)

    # The output is a dict of all the input data needed to create a TextSearchQueryResult.
    # To separate testing of view and model logic from testing of RAG logic,
    # the TextSearchQueryResult is created in the view.
    query_result_parameters = {
        'conversation': conversation_id,
        'celery_task_id': self.id,
        'model': llm_response.model,
        'min_year': min_year,
        'max_year': max_year,
        'document_types_string': document_types_string,
        'user_input': user_input,
        'response': llm_response.message,
        'input_tokens': llm_response.input_tokens,
        'output_tokens': llm_response.response_tokens,
        'total_cost': llm_response.total_cost,
        'response_headers': llm_response.headers,
    }

    return query_result_parameters
