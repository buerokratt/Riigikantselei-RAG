from typing import List

from django.contrib.auth.models import User
from django.db import models


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
        if self.query_results.exists():
            for query_result in self.query_results.order_by('created_at'):
                container.extend(query_result.messages)
        return container


class TextSearchQueryResult(models.Model):
    conversation = models.ForeignKey(
        TextSearchConversation, on_delete=models.CASCADE, related_name='query_results'
    )
    model = models.CharField(max_length=100)

    min_year = models.IntegerField()
    max_year = models.IntegerField()
    document_types_string = models.TextField()

    user_input = models.TextField()
    response = models.TextField()

    input_tokens = models.IntegerField()
    output_tokens = models.IntegerField()
    total_cost = models.FloatField()

    response_headers = models.JSONField()

    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def messages(self) -> List[dict]:
        return [
            {'role': 'user', 'content': self.user_input},
            {'role': 'assistant', 'content': self.response},
        ]

    @property
    def document_types(self) -> List[str]:
        return self.document_types_string.split(',')
