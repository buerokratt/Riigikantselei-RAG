import logging
from typing import List

import openai
from celery import Task
from django.conf import settings
from django.db.models import F

from api.celery_handler import app
from api.utilities.core_settings import get_core_setting
from api.utilities.elastic import ElasticKNN
from api.utilities.gpt import ChatGPT
from api.utilities.vectorizer import Vectorizer
from core.models import TextSearchConversation, TextSearchQueryResult, DocumentSearchConversation
from .models import Task as TaskModel
from .utilities import parse_hits_as_references

# pylint: disable=unused-argument,too-many-arguments

# TODO: Revisit the retry parameters, or do it by hand,
#   probably using the headers information about timeout expirations would be useful.


OPENAI_EXCEPTIONS = (
    openai.InternalServerError,
    openai.RateLimitError,
    openai.UnprocessableEntityError,
    openai.APITimeoutError,
)


def async_call_celery_task_chain(
        min_year: int,
        max_year: int,
        user_input: str,
        document_indices: List[str],
        conversation_id: int,
        document_types_string: str,
        result_uuid: str,
) -> None:
    rag_task = query_and_format_rag_context.s(
        min_year=min_year,
        max_year=max_year,
        user_input=user_input,
        document_indices=document_indices,
    )
    openai_task = call_openai_api.s(
        conversation_id=conversation_id,
        min_year=min_year,
        max_year=max_year,
        document_types_string=document_types_string,
        user_input=user_input,
        result_uuid=result_uuid,
    )
    save_task = save_openai_results.s(conversation_id, result_uuid)

    (rag_task | openai_task | save_task).apply_async()


@app.task(name='query_and_format_rag_context', max_retries=5, bind=True)
def query_and_format_rag_context(
        self: Task, min_year: int, max_year: int, user_input: str, document_indices: List[str]
) -> dict:
    """
    Task for fetching the RAG context from pre-processed vectors in ElasticSearch.

    :param self: Contains access to the Celery Task instance.
    :param min_year: Earliest year to consider documents from.
    :param max_year: Latest year to consider documents from.
    :param user_input: User sent input to add context to.
    :param document_indices: Which indices to search from Elasticsearch.
    :return: Text containing user input and relevant context documents.
    """
    # Load important variables
    data_url_key = get_core_setting('ELASTICSEARCH_URL_FIELD')
    data_title_key = get_core_setting('ELASTICSEARCH_TITLE_FIELD')
    data_content_key = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')

    vectorizer = Vectorizer(
        model_name=settings.VECTORIZATION_MODEL_NAME,
        system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
        inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
        model_directory=settings.DATA_DIR,
    )
    input_vector = vectorizer.vectorize([user_input])['vectors'][0]

    indices_string = ','.join(document_indices)
    elastic_knn = ElasticKNN(indices=indices_string)

    search_query = ElasticKNN.create_date_query(min_year=min_year, max_year=max_year)
    search_query = {'search_query': search_query} if search_query else {}
    matching_documents = elastic_knn.search_vector(vector=input_vector, **search_query)

    hits = matching_documents['hits']['hits']
    question_and_reference = parse_hits_as_references(hits, data_content_key, data_url_key, data_title_key, user_input)
    return question_and_reference


