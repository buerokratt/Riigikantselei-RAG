import logging

from celery import Task
from django.conf import settings
from django.db.models import F

from api.celery_handler import app
from api.utilities.core_settings import get_core_setting
from api.utilities.elastic import ElasticKNN
from api.utilities.gpt import ChatGPT
from api.utilities.vectorizer import Vectorizer
from core.exceptions import OPENAI_EXCEPTIONS
from core.utilities import parse_gpt_question_and_references
from document_search.models import DocumentSearchConversation, DocumentSearchQueryResult, DocumentTask, DocumentAggregationResult, AggregationTask


@app.task(name="generate_aggregations", bind=True)
def generate_aggregations(self, conversation_id: int, user_input: str, result_uuid: str):
    try:
        aggregations = {}
        response = []

        conversation: DocumentSearchConversation = DocumentSearchConversation.objects.get(pk=conversation_id)
        aggregation_result: DocumentAggregationResult = DocumentAggregationResult.objects.get(uuid=result_uuid, conversation=conversation)
        task = aggregation_result.celery_task

        task.set_started()

        knn = ElasticKNN(indices='*')  # TODO: Change when the index system is ready.
        year_field = get_core_setting('ELASTICSEARCH_YEAR_FIELD')

        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )

        question_vector = vectorizer.vectorize([user_input])['vectors'][0]
        output_count = 100
        hits = knn.search_vector(
            vector=question_vector,
            num_candidates=500,
            k=output_count,
            source=[year_field],
            size=output_count
        )

        for hit in hits:
            index = hit.meta.index
            year = getattr(hit, year_field)
            if index not in aggregations:
                aggregations[index] = [year]
            else:
                aggregations[index].append(year)

        for index, years in aggregations.items():
            response.append(
                {
                    'index': index,
                    'min_year': min(years),
                    'max_year': max(years),
                    'count': len(years)
                }
            )

        aggregation_result.aggregations = response
        aggregation_result.save()

        task.set_success()

    except Exception as exception:
        logging.getLogger(settings.ERROR_LOGGER).exception('Failed to fetch aggregations!')
        conversation = DocumentSearchConversation.objects.get(id=conversation_id)
        aggregation_result: DocumentAggregationResult = conversation.aggregation_result
        celery_task: AggregationTask = aggregation_result.celery_task
        celery_task.set_failed(str(exception))
        raise exception


@app.task(name="generate_openeai_prompt", bind=True)
def generate_openeai_prompt(self, conversation_id: int, index: str):
    conversation = DocumentSearchConversation.objects.get(pk=conversation_id)
    knn = ElasticKNN(indices=index)

    vectorizer = Vectorizer(
        model_name=settings.VECTORIZATION_MODEL_NAME,
        system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
        inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
        model_directory=settings.DATA_DIR,
    )

    question_vector = vectorizer.vectorize([conversation.user_input])['vectors'][0]

    response = knn.search_vector(
        vector=question_vector,
    )

    hits = response['hits']['hits']
    context_and_references = parse_gpt_question_and_references(user_input=conversation.user_input, hits=hits)
    return context_and_references


@app.task(
    name='send_document_search',
    autoretry_for=OPENAI_EXCEPTIONS,
    max_retries=10,
    bind=True,
)
def send_document_search(
        self: Task,
        context_and_references: dict,
        conversation_id: int,
        user_input: str,
        result_uuid: str,
) -> dict:
    """
    Task for fetching the RAG context from pre-processed vectors in ElasticSearch.

    :param context_and_references: Text containing user input and relevant context documents.
    :param self: Contains access to the Celery Task instance.
    :param conversation_id: ID of the conversation this API call is a part of.
    :param min_year: Earliest year to consider documents from.
    :param max_year: Latest year to consider documents from.
    :param document_types_string: Which indices to search from Elasticsearch.
    :param user_input: User sent input to send to the LLM.
    :return: Dict needed to build a TextSearchQueryResult.
    """
    try:
        conversation = DocumentSearchConversation.objects.get(id=conversation_id)
        result: DocumentSearchQueryResult = conversation.query_results.filter(uuid=result_uuid).first()
        task: DocumentTask = result.celery_task

        task.set_started()

        user_input_with_context = context_and_references['context']
        references = context_and_references['references']

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
        }

    # Reraise these since they'd be necessary for a retry.
    except OPENAI_EXCEPTIONS as exception:
        raise exception

    except Exception as exception:
        logging.getLogger(settings.ERROR_LOGGER).exception('Failed to connect to OpenAI API!')
        conversation = DocumentSearchConversation.objects.get(id=conversation_id)
        query_result: DocumentSearchQueryResult = conversation.query_results.last()
        celery_task: DocumentTask = query_result.celery_task
        celery_task.set_failed(str(exception))
        raise exception


@app.task(name='save_openai_results_for_doc', bind=True, ignore_results=True)
def save_openai_results_for_doc(self: Task, results: dict, conversation_id: int, result_uuid: str) -> None:
    conversation = DocumentSearchConversation.objects.get(id=conversation_id)
    result: DocumentSearchQueryResult = conversation.query_results.filter(uuid=result_uuid).first()
    task: DocumentTask = result.celery_task

    result.model = results['model']
    result.user_input = results['user_input']
    result.response = results['response']
    result.input_tokens = results['input_tokens']
    result.output_tokens = results['output_tokens']
    result.total_cost = results['total_cost']
    result.response_headers = results['response_headers']
    result.references = results['references']
    result.save()

    # Increment the counter for cost in the user profile to prevent
    # it from lowering when deleting old records. Issue #23
    user = conversation.auth_user
    user.user_profile.used_cost = F('used_cost') + results['total_cost']
    user.user_profile.save(update_fields=['used_cost'])

    task.set_success()
