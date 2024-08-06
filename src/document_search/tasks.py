import logging
from typing import List

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils.translation import gettext as _

from api.celery_handler import app
from api.utilities.elastic import ElasticKNN
from api.utilities.gpt import ChatGPT
from core.base_task import ResourceTask
from core.exceptions import OPENAI_EXCEPTIONS
from core.models import Dataset
from document_search.models import (
    DocumentAggregationResult,
    DocumentSearchConversation,
    DocumentSearchQueryResult,
)
from document_search.utilities import parse_aggregation


# pylint: disable=unused-argument,too-many-arguments

# TODO: this file and its text_search sibling
#  differ in unnecessary ways (code that does the same thing is written differently)
#  and is way too similar in other ways (duplicated code).
#  Unify the unnecessarily different code and then refactor all shared code out.
#  Otherwise we will end up with different behaviour between workflows
#  and bugs will happen more easily.


# TODO: unit test
# Using bind=True sets the Celery Task object to the first argument, in this case celery_task.
@app.task(
    name='generate_aggregations',
    bind=True,
    base=ResourceTask,
    soft_task_limit=settings.CELERY_AGGREGATE_TASK_SOFT_LIMIT,
)
def generate_aggregations(
        celery_task: ResourceTask, conversation_id: int, user_input: str, result_uuid: str
) -> None:
    try:
        conversation = DocumentSearchConversation.objects.get(pk=conversation_id)
        aggregation_result = DocumentAggregationResult.objects.get(
            uuid=result_uuid, conversation=conversation
        )
        task = aggregation_result.celery_task
        task.set_started()

        knn = ElasticKNN()
        indices = Dataset.get_all_dataset_values('index')

        question_vector = celery_task.vectorizer.vectorize([user_input])['vectors'][0]
        output_count = 100
        hits = knn.search_vector(
            vector=question_vector,
            k=output_count,
            num_candidates=500,
            size=output_count,
            indices=indices,
        ).to_dict()

        hits = hits['hits']['hits']
        aggregations = parse_aggregation(hits)
        aggregation_result.aggregations = aggregations
        aggregation_result.save()

        task.set_success()

    except SoftTimeLimitExceeded as exception:
        conversation = DocumentSearchConversation.objects.get(pk=conversation_id)
        DocumentSearchConversation.handle_celery_timeouts(
            conversation=conversation, result_uuid=result_uuid
        )
        raise exception

    except Exception as exception:
        logging.getLogger(settings.ERROR_LOGGER).exception('Failed to fetch aggregations!')
        conversation = DocumentSearchConversation.objects.get(id=conversation_id)
        aggregation_result = conversation.aggregation_result
        celery_task = aggregation_result.celery_task
        celery_task.set_failed(str(exception))
        raise exception


# TODO: implement real RAG logic, then unit test
# Using bind=True sets the Celery Task object to the first argument, in this case celery_task.
@app.task(
    name='generate_openai_prompt',
    bind=True,
    base=ResourceTask,
    soft_time_limit=settings.CELERY_VECTOR_SEARCH_SOFT_LIMIT,
)
def generate_openai_prompt(
        celery_task: ResourceTask,
        result_uuid: str,
        conversation_id: int,
        dataset_index_queries: List[str],
) -> dict:
    try:
        conversation = DocumentSearchConversation.objects.get(pk=conversation_id)
        task = conversation.query_results.filter(uuid=result_uuid).first()
        user_input = conversation.user_input
        parents = conversation.get_previous_results_parents_ids()
        context_and_references = conversation.generate_conversations_and_references(
            user_input=user_input,
            dataset_index_queries=dataset_index_queries,
            vectorizer=celery_task.vectorizer,
            encoder=celery_task.encoder,
            parent_references=parents,
            task=task.celery_task
        )
        return context_and_references

    except SoftTimeLimitExceeded as exception:
        conversation = DocumentSearchConversation.objects.get(pk=conversation_id)
        DocumentSearchConversation.handle_celery_timeouts(
            conversation=conversation, result_uuid=result_uuid
        )
        raise exception


# TODO: unit test, mocking like in test_openai_components.py
# Using bind=True sets the Celery Task object to the first argument, in this case celery_task.
@app.task(
    name='send_document_search',
    autoretry_for=OPENAI_EXCEPTIONS,
    max_retries=10,
    soft_time_limit=settings.CELERY_OPENAI_SOFT_LIMIT,
    bind=True,
)
def send_document_search(
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
        conversation = DocumentSearchConversation.objects.get(id=conversation_id)
        result = conversation.query_results.filter(uuid=result_uuid).first()
        document_task = result.celery_task

        document_task.set_started()

        user_input_with_context = context_and_references['context']
        references = context_and_references['references']
        is_pruned = context_and_references['is_context_pruned']

        messages = conversation.messages + [{'role': 'user', 'content': user_input_with_context}]

        chat_gpt = ChatGPT()
        llm_response = chat_gpt.chat(messages=messages)

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
            'is_context_pruned': is_pruned,
        }

    # Reraise these since they'd be necessary for a retry.
    except OPENAI_EXCEPTIONS as exception:
        raise exception

    except SoftTimeLimitExceeded as exception:
        conversation = DocumentSearchConversation.objects.get(pk=conversation_id)
        DocumentSearchConversation.handle_celery_timeouts(
            conversation=conversation, result_uuid=result_uuid
        )
        raise exception
    except Exception as exception:
        logging.getLogger(settings.ERROR_LOGGER).exception('Failed to connect to OpenAI API!')
        conversation = DocumentSearchConversation.objects.get(id=conversation_id)
        query_result = conversation.query_results.last()
        celery_task = query_result.celery_task
        message = _("Unknown error, couldn't handle response from ChatGPT!")
        celery_task.set_failed(message)
        raise exception


# TODO: unit test
# Using bind=True sets the Celery Task object to the first argument, in this case celery_task.
@app.task(
    name='save_openai_results_for_doc',
    bind=True,
    ignore_results=True,
    soft_time_limit=settings.CELERY_RESULT_STORE_SOFT_LIMIT,
)
def save_openai_results_for_doc(
        celery_task: Task, results: dict, conversation_id: int, result_uuid: str, dataset_name: str
) -> None:
    try:
        conversation = DocumentSearchConversation.objects.get(id=conversation_id)
        result: DocumentSearchQueryResult = conversation.query_results.filter(
            uuid=result_uuid
        ).first()
        result.save_results(results)
    except SoftTimeLimitExceeded as exception:
        conversation = DocumentSearchConversation.objects.get(pk=conversation_id)
        DocumentSearchConversation.handle_celery_timeouts(
            conversation=conversation, result_uuid=result_uuid
        )
        raise exception
