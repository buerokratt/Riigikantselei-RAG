from typing import Any

from django.conf import settings
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from core.choices import CORE_VARIABLE_CHOICES
from core.models import CoreVariable, Dataset


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


# Objects are never modified through views, so the serializer is used only for reading
class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = '__all__'
