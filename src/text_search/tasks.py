import logging
from typing import List

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings

from api.celery_handler import app
from api.utilities.gpt import ChatGPT
from core.base_task import ResourceTask
from core.exceptions import OPENAI_EXCEPTIONS
from text_search.models import TextSearchConversation, TextSearchQueryResult, TextTask

# pylint: disable=unused-argument,too-many-arguments

# TODO: Revisit the retry parameters, or do it by hand,
#   probably using the headers information about timeout expirations would be useful.


# TODO: unit test
def async_call_celery_task_chain(
    user_input: str,
    dataset_index_queries: List[str],
    conversation_id: int,
    result_uuid: str,
) -> None:
    rag_task = query_and_format_rag_context.s(
        conversation_id=conversation_id,
        result_uuid=result_uuid,
        user_input=user_input,
        dataset_index_queries=dataset_index_queries,
    )
    openai_task = call_openai_api.s(
        conversation_id=conversation_id,
        user_input=user_input,
        result_uuid=result_uuid,
    )
    save_task = save_openai_results.s(conversation_id, result_uuid)

    (rag_task | openai_task | save_task).apply_async()


# TODO: implement real RAG logic, then unit test
# Using bind=True sets the Celery Task object to the first argument, in this case celery_task.
@app.task(
    name='query_and_format_rag_context',
    max_retries=5,
    bind=True,
    base=ResourceTask,
    soft_time_limit=settings.CELERY_VECTOR_SEARCH_SOFT_LIMIT,
)
def query_and_format_rag_context(
    celery_task: ResourceTask,
    conversation_id: int,
    result_uuid: str,
    user_input: str,
    dataset_index_queries: List[str],
) -> dict:
    """
    Task for fetching the RAG context from pre-processed vectors in ElasticSearch.

    :param result_uuid: UUID of the Result model to keep track of status.
    :param conversation_id: ID of the conversation.
    :param celery_task: Contains access to the Celery Task instance.
    :param user_input: User sent input to add context to.
    :param dataset_index_queries: Which wildcarded indexes to search from in Elasticsearch.
    :return: Text containing user input and relevant context documents.
    """
    try:
        conversation: TextSearchConversation = TextSearchConversation.objects.get(
            pk=conversation_id
        )
        parents = conversation.get_previous_results_parents_ids()
        result = conversation.query_results.filter(uuid=result_uuid).first()

        context_and_references = conversation.generate_conversations_and_references(
            user_input=user_input,
            dataset_index_queries=dataset_index_queries,
            vectorizer=celery_task.vectorizer,
            encoder=celery_task.encoder,
            parent_references=parents,
            task=result.celery_task,
        )
        return context_and_references
    except SoftTimeLimitExceeded as exception:
        conversation = TextSearchConversation.objects.get(pk=conversation_id)
        TextSearchConversation.handle_celery_timeouts(
            conversation=conversation, result_uuid=result_uuid
        )
        raise exception


# TODO: unit test, mocking like in test_openai_components.py
# Using bind=True sets the Celery Task object to the first argument, in this case celery_task.
@app.task(
    name='call_openai_api',
    autoretry_for=OPENAI_EXCEPTIONS,
    max_retries=10,
    bind=True,
    soft_time_limit=settings.CELERY_OPENAI_SOFT_LIMIT,
)
def call_openai_api(
    celery_task: Task,
    context_and_references: dict,
    conversation_id: int,
    user_input: str,
    result_uuid: str,
) -> dict:
    """
    Task for fetching the RAG context from pre-processed vectors in ElasticSearch.

    :param celery_task: Contains access to the Celery Task instance.
    :param context_and_references: Text containing user input and relevant context documents.
    :param conversation_id: ID of the conversation this API call is a part of.
    :param user_input: User sent input to send to the LLM.
    :param result_uuid: UUID of the TaskResult.
    :return: Dict needed to build a TextSearchQueryResult.
    """
    try:
        conversation = TextSearchConversation.objects.get(id=conversation_id)
        result: TextSearchQueryResult = conversation.query_results.filter(uuid=result_uuid).first()
        text_task: TextTask = result.celery_task

        text_task.set_started()

        user_input_with_context = context_and_references['context']
        references = context_and_references['references']
        is_context_pruned = context_and_references['is_context_pruned']

        messages = conversation.messages + [{'role': 'user', 'content': user_input_with_context}]

        chat_gpt = ChatGPT()
        llm_response = chat_gpt.chat(messages=messages)

        gpt_references = llm_response.used_references

        # Adds binary field 'used_by_gpt'
        for index, reference in enumerate(references):
            if index in gpt_references:
                reference['used_by_gpt'] = True
            else:
                reference['used_by_gpt'] = False

        # The output is a dict of all the input data needed to create a TextSearchQueryResult.
        # To separate testing of view and model logic from testing of RAG logic,
        # the TextSearchQueryResult is created in the view.
        return {
            'model': llm_response.model,
            'user_input': user_input,
            'response': llm_response.message,
            'input_tokens': llm_response.input_tokens,
            'output_tokens': llm_response.response_tokens,
            'total_cost': llm_response.total_cost,
            'response_headers': llm_response.headers,
            'references': references,
            'is_context_pruned': is_context_pruned,
        }

    # Reraise these since they'd be necessary for a retry.
    except OPENAI_EXCEPTIONS as exception:
        raise exception

    except SoftTimeLimitExceeded as exception:
        conversation = TextSearchConversation.objects.get(pk=conversation_id)
        TextSearchConversation.handle_celery_timeouts(
            conversation=conversation, result_uuid=result_uuid
        )
        raise exception

    except Exception as exception:
        logging.getLogger(settings.ERROR_LOGGER).exception('Failed to connect to OpenAI API!')
        conversation = TextSearchConversation.objects.get(id=conversation_id)
        query_result: TextSearchQueryResult = conversation.query_results.last()
        celery_task = query_result.celery_task
        celery_task.set_failed(str(exception))
        raise exception


# TODO: unit test
# Using bind=True sets the Celery Task object to the first argument, in this case celery_task.
@app.task(
    name='save_openai_results',
    bind=True,
    ignore_results=True,
    soft_time_limit=settings.CELERY_RESULT_STORE_SOFT_LIMIT,
)
def save_openai_results(
    celery_task: Task, results: dict, conversation_id: int, result_uuid: str
) -> None:
    try:
        conversation = TextSearchConversation.objects.get(id=conversation_id)
        result: TextSearchQueryResult = conversation.query_results.filter(uuid=result_uuid).first()
        result.save_results(results)
    except SoftTimeLimitExceeded as exception:
        conversation = TextSearchConversation.objects.get(pk=conversation_id)
        conversation.handle_celery_timeouts(
            conversation=conversation, result_uuid=result_uuid, exception=exception
        )
