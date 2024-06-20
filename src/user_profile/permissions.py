# type: ignore
from rest_framework import permissions

_LOGGED_OUT_ONLY_ACTIONS = {
    'create',
    'request_password_reset',
    'confirm_password_reset',
    'reset_password',
}
_LOGGED_IN_AND_ACCEPTED_ONLY_ACTIONS = {'retrieve', 'change_password'}
_MANAGER_ONLY_ACTIONS = {'list', 'accept', 'decline', 'ban', 'set_limit'}


class UserProfilePermission(permissions.BasePermission):
    def has_permission(self, request, view):  # type: ignore
        if request.user.is_authenticated and request.user.is_superuser:
            return True

        if view.action in _LOGGED_OUT_ONLY_ACTIONS:
            return not request.user.is_authenticated
        if view.action in _LOGGED_IN_AND_ACCEPTED_ONLY_ACTIONS:
            return request.user.is_authenticated and request.user.user_profile.is_accepted
        if view.action in _MANAGER_ONLY_ACTIONS:
            return request.user.is_authenticated and request.user.user_profile.is_manager

        # TODO: uncomment once browsable API is no longer needed
        # raise RuntimeError('Unknown action.')
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):  # type: ignore
        if request.user.is_superuser:
            return True

        if view.action == 'retrieve':
            return request.user.user_profile.is_manager or obj.auth_user == request.user
        raise RuntimeError('No action other than "retrieve" should check for object permission.')


class IsManagerPermission(permissions.BasePermission):
    def has_permission(self, request, view):  # pylint: disable=unused-argument
        return request.user.is_authenticated and request.user.user_profile.is_manager


class CanSpendResourcesPermission(permissions.BasePermission):
    def has_permission(self, request, view):  # pylint: disable=unused-argument
        return (
            request.user.is_authenticated
            and request.user.user_profile.is_allowed_to_spend_resources
        )
