from rest_framework import serializers

from user_profile.models import UserProfile


class UserCreateSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    email = serializers.CharField()
    first_name = serializers.CharField()
    last_name = serializers.CharField()

    # TODO here: help_text, validators (no duplicate email; username and password reasonable)


# Objects are modified only through very specific views,
# so the serializer is used only for reading
class UserProfileReadOnlySerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField()
    reviewed = serializers.BooleanField()
    accepted = serializers.BooleanField()
    allowed_to_spend_resources = serializers.BooleanField()
    usage_limit_is_default = serializers.BooleanField()
    custom_usage_limit_euros = serializers.FloatField()

    # TODO here: help_text?

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
            'is_admin',
            'reviewed',
            'accepted',
            'allowed_to_spend_resources',
            'usage_limit_is_default',
            'custom_usage_limit_euros',
        )
        read_only_fields = ('__all__',)
