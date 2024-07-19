import uuid

from django.db import models

from core.models import ConversationMixin, ResultMixin, TaskMixin


# Create your models here.
class DocumentSearchConversation(ConversationMixin):
    user_input = models.TextField()
    title = models.CharField(max_length=100, default='')


class DocumentSearchQueryResult(ResultMixin):
    dataset_name = models.TextField(null=True, default=None)
    conversation = models.ForeignKey(
        DocumentSearchConversation, on_delete=models.CASCADE, related_name='query_results'
    )


class DocumentAggregationResult(models.Model):
    conversation = models.OneToOneField(
        DocumentSearchConversation, on_delete=models.CASCADE, related_name='aggregation_result'
    )
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    aggregations = models.JSONField(default=list)


class AggregationTask(TaskMixin):
    result = models.OneToOneField(
        DocumentAggregationResult, on_delete=models.CASCADE, related_name='celery_task'
    )


class DocumentTask(TaskMixin):
    result = models.OneToOneField(
        DocumentSearchQueryResult, on_delete=models.CASCADE, related_name='celery_task'
    )
