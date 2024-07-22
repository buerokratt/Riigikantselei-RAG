from typing import List, Optional

from django.db import models

from core.mixins import ConversationMixin, ResultMixin, TaskMixin


class TextSearchConversation(ConversationMixin):
    dataset_names_string = models.TextField(null=True, default=None)

    @property
    def dataset_names(self) -> Optional[List[str]]:
        if self.dataset_names_string:
            return self.dataset_names_string.split(',')

        return None


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
