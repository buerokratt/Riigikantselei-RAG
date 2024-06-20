from django.contrib.auth.models import User
from django.db import models
from django.db.models import Sum
from rest_framework.authtoken.models import Token

from api.utilities.core_settings import get_core_setting
from core.models import TextSearchQueryResult


class UserProfile(models.Model):
    # The authentication user tied to this user profile.
    # Contains id, which can be used as a unique identifier.
    # Contains the following, which can be used to identify and contact the person:
    # - username
    # - email
    # - first_name
    # - last_name
    # Set on creation.
    auth_user = models.OneToOneField(User, on_delete=models.RESTRICT, related_name='user_profile')
    # Whether the user is allowed to manage other users.
    # Separate from Django superuser or staff as administering the web application is our job
    # and managing the users' rights is the customers' job.
    # May be manually set to True later by the developers if the customer requests.
    is_manager = models.BooleanField(default=False)
    # Whether a manager needs to review this user's request to use the application.
    # Used to choose which users to show to managers as needing review.
    # Will be set to True once a manager reviews the request to use the application.
    is_reviewed = models.BooleanField(default=False)
    # Whether the user has been accepted to use the application.
    # Used to check if the user should be able to log in.
    # Will be set to True if a manager reviews and accepts the request to use the application.
    is_accepted = models.BooleanField(default=False)
    # Whether the user is allowed to take actions that cost money.
    # If this is False (and is_accepted=True),
    # the user should still see their previous interactions.
    # Will be set to True if a manager reviews and accepts the request to use the application.
    # May be set to False later to stop an expensive user.
    is_allowed_to_spend_resources = models.BooleanField(default=False)
    # The user's custom usage limit.
    # May be set and unset later to change the user's limit logic.
    # If this is None, the usage limit should be read from the default value.
    custom_usage_limit_euros = models.FloatField(default=None, null=True)

    @property
    def usage_limit(self) -> float:
        if self.custom_usage_limit_euros is not None:
            return self.custom_usage_limit_euros
        return get_core_setting('DEFAULT_USAGE_LIMIT_EUROS')

    @property
    def used_cost(self) -> float:
        user_queries = TextSearchQueryResult.objects.filter(conversation__auth_user=self.auth_user)
        return user_queries.aggregate(Sum('total_cost', default=0.0))['total_cost__sum']


class PasswordResetToken(models.Model):
    auth_user = models.ForeignKey(User, on_delete=models.RESTRICT)
    key = models.CharField(default=Token.generate_key, max_length=50)
