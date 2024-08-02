from datetime import datetime
from typing import Any

from django.conf import settings
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueValidator

from api.utilities.serializers import reasonable_character_with_spaces_validator
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


class ConversationSetTitleSerializer(serializers.Serializer):
    title = serializers.CharField(
        required=True, max_length=100, validators=[reasonable_character_with_spaces_validator]
    )


class ConversationBulkDeleteSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField())


class StatisticsSerializer(serializers.Serializer):
    year = serializers.IntegerField(required=True, min_value=2024)
    month = serializers.IntegerField(required=True, min_value=1, max_value=12)

    def validate(self, data: dict) -> dict:
        if data['year'] > datetime.now().year:
            raise ValidationError('year must be less than the current year!')
        if data['year'] == 2024 and data['month'] < 7:
            raise ValidationError("Can't make statistics for before July 2024!")
        if data['year'] == datetime.now().year and data['month'] > datetime.now().month:
            raise ValidationError("Can't make statistics for after the current month!")
        return data
