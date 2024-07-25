import logging
import uuid
from typing import List, Tuple

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from tiktoken import Encoding

from api.utilities.elastic import ElasticKNN
from api.utilities.vectorizer import Vectorizer
from core.choices import TASK_STATUS_CHOICES, TaskStatus
from core.models import CoreVariable
from core.utilities import exceeds_token_limit, prune_context


class ConversationMixin(models.Model):
    title = models.CharField(max_length=100)
    auth_user = models.ForeignKey(User, on_delete=models.RESTRICT)
    system_input = models.TextField()

    min_year = models.IntegerField(null=True, default=None)
    max_year = models.IntegerField(null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"'{self.title}' by {self.auth_user.username}"

    @staticmethod
    def format_gpt_question(user_input: str, context: str) -> str:
        missing_context = CoreVariable.get_core_setting('OPENAI_MISSING_CONTEXT_MESSAGE')
        prompt = CoreVariable.get_core_setting('OPENAI_OPENING_QUESTION')

        try:
            message = prompt.format(context, missing_context, user_input)
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

        context_documents_contents = []
        for hit in hits:
            source = dict(hit['_source'])
            content = source.get(text_field, '')
            reference = {
                'text': content,
                'elastic_id': hit['_id'],
                'index': hit['_index'],
                'title': source.get(title_field, ''),
                'url': source.get(url_field, ''),
                'year': source.get(year_field, ''),
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

        context = '\n\n'.join(context_container)
        query_with_context = ConversationMixin.format_gpt_question(user_input, context)

        for reference in context_documents_contents:
            reference.pop('text', None)

        return {
            'context': query_with_context,
            'references': context_documents_contents,
            'is_context_pruned': any(is_pruned_container),
        }

    @property
    def messages(self) -> List[dict]:
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

    def generate_conversations_and_references(
        self,
        user_input: str,
        dataset_index_queries: List[str],
        vectorizer: Vectorizer,
        encoder: Encoding,
    ) -> dict:
        input_vector = vectorizer.vectorize([user_input])['vectors'][0]

        knn = ElasticKNN()

        search_query = knn.create_date_query(min_year=self.min_year, max_year=self.max_year)
        search_query_wrapper = {'search_query': search_query} if search_query else {}
        matching_documents = knn.search_vector(
            vector=input_vector, indices=dataset_index_queries, **search_query_wrapper
        )

        hits = matching_documents['hits']['hits']
        question_and_references = self.parse_gpt_question_and_references(
            user_input=user_input, hits=hits, encoder=encoder
        )
        return question_and_references

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

    @property
    def messages(self) -> List[dict]:
        return [
            {'role': 'user', 'content': self.user_input},
            {'role': 'assistant', 'content': self.response},
        ]

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
