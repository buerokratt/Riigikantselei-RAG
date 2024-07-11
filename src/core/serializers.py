import datetime
from typing import Any

from django.conf import settings
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueValidator

from api.utilities.core_settings import get_core_setting
from api.utilities.serializers import reasonable_character_with_spaces_validator
from core.choices import CORE_VARIABLE_CHOICES
from core.models import (
    CoreVariable,
    Task,
    TextSearchConversation,
    TextSearchQueryResult,
)
from core.tasks import async_call_celery_task_chain


class CoreVariableSerializer(serializers.ModelSerializer):
    name = serializers.ChoiceField(
        help_text='Name of the core variable.',
        choices=CORE_VARIABLE_CHOICES,
        validators=[UniqueValidator(queryset=CoreVariable.objects.all())],
        required=True,
    )

    value = serializers.CharField(
        help_text='Value of the core variable.', required=True, allow_blank=True, allow_null=True
    )

    env_value = serializers.SerializerMethodField()

    def to_representation(self, instance: CoreVariable) -> dict:
        data = super().to_representation(instance)

        protected = settings.PROTECTED_CORE_KEYS
        for protected_key in protected:
            if protected_key.lower() in instance.name.lower():
                data['value'] = 12 * '*' + data['value'][-3:]

        return data

    class Meta:
        model = CoreVariable
        fields = ('id', 'name', 'value', 'env_value')

    def get_env_value(self, obj: CoreVariable) -> Any:
        """Retrieves value for the variable from env."""
        variable_name = obj.name
        env_value = settings.CORE_SETTINGS.get(variable_name, '')
        return env_value


class TextSearchConversationCreateSerializer(serializers.Serializer):
    user_input = serializers.CharField()

    min_year = serializers.IntegerField(default=None, min_value=1700)
    max_year = serializers.IntegerField(default=None, min_value=1700)
    document_types = serializers.ListField(
        # By default include all indices.
        default=list(settings.DOCUMENT_CATEGORY_TO_INDICES_MAP.keys()),
        child=serializers.ChoiceField(
            choices=list(settings.DOCUMENT_CATEGORY_TO_INDICES_MAP.keys())
        ),
    )

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
        document_types_string = ','.join(self.validated_data['document_types'])

        document_indices = []
        for document_type in self.validated_data['document_types']:
            document_indices.extend(settings.DOCUMENT_CATEGORY_TO_INDICES_MAP[document_type])

        conversation = TextSearchConversation.objects.create(
            auth_user=validated_data['auth_user'],
            system_input=get_core_setting('OPENAI_SYSTEM_MESSAGE'),
            title=validated_data['user_input'],
            document_types_string=document_types_string,
            min_year=min_year,
            max_year=max_year,
        )
        conversation.save()
        return conversation


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
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
            'document_types',
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

        document_indices = []
        for document_type in instance.document_types:
            document_indices.extend(settings.DOCUMENT_CATEGORY_TO_INDICES_MAP[document_type])

        # TODO: Maybe auto-create the task through a signal or by rewriting
        #  results .save() function in the model?
        result = TextSearchQueryResult.objects.create(conversation=instance, user_input=user_input)
        Task.objects.create(result=result)

        with transaction.atomic():
            # We need to ensure that the data is nicely in the database
            # before Celery starts working on it since it being quicker is a common occurrence.
            transaction.on_commit(
                lambda: async_call_celery_task_chain(
                    instance.min_year,
                    instance.max_year,
                    user_input,
                    document_indices,
                    conversation_id,
                    instance.document_types_string,
                    result_uuid=result.uuid,
                )
            )

            return TextSearchConversationReadOnlySerializer(instance).data
