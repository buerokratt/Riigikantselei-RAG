from rest_framework import serializers
from rest_framework.authtoken.admin import User

from document_search.models import DocumentSearchConversation, DocumentSearchQueryResult, DocumentTask, DocumentAggregationResult
from text_search.serializers import TaskSerializer


class DocumentSearchQueryResultSerializer(serializers.ModelSerializer):
    title = serializers.CharField(default='', help_text="Display value for history, no need to fill this as it's automatically set")
    celery_task = TaskSerializer(read_only=True, many=False)

    class Meta:
        model = DocumentSearchQueryResult
        fields = (
            'id',
            'uuid',
            'title',
            'user_input',
            'response',
            'input_tokens',
            'output_tokens',
            'total_cost',
            'celery_task',
            'references',
            'created_at'
        )


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTask
        fields = ('status', 'error', 'created_at', 'modified_at')
        read_only_fields = ('__all__',)


class DocumentSearchChatSerializer(serializers.Serializer):
    index = serializers.CharField()


class AggregationTaskSerializer(serializers.ModelSerializer):
    celery_task = TaskSerializer(read_only=True)

    class Meta:
        model = DocumentAggregationResult
        fields = (
            'id',
            'aggregations',
            'celery_task',
        )


class DocumentSearchConversationSerializer(serializers.ModelSerializer):
    system_input = serializers.CharField(default=None)
    auth_user = serializers.SerializerMethodField()
    query_results = DocumentSearchQueryResultSerializer(many=True, read_only=True)
    aggregation_result = AggregationTaskSerializer(read_only=True)

    def get_auth_user(self, obj):
        user = User.objects.get(pk=obj.auth_user.id)
        return {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name
        }

    class Meta:
        fields = '__all__'
        read_only_fields = ('auth_user', 'query_results', 'aggregation_result', 'created_at', 'modified_at')
        model = DocumentSearchConversation
