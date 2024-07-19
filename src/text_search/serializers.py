from django.db import transaction
from rest_framework import serializers

from api.utilities.core_settings import get_core_setting
from api.utilities.serializers import reasonable_character_with_spaces_validator
from core.models import Dataset
from core.utilities import (
    get_all_dataset_values,
    validate_dataset_names,
    validate_min_max_years,
)
from text_search.models import TextSearchConversation, TextSearchQueryResult, TextTask
from text_search.tasks import async_call_celery_task_chain


class TextSearchConversationCreateSerializer(serializers.Serializer):
    user_input = serializers.CharField()

    min_year = serializers.IntegerField(default=None, min_value=1700)
    max_year = serializers.IntegerField(default=None, min_value=1700)
    dataset_names = serializers.ListField(
        # By default include all datasets.
        default=get_all_dataset_values,
        child=serializers.CharField(),
    )

    def validate(self, data: dict) -> dict:
        validate_min_max_years(data['min_year'], data['max_year'])

        validate_dataset_names(data['dataset_names'])

        return data

    def create(self, validated_data: dict) -> TextSearchConversation:
        min_year = self.validated_data['min_year']
        max_year = self.validated_data['max_year']
        dataset_names_string = ','.join(self.validated_data['dataset_names'])

        conversation = TextSearchConversation.objects.create(
            auth_user=validated_data['auth_user'],
            system_input=get_core_setting('OPENAI_SYSTEM_MESSAGE'),
            title=validated_data['user_input'],
            dataset_names_string=dataset_names_string,
            min_year=min_year,
            max_year=max_year,
        )
        conversation.save()
        return conversation


# Objects are never modified through views, so the serializer is used only for reading
class TextTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextTask
        fields = ('status', 'error', 'created_at', 'modified_at')
        read_only_fields = ('__all__',)


# Objects are never modified, so the serializer is used only for reading
class TextSearchQueryResultReadOnlySerializer(serializers.ModelSerializer):
    celery_task = TextTaskSerializer(read_only=True, many=False)

    class Meta:
        model = TextSearchQueryResult
        fields = (
            'user_input',
            'response',
            'references',
            'total_cost',
            'created_at',
            'celery_task',
        )
        read_only_fields = ('__all__',)


# Objects are modified only through very specific views,
# so the serializer is used only for reading
class TextSearchConversationReadOnlySerializer(serializers.ModelSerializer):
    query_results = TextSearchQueryResultReadOnlySerializer(many=True)

    class Meta:
        model = TextSearchConversation
        fields = (
            'id',
            'title',
            'min_year',
            'max_year',
            'dataset_names',
            'created_at',
            'query_results',
        )
        read_only_fields = ('__all__',)


class ConversationSetTitleSerializer(serializers.Serializer):
    title = serializers.CharField(
        required=True, max_length=100, validators=[reasonable_character_with_spaces_validator]
    )


class TextSearchConversationBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField())


class TextSearchQuerySubmitSerializer(serializers.Serializer):
    user_input = serializers.CharField()

    def save(self, conversation_id: int) -> dict:
        user_input = self.validated_data['user_input']

        instance = TextSearchConversation.objects.get(id=conversation_id)

        dataset_index_queries = []
        for dataset_name in instance.dataset_names:
            dataset = Dataset.objects.get(name=dataset_name)
            dataset_index_queries.append(dataset.index)

        # TODO: Maybe auto-create the task through a signal or by rewriting
        #  results .save() function in the model?
        result = TextSearchQueryResult.objects.create(conversation=instance, user_input=user_input)
        TextTask.objects.create(result=result)

        with transaction.atomic():
            # We need to ensure that the data is nicely in the database
            # before Celery starts working on it since it being quicker is a common occurrence.
            transaction.on_commit(
                lambda: async_call_celery_task_chain(
                    min_year=instance.min_year,
                    max_year=instance.max_year,
                    user_input=user_input,
                    dataset_index_queries=dataset_index_queries,
                    conversation_id=conversation_id,
                    result_uuid=result.uuid,
                )
            )

            return TextSearchConversationReadOnlySerializer(instance).data
