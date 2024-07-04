from typing import List, Optional

from django.contrib.auth.models import User
from django.db import models

from core.choices import TASK_STATUS_CHOICES, TaskStatus


class CoreVariable(models.Model):
    name = models.CharField(max_length=100)
    value = models.TextField(default=None, null=True)

    def __str__(self) -> str:
        return f'{self.name} - {self.value}'


class TextSearchConversation(models.Model):
    auth_user = models.ForeignKey(User, on_delete=models.RESTRICT)
    system_input = models.TextField()
    title = models.CharField(max_length=100)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def messages(self) -> List[dict]:
        container = [{'role': 'system', 'content': self.system_input}]
        query = (
            self.query_results.filter(celery_task__status=TaskStatus.SUCCESS)
            .exclude(user_input=None)
            .order_by('created_at')
        )
        if query.exists():
            for query_result in query:
                container.extend(query_result.messages)
        return container


class TextSearchQueryResult(models.Model):
    conversation = models.ForeignKey(
        TextSearchConversation, on_delete=models.CASCADE, related_name='query_results'
    )

    model = models.CharField(max_length=100, null=True, default=None)

    min_year = models.IntegerField(null=True, default=None)
    max_year = models.IntegerField(null=True, default=None)
    document_types_string = models.TextField(null=True, default=None)

    user_input = models.TextField(null=True, default=None)
    response = models.TextField(null=True, default=None)

    input_tokens = models.PositiveIntegerField(null=True, default=None)
    output_tokens = models.PositiveIntegerField(null=True, default=None)
    total_cost = models.FloatField(null=True, default=None)

    response_headers = models.JSONField(null=True, default=None)

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def messages(self) -> List[dict]:
        return [
            {'role': 'user', 'content': self.user_input},
            {'role': 'assistant', 'content': self.response},
        ]

    @property
    def document_types(self) -> Optional[List[str]]:
        if self.document_types_string:
            return self.document_types_string.split(',')

        return None

    def __str__(self) -> str:
        return f"'{self.conversation.title.title()}' @ {self.conversation.auth_user.username}"


class Task(models.Model):
    status = models.CharField(
        choices=TASK_STATUS_CHOICES, max_length=50, default=TaskStatus.PENDING
    )
    error = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    modified_at = models.DateTimeField(auto_now=True)

    result = models.OneToOneField(
        TextSearchQueryResult, on_delete=models.CASCADE, related_name='celery_task'
    )

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
