# type: ignore
from django.utils.translation import gettext as _
from rest_framework import permissions

_LOGGED_OUT_ONLY_ACTIONS = {
    'create',
}
_LOGGED_IN_ONLY_ACTIONS = {'retrieve', 'change_password'}
_MANAGER_ONLY_ACTIONS = {'list', 'accept', 'decline', 'ban', 'set_limit'}


class UserProfilePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        # Just in case superuser does not have good UserProfile values set
        if request.user.is_authenticated and request.user.is_superuser:
            return True

        if view.action in _LOGGED_OUT_ONLY_ACTIONS:
            return not request.user.is_authenticated
        if view.action in _LOGGED_IN_ONLY_ACTIONS:
            return request.user.is_authenticated
        if view.action in _MANAGER_ONLY_ACTIONS:
            return request.user.is_authenticated and request.user.user_profile.is_manager

        return request.user.is_authenticated


class IsManagerPermission(permissions.BasePermission):
    message = _('Your account is not a manager!')

    def has_permission(self, request, view):  # pylint: disable=unused-argument
        # Just in case superuser does not have good UserProfile values set
        if request.user.is_authenticated and request.user.is_superuser:
            return True

        return request.user.is_authenticated and request.user.user_profile.is_manager


class IsAcceptedPermission(permissions.BasePermission):
    message = _('Your account has not been accepted by a moderator!')

    def has_permission(self, request, view):  # pylint: disable=unused-argument
        # Just in case superuser does not have good UserProfile values set
        if request.user.is_authenticated and request.user.is_superuser:
            return True

        return request.user.is_authenticated and request.user.user_profile.is_accepted


class CanSpendResourcesPermission(permissions.BasePermission):
    message = _('You have reached your monetary limit!')

    def has_permission(self, request, view):  # pylint: disable=unused-argument
        # Just in case superuser does not have good UserProfile values set
        if request.user.is_authenticated and request.user.is_superuser:
            return True

        return (
            request.user.is_authenticated
            and request.user.user_profile.is_allowed_to_spend_resources
            and request.user.user_profile.used_cost < request.user.user_profile.usage_limit
        )
