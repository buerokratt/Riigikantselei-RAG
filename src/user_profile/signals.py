from typing import Any

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from user_profile.models import UserProfile

# pylint: disable=unused-argument


@receiver(post_save, sender=User)
def create_profile(sender: User, instance: User, created: bool, **kwargs: Any) -> None:
    """When User object is created, create a UserProfile"""
    if created:
        UserProfile.objects.get_or_create(auth_user=instance)
