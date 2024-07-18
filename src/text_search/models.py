from django.db import models

from core.models import ConversationMixin, ResultMixin, TaskMixin


class TextSearchConversation(ConversationMixin):
    indices = models.JSONField(null=True, default=None)

    min_year = models.IntegerField(null=True, default=None)
    max_year = models.IntegerField(null=True, default=None)


class TextSearchQueryResult(ResultMixin):
    conversation = models.ForeignKey(
        TextSearchConversation, on_delete=models.CASCADE, related_name='query_results'
    )

    def __str__(self) -> str:
        return f"'{self.conversation.title.title()}' @ {self.conversation.auth_user.username}"


class TextTask(TaskMixin):
    result = models.OneToOneField(
        TextSearchQueryResult, on_delete=models.CASCADE, related_name='celery_task'
    )
