import uuid
from typing import List

from django.contrib.auth.models import User
from django.db import models

from core.choices import TASK_STATUS_CHOICES, TaskStatus


class CoreVariable(models.Model):
    name = models.CharField(max_length=100)
    value = models.TextField(default=None, null=True)

    def __str__(self) -> str:
        return f'{self.name} - {self.value}'


class Dataset(models.Model):
    # Name of the dataset, for example 'Riigi teataja'
    name = models.CharField(max_length=100, unique=True)
    # Type of dataset, for example 'Arengukava'
    type = models.CharField(max_length=100)
    # Elasticsearch wildcard string describing names of all indexes used by this dataset.
    # For example, to cover 'riigiteataja_1' and 'riigiteataja_2', use 'riigiteataja_*'.
    index_query = models.CharField(max_length=100)
    # Description of dataset contents
    description = models.TextField(default='')

    def __str__(self) -> str:
        return f'{self.name} ({self.type})'


class ConversationMixin(models.Model):
    title = models.CharField(max_length=100)
    auth_user = models.ForeignKey(User, on_delete=models.RESTRICT)
    system_input = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"'{self.title}' by {self.auth_user.username}"

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

    class Meta:
        abstract = True


class ResultMixin(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

    model = models.CharField(max_length=100, null=True, default=None)

    user_input = models.TextField(null=True, default=None)
    response = models.TextField(null=True, default=None)

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
