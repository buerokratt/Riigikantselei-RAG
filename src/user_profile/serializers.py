import re

from django.contrib.auth.models import User
from rest_framework import serializers

from user_profile.models import UserProfile

# Prevent using bad characters like various whitespace
_REASONABLE_CHARACTER_PATTERN = re.compile(r'[\w<>|,;.:\-_~+!"#¤%&/()=?@£€${\[\]}\\§\'*]*')
# Real email matching is incredibly complex, but this checks for the main structure
_SIMPLE_EMAIL_PATTERN = re.compile(r'[^\s@]+@[^\s@]+\.[^\s@]+')


def _reasonable_character_validator(string: str) -> str:
    if not _REASONABLE_CHARACTER_PATTERN.fullmatch(string):
        raise serializers.ValidationError('The given value contains forbidden characters.')
    return string


def _simple_email_format_validator(email: str) -> str:
    if not _SIMPLE_EMAIL_PATTERN.fullmatch(email):
        raise serializers.ValidationError('The given value is not an email.')
    return email


def _unique_username_validator(username: str) -> str:
    if User.objects.filter(username=username):
        raise serializers.ValidationError('The given username is already in use.')
    return username


def _unique_email_validator(email: str) -> str:
    if User.objects.filter(email=email):
        raise serializers.ValidationError('The given email is already in use.')
    return email


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(
        required=True,
        max_length=100,
        min_length=4,
        validators=[_reasonable_character_validator, _unique_username_validator],
    )
    password = serializers.CharField(
        required=True, max_length=100, min_length=4, validators=[_reasonable_character_validator]
    )
    email = serializers.CharField(
        required=True,
        max_length=100,
        validators=[_simple_email_format_validator, _unique_email_validator],
    )
    first_name = serializers.CharField(required=True, max_length=100)
    last_name = serializers.CharField(required=True, max_length=100)


# Objects are modified only through very specific views,
# so the serializer is used only for reading
class UserProfileReadOnlySerializer(serializers.ModelSerializer):
    is_manager = serializers.BooleanField()
    is_reviewed = serializers.BooleanField()
    is_accepted = serializers.BooleanField()
    is_allowed_to_spend_resources = serializers.BooleanField()
    custom_usage_limit_euros = serializers.FloatField()

    def to_representation(self, instance: UserProfile) -> dict:
        data = super().to_representation(instance)

        # Adding values from User that we care about
        auth_user = instance.auth_user
        data['id'] = auth_user.id
        data['username'] = auth_user.username
        data['email'] = auth_user.email
        data['first_name'] = auth_user.first_name
        data['last_name'] = auth_user.last_name

        return data

    class Meta:
        model = UserProfile
        fields = (
            'is_manager',
            'is_reviewed',
            'is_accepted',
            'is_allowed_to_spend_resources',
            'custom_usage_limit_euros',
        )
        read_only_fields = ('__all__',)


class LimitSerializer(serializers.Serializer):
    limit = serializers.FloatField(required=True, min_value=0.0, max_value=1000.0)


class PasswordSerializer(serializers.Serializer):
    password = serializers.CharField(
        required=True, max_length=100, min_length=4, validators=[_reasonable_character_validator]
    )


class PasswordResetSerializer(serializers.Serializer):
    password = serializers.CharField(
        required=True, max_length=100, min_length=4, validators=[_reasonable_character_validator]
    )
    token = serializers.CharField(required=True)


class EmailSerializer(serializers.Serializer):
    email = serializers.CharField(
        required=True,
        max_length=100,
        validators=[_simple_email_format_validator],
    )