# Using bind sets the Celery Task object to the first argument, in this case self.
@app.task(
    name='call_openai_api',
    autoretry_for=OPENAI_EXCEPTIONS,
    max_retries=10,
    bind=True,
)
def call_openai_api(
        self: Task,
        context_and_references: dict,
        conversation_id: int,
        min_year: int,
        max_year: int,
        document_types_string: str,
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
        data_content_key = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')

        conversation = TextSearchConversation.objects.get(id=conversation_id)
        result: TextSearchQueryResult = conversation.query_results.filter(uuid=result_uuid).first()
        task: TaskModel = result.celery_task

        task.set_started()

        user_input_with_context = context_and_references['context']
        references = context_and_references['references']

        # Remove content from the references since we don't
        # want to keep all that text in the database.
        for reference in references:
            reference.pop(data_content_key)

        messages = conversation.messages + [{'role': 'user', 'content': user_input_with_context}]

        chat_gpt = ChatGPT()
        llm_response = chat_gpt.chat(messages=messages)

        # The output is a dict of all the input data needed to create a TextSearchQueryResult.
        # To separate testing of view and model logic from testing of RAG logic,
        # the TextSearchQueryResult is created in the view.
        return {
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
            'references': references,
        }

    # Reraise these since they'd be necessary for a retry.
    except OPENAI_EXCEPTIONS as exception:
        raise exception

    except Exception as exception:
        logging.getLogger(settings.ERROR_LOGGER).exception('Failed to connect to OpenAI API!')
        conversation = TextSearchConversation.objects.get(id=conversation_id)
        query_result: TextSearchQueryResult = conversation.query_results.last()
        celery_task: TaskModel = query_result.celery_task
        celery_task.set_failed(str(exception))
        raise exception


@app.task(name='save_openai_results', bind=True, ignore_results=True)
def save_openai_results(self: Task, results: dict, conversation_id: int, result_uuid: str) -> None:
    conversation = TextSearchConversation.objects.get(id=conversation_id)
    result: TextSearchQueryResult = conversation.query_results.filter(uuid=result_uuid).first()
    task: TaskModel = result.celery_task

    result.model = results['model']
    result.min_year = results['min_year']
    result.max_year = results['max_year']
    result.document_types_string = results['document_types_string']
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


@app.task(name='vectorize_and_aggregate', bind=True, ignore_results=True)
def vectorize_and_aggregate(self, conversation_id: int, vector_field, document_type_field: str, year_field: str) -> None:
    conversation = DocumentSearchConversation.objects.get(id=conversation_id)

    knn = ElasticKNN(conversation.indices, field=vector_field)

    vectorizer = Vectorizer(
        model_name=settings.VECTORIZATION_MODEL_NAME,
        system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
        inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
        model_directory=settings.DATA_DIR,
    )

    question_vector = vectorizer.vectorize([conversation.user_input])["vectors"][0]

    aggregates = knn.knn_filter_and_aggregate(
        document_type_field=document_type_field,
        year_field=year_field,
        vector=question_vector,
        search_query=None,
        num_candidates=20,
        k=20
    )

    conversation.aggregations = aggregates
    conversation.save()


@app.task(name='generate_doc_search_context', bind=True)
def generate_doc_search_context(self, conversation_id: int, document_type: str) -> dict:
    text_field = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')
    document_type_field = get_core_setting('ELASTICSEARCH_DOCUMENT_TYPE_FIELD')
    year_field = get_core_setting('ELASTICSEARCH_YEAR_FIELD')
    data_url_key = get_core_setting('ELASTICSEARCH_URL_FIELD')
    vector_field = get_core_setting('ELASTICSEARCH_VECTOR_FIELD')
    title_field = get_core_setting('ELASTICSEARCH_TITLE_FIELD')

    instance: DocumentSearchConversation = DocumentSearchConversation.objects.get(pk=conversation_id)

    knn = ElasticKNN(indices=instance.indices, field=vector_field)
    vectorizer = Vectorizer(
        model_name=settings.VECTORIZATION_MODEL_NAME,
        system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
        inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
        model_directory=settings.DATA_DIR,
    )
    question_vector = vectorizer.vectorize([instance.user_input])["vectors"][0]
    year_and_type_filter = knn.year_and_type_filter(
        year_field,
        document_type_field,
        document_type,
        instance.min_year,
        instance.max_year,
    )

    search = knn.generate_knn_with_filter(
        search_query=year_and_type_filter,
        vector=question_vector
    )

    hits = search.execute()['hits']['hits']
    question_and_reference = parse_hits_as_references(hits, text_field, data_url_key, title_field, instance.user_input)
    return question_and_reference
