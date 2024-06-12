from django.conf import settings
from django.db import transaction
from django.urls import reverse
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from api.utilities.core_settings import get_core_setting

from .choices import CORE_VARIABLE_CHOICES
from .models import ChatGPTConversation, CoreVariable
from .tasks import commit_openai_api_call, get_rag_context

MODEL_FIELD_HELPTEXT = (
    "Manual override for the model to use with ChatGPT, only use if you know what you're doing.",
)


class ChatGPTConversationSerializer(serializers.ModelSerializer):
    input_text = serializers.CharField(write_only=True)
    model = serializers.CharField(
        default=None,
        help_text=MODEL_FIELD_HELPTEXT,
        write_only=True,
    )

    system_input = serializers.CharField(default=None, allow_blank=True)
    messages = serializers.SerializerMethodField()

    # Since we create the the first chat upon the creation of the conversation we need to display the first task id in the output for the CREATE.
    def to_representation(self, instance: ChatGPTConversation):
        data = super().to_representation(instance)
        creation_task = instance.llmresult_set.first()
        if creation_task:
            task_id = creation_task.celery_task_id
            relative_path = reverse('async_result', kwargs={'task_id': task_id})
            data['task'] = {
                'id': task_id,
                'url': self.context['request'].build_absolute_uri(relative_path),
            }

        return data

    def create(self, validated_data):
        input_text = validated_data.pop('input_text', None)
        model = validated_data.pop('model', None)

        indices = validated_data['indices']
        vector_field = get_core_setting('ELASTICSEARCH_VECTOR_FIELD')
        content_field = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')

        # Since Celery tasks can happen quicker than the db can handle transaction, we only launch the task AFTER the commit.
        with transaction.atomic():
            orm = super().create(validated_data)
            task = get_rag_context.s(
                input_text, indices, vector_field, content_field
            ) | commit_openai_api_call.s(orm.pk, model)
            transaction.on_commit(lambda: task.apply_async())
            return orm

    def get_messages(self, obj):
        return obj.messages

    class Meta:
        model = ChatGPTConversation
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'author')


class OpenAISerializer(serializers.Serializer):
    input_text = serializers.CharField(help_text='User query to send towards ChatGPT')
    model = serializers.CharField(
        default=None,
        help_text=MODEL_FIELD_HELPTEXT,
    )


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

    def to_representation(self, instance):
        data = super(CoreVariableSerializer, self).to_representation(instance)
        protected = settings.PROTECTED_CORE_KEYS

        for protected_key in protected:
            if protected_key.lower() in instance.name.lower():
                data['value'] = 12 * '*' + data['value'][-3:]

        return data

    class Meta:
        model = CoreVariable
        fields = ('id', 'name', 'value', 'env_value')

    def get_env_value(self, obj):
        """Retrieves value for the variable from env."""
        variable_name = obj.name
        env_value = settings.CORE_SETTINGS.get(variable_name, '')
        return env_value
