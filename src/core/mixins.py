# pylint: disable=too-many-instance-attributes,too-many-arguments
# type: ignore


import logging
import uuid
from typing import Any, Dict, Iterable, List, Set, Tuple

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils.translation import gettext as _
from tiktoken import Encoding

from api.utilities.elastic import ElasticKNN
from api.utilities.gpt import ChatGPT
from api.utilities.vectorizer import Vectorizer
from core.choices import TASK_STATUS_CHOICES, TaskStatus
from core.models import CoreVariable
from core.utilities import exceeds_token_limit, prune_context


class ConversationMixin(models.Model):
    title = models.TextField(default='')
    auth_user = models.ForeignKey(User, on_delete=models.PROTECT)
    system_input = models.TextField()

    min_year = models.IntegerField(null=True, default=None)
    max_year = models.IntegerField(null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    is_deleted = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"'{self.title}' by {self.auth_user.username}"

    @staticmethod
    def format_gpt_question(user_input: str, context: str) -> str:
        missing_context = CoreVariable.get_core_setting('OPENAI_MISSING_CONTEXT_MESSAGE')
        prompt = CoreVariable.get_core_setting('OPENAI_OPENING_QUESTION')
        sources_text = CoreVariable.get_core_setting('OPENAI_SOURCES_TEXT')

        try:
            message = prompt.format(context, missing_context, user_input, sources_text)
        except ValueError:
            logging.getLogger(settings.ERROR_LOGGER).exception(
                'Could not format the OpenAI prompt!'
            )
            message = settings.GPT_SYSTEM_PROMPT_DEFAULT

        return message

    @staticmethod
    def prune_context(context: str, encoder: Encoding) -> Tuple[str, bool]:
        token_limit = CoreVariable.get_core_setting('OPENAI_CONTEXT_MAX_TOKEN_LIMIT')

        exceeds_limit = exceeds_token_limit(text=context, encoder=encoder, token_limit=token_limit)

        if exceeds_limit:
            pruned_context = prune_context(text=context, encoder=encoder, token_limit=token_limit)
            return pruned_context, True

        return context, False

    @staticmethod
    def parse_gpt_question_and_references(
        user_input: str, hits: List[dict], encoder: Encoding
    ) -> dict:
        url_field = CoreVariable.get_core_setting('ELASTICSEARCH_URL_FIELD')
        title_field = CoreVariable.get_core_setting('ELASTICSEARCH_TITLE_FIELD')
        text_field = CoreVariable.get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')
        year_field = CoreVariable.get_core_setting('ELASTICSEARCH_YEAR_FIELD')
        parent_field = CoreVariable.get_core_setting('ELASTICSEARCH_PARENT_FIELD')
        id_field = CoreVariable.get_core_setting('ELASTICSEARCH_ID_FIELD')

        context_documents_contents = []
        for hit in hits:
            source = dict(hit['_source'])
            content = source.get(text_field, '')
            content_id = source.get(id_field, '')
            reference = {
                'text': content,
                'elastic_id': hit['_id'],
                'id': content_id,
                'index': hit['_index'],
                'title': source.get(title_field, ''),
                'url': source.get(url_field, ''),
                'year': source.get(year_field, None),
                'parent': source.get(parent_field, ''),
            }
            if content:
                context_documents_contents.append(reference)

        is_pruned_container = []
        context_container = []
        for document in context_documents_contents:
            text, is_pruned = ConversationMixin.prune_context(
                document.get(text_field, ''), encoder=encoder
            )
            context_container.append(text)
            is_pruned_container.append(is_pruned)

        context_container = [
            f'{i}:\n{context_doc}' for i, context_doc in enumerate(context_container)
        ]
        context = '\n\n'.join(context_container)
        query_with_context = ConversationMixin.format_gpt_question(user_input, context)

        for reference in context_documents_contents:
            reference.pop('text', None)

        return {
            'context': query_with_context,
            'references': context_documents_contents,
            'is_context_pruned': any(is_pruned_container),
        }

    @staticmethod
    def handle_celery_timeouts(conversation: Any, result_uuid: str) -> None:
        logging.getLogger(settings.ERROR_LOGGER).exception('Celery task soft-time limit exceeded!')
        result = conversation.query_results.filter(uuid=result_uuid).first()
        message = _('Task toke too much time!')
        result.celery_task.set_failed(message)

    @property
    def messages(self) -> List[Dict[str, str]]:
        container = [{'role': 'system', 'content': self.system_input}]
        query = (
            self.query_results.filter(celery_task__status=TaskStatus.SUCCESS)
            .exclude(response=None)
            .order_by('created_at')
        )
        if query.exists():
            for query_result in query:
                container.extend(query_result.messages)
        return container

    def get_previous_results_parents_ids(self) -> Set[str]:
        success_messages = (
            self.query_results.filter(celery_task__status=TaskStatus.SUCCESS)
            .exclude(response=None)
            .order_by('created_at')
        )
        parents = set()

        if success_messages:
            latest_message = success_messages.first()
            references = latest_message.references
            for reference in references:
                parent_id = reference.get('parent', None)
                if parent_id:
                    parents.add(parent_id)

        return parents

    @property
    def messages_for_pdf(self) -> List[Dict[str, str]]:
        container = []
        query = (
            self.query_results.filter(celery_task__status=TaskStatus.SUCCESS)
            .exclude(response=None)
            .order_by('created_at')
        )
        if query.exists():
            for query_result in query:
                container.append(query_result.messages_for_pdf)
        return container

    @property
    def references_for_pdf(self) -> List[List[Dict[str, str]]]:
        container = []
        query = (
            self.query_results.filter(celery_task__status=TaskStatus.SUCCESS)
            .exclude(response=None)
            .order_by('created_at')
        )
        if query.exists():
            for query_result in query:
                container.append(query_result.references)
        return container

    def generate_conversations_and_references(
        self,
        user_input: str,
        dataset_index_queries: List[str],
        vectorizer: Vectorizer,
        encoder: Encoding,
        parent_references: Iterable[str],
        task: Any,
    ) -> dict:
        try:
            input_vector = vectorizer.vectorize([user_input])['vectors'][0]

            knn = ElasticKNN()

            date_query = knn.create_date_query(min_year=self.min_year, max_year=self.max_year)
            search_query = knn.create_doc_id_query(date_query, parent_references)
            search_query_wrapper = {'search_query': search_query} if search_query else {}
            matching_documents = knn.search_vector(
                vector=input_vector, indices=dataset_index_queries, **search_query_wrapper
            )

            hits = matching_documents['hits']['hits']
            question_and_references = self.parse_gpt_question_and_references(
                user_input=user_input, hits=hits, encoder=encoder
            )
            return question_and_references
        except Exception as exception:
            logging.getLogger(settings.ERROR_LOGGER).exception(
                'Failed to search vectors for context!'
            )
            message = _("Couldn't get context from Elasticsearch!")
            task.set_failed(message)
            raise exception

    class Meta:
        abstract = True


class ResultMixin(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    model = models.CharField(max_length=100, null=True, default=None)

    user_input = models.TextField(null=True, default=None)
    response = models.TextField(null=True, default=None)

    is_context_pruned = models.BooleanField(default=False)

    input_tokens = models.PositiveIntegerField(null=True, default=None)
    output_tokens = models.PositiveIntegerField(null=True, default=None)
    total_cost = models.FloatField(null=True, default=None)

    response_headers = models.JSONField(null=True, default=None)
    references = models.JSONField(null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True)

    def commit_search(self, task, context_and_references: dict, user_input: str) -> dict:
        task.set_started()

        user_input_with_context = context_and_references['context']
        references = context_and_references['references']
        is_context_pruned = context_and_references['is_context_pruned']

        messages = self.conversation.messages + [
            {'role': 'user', 'content': user_input_with_context}
        ]

        chat_gpt = ChatGPT()
        llm_response = chat_gpt.chat(messages=messages)

        gpt_references = llm_response.used_references

        # Adds binary field 'used_by_gpt'
        for index, reference in enumerate(references):
            if index in gpt_references:
                reference['used_by_gpt'] = True
            else:
                reference['used_by_gpt'] = False

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

    def save_results(self, results: dict) -> None:
        try:
            self.model = results['model']
            self.user_input = results['user_input']
            self.is_context_pruned = results['is_context_pruned']
            self.response = results['response']
            self.input_tokens = results['input_tokens']
            self.output_tokens = results['output_tokens']
            self.total_cost = results['total_cost']
            self.response_headers = results['response_headers']
            self.references = results['references']
            self.save()

            self.celery_task.set_success()

        except Exception as exception:
            logging.getLogger(settings.ERROR_LOGGER).exception("Couldn't store database results!")
            message = _("Couldn't store ChatGPT results!")
            self.celery_task.set_failed(message)
            raise exception

    @property
    def messages(self) -> List[Dict[str, str]]:
        return [
            {'role': 'user', 'content': self.user_input},
            {'role': 'assistant', 'content': self.response},
        ]

    @property
    def messages_for_pdf(self) -> Dict[str, str]:
        return {
            'user': self.user_input,
            'assistant': self.response,
        }

    class Meta:
        abstract = True


class TaskMixin(models.Model):
    status = models.CharField(
        choices=TASK_STATUS_CHOICES, max_length=50, default=TaskStatus.PENDING
    )
    error = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def set_success(self) -> None:
        self.status = TaskStatus.SUCCESS
        self.save()

    def set_failed(self, error: str) -> None:
        self.status = TaskStatus.FAILURE
        self.error = error
        self.save()

    def set_started(self) -> None:
        self.status = TaskStatus.STARTED
        self.save()

    def __str__(self) -> str:
        return f'Task {self.status} @ {self.modified_at}'

    class Meta:
        abstract = True
