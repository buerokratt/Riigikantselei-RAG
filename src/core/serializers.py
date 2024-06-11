from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .choices import CORE_VARIABLE_CHOICES
from .models import CoreVariable, ChatGPTConversation


class ChatGPTConversationSerializer(serializers.ModelSerializer):
    system_input = serializers.CharField(default=None, allow_blank=True)
    messages = serializers.SerializerMethodField()

    def get_messages(self, obj):
        return obj.messages

    class Meta:
        model = ChatGPTConversation
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'author')


class OpenAISerializer(serializers.Serializer):
    input_text = serializers.CharField(help_text="User query to send towards ChatGPT")
    model = serializers.CharField(default=None, help_text="Manual override for the model to use with ChatGPT, only use if you know what you're doing.")


class CoreVariableSerializer(serializers.ModelSerializer):
    name = serializers.ChoiceField(
        help_text="Name of the core variable.",
        choices=CORE_VARIABLE_CHOICES,
        validators=[UniqueValidator(queryset=CoreVariable.objects.all())],
        required=True
    )

    value = serializers.CharField(
        help_text="Value of the core variable.",
        required=True,
        allow_blank=True,
        allow_null=True
    )

    env_value = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super(CoreVariableSerializer, self).to_representation(instance)
        protected = settings.PROTECTED_CORE_KEYS

        for protected_key in protected:
            if protected_key.lower() in instance.name.lower():
                data["value"] = 12 * "*" + data["value"][-3:]

        return data

    class Meta:
        model = CoreVariable
        fields = ("id", "name", "value", "env_value")

    def get_env_value(self, obj):
        """Retrieves value for the variable from env."""
        variable_name = obj.name
        env_value = settings.CORE_SETTINGS.get(variable_name, "")
        return env_value
