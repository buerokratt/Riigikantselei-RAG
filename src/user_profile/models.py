from django.contrib.auth.models import User
from django.db import models


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
    # Whether the user is an admin for the purposes of customer requirements.
    # Separate from Django superuser or staff as administering the web application is our job
    # and administering the users' rights is the customers' job.
    # May be manually set to True later by the developers if the customer requests.
    is_admin = models.BooleanField(default=False)
    # Whether an admin needs to review this user's request to use the application.
    # Used to choose which users to show to admins as needing review.
    # Will be set to True once an admin reviews the request to use the application.
    is_reviewed = models.BooleanField(default=False)
    # Whether the user has been accepted to use the application.
    # Used to check if the user should be able to log in.
    # Will be set to True if an admin reviews and accepts the request to use the application.
    is_accepted = models.BooleanField(default=False)
    # Whether the user is allowed to take actions that cost money.
    # If this is False (and is_accepted=True),
    # the user should still see their previous interactions.
    # Will be set to True if an admin reviews and accepts the request to use the application.
    # May be set to False later to stop an expensive user.
    is_allowed_to_spend_resources = models.BooleanField(default=False)
    # Whether the user's usage limit should be tied to the default.
    # If this is True, the usage limit should be read from the default value.
    # If this is False, the usage limit should be read from custom_usage_limit_euros.
    # May be switched later to change the user's limit logic.
    usage_limit_is_default = models.BooleanField(default=True)
    # The user's custom usage limit.
    # May be set and unset later to change the user's limit logic.
    custom_usage_limit_euros = models.FloatField(default=None, null=True)

    # TODO: The user's current usage balance is the sum of the costs of UsageEvents
    #  tied to the user and will be calculated when needed.
