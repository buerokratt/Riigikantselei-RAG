import datetime

from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from api.utilities.core_settings import get_core_setting
from api.utilities.serializers import reasonable_character_with_spaces_validator
from text_search.models import TextSearchConversation, TextTask, TextSearchQueryResult
from text_search.tasks import async_call_celery_task_chain


class TextSearchConversationCreateSerializer(serializers.Serializer):
    user_input = serializers.CharField()

    min_year = serializers.IntegerField(default=None, min_value=1700)
    max_year = serializers.IntegerField(default=None, min_value=1700)
    indices = serializers.ListField(child=serializers.CharField(), default=list(['rk_riigi_teataja_kehtivad_vectorized']))

    def validate(self, data: dict) -> dict:
        min_year = data['min_year']
        if min_year and min_year > datetime.datetime.now().year:
            raise ValidationError('min_year must be lesser than currently running year!')

        max_year = data['max_year']
        if max_year and max_year > datetime.datetime.now().year:
            raise ValidationError('max_year must be lesser than currently running year!')

        if min_year and max_year and min_year > max_year:
            raise ValidationError('min_year must be lesser than max_year!')

        return data

    def create(self, validated_data: dict) -> TextSearchConversation:
        min_year = self.validated_data['min_year']
        max_year = self.validated_data['max_year']
        indices = self.validated_data['indices']

        conversation = TextSearchConversation.objects.create(
            auth_user=validated_data['auth_user'],
            system_input=get_core_setting('OPENAI_SYSTEM_MESSAGE'),
            title=validated_data['user_input'],
            indices=indices,
            min_year=min_year,
            max_year=max_year,
        )
        conversation.save()
        return conversation


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = TextTask
        fields = ('status', 'error', 'created_at', 'modified_at')
        read_only_fields = ('__all__',)


# Objects are never modified, so the serializer is used only for reading
class TextSearchQueryResultReadOnlySerializer(serializers.ModelSerializer):
    celery_task = TaskSerializer(read_only=True, many=False)

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


# Objects are never modified, so the serializer is used only for reading
class TextSearchConversationReadOnlySerializer(serializers.ModelSerializer):
    query_results = TextSearchQueryResultReadOnlySerializer(many=True)

    class Meta:
        model = TextSearchConversation
        fields = (
            'id',
            'title',
            'min_year',
            'max_year',
            'indices',
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

        instance = TextSearchConversation.objects.get(pk=conversation_id)

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
                    conversation_id=conversation_id,
                    indices=instance.indices,
                    result_uuid=result.uuid,
                )
            )

            return TextSearchConversationReadOnlySerializer(instance).data
