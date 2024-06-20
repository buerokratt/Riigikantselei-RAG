from typing import Any

from celery.result import AsyncResult
from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from api.utilities.core_settings import get_core_setting
from api.utilities.serializers import reasonable_character_with_spaces_validator
from core.choices import CORE_VARIABLE_CHOICES
from core.models import CoreVariable, TextSearchConversation, TextSearchQueryResult
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

    def create(self, validated_data: dict) -> TextSearchConversation:
        conversation = TextSearchConversation.objects.create(
            auth_user=validated_data['auth_user'],
            system_input=get_core_setting('OPENAI_SYSTEM_MESSAGE'),
            title=validated_data['user_input'],
        )
        conversation.save()
        return conversation


# Objects are never modified, so the serializer is used only for reading
class TextSearchQueryResultReadOnlySerializer(serializers.ModelSerializer):
    def to_representation(self, instance: TextSearchQueryResult) -> dict:
        data = super().to_representation(instance)
        # This is a list, so is saved in the database as a string,
        # but we should still return it as a list
        data['document_types'] = instance.document_types
        return data

    class Meta:
        model = TextSearchQueryResult
        fields = (
            'min_year',
            'max_year',
            'user_input',
            'response',
            'total_cost',
            'created_at',
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
            'created_at',
            'query_results',
        )
        read_only_fields = ('__all__',)


class ConversationSetTitleSerializer(serializers.Serializer):
    title = serializers.CharField(
        required=True, max_length=100, validators=[reasonable_character_with_spaces_validator]
    )


class TextSearchQuerySubmitSerializer(serializers.Serializer):
    min_year = serializers.IntegerField(required=True, min_value=1900, max_value=2024)
    max_year = serializers.IntegerField(required=True, min_value=1900, max_value=2024)
    document_types = serializers.ListField(
        required=True,
        child=serializers.ChoiceField(
            choices=list(settings.DOCUMENT_CATEGORY_TO_INDICES_MAP.keys())
        ),
    )

    user_input = serializers.CharField()

    def save(self, conversation_id: int) -> AsyncResult:
        min_year = self.validated_data['min_year']
        max_year = self.validated_data['max_year']
        document_types_string = ','.join(self.validated_data['document_types'])
        user_input = self.validated_data['user_input']

        document_indices = []
        for document_type in self.validated_data['document_types']:
            document_indices.extend(settings.DOCUMENT_CATEGORY_TO_INDICES_MAP[document_type])

        return async_call_celery_task_chain(
            min_year, max_year, user_input, document_indices, conversation_id, document_types_string
        )
