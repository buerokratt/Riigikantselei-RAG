import logging
from typing import List

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings
from django.utils.translation import gettext as _

from api.celery_handler import app
from api.utilities.elastic import ElasticKNN
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
            task=task.celery_task,
        )
        return context_and_references

    except SoftTimeLimitExceeded as exception:
        conversation = DocumentSearchConversation.objects.get(pk=conversation_id)
        DocumentSearchConversation.handle_celery_timeouts(
            conversation=conversation, result_uuid=result_uuid
        )
        raise exception


# Using bind=True sets the Celery Task object to the first argument, in this case celery_task.
@app.task(
    name='send_document_search',
    autoretry_for=OPENAI_EXCEPTIONS,
    retry_backoff=1,
    retry_jitter=True,
    retry_backoff_max=5*60,
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
        task = result.celery_task

        api_results = result.commit_search(
            task=task, context_and_references=context_and_references, user_input=user_input
        )

        return api_results

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
