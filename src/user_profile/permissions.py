# type: ignore
from rest_framework import permissions

_ADMIN_ONLY_ACTIONS = {'list', 'accept', 'decline', 'ban', 'set_limit'}


class UserProfilePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if view.action == 'create':
            return not request.user.is_authenticated
        if view.action == 'retrieve':
            return request.user.is_authenticated and request.user.user_profile.is_accepted
        if view.action in _ADMIN_ONLY_ACTIONS:
            return request.user.is_authenticated and request.user.user_profile.is_admin
        return False

    def has_object_permission(self, request, view, obj):
        if view.action == 'retrieve':
            return request.user.user_profile.is_admin or obj.auth_user == request.user
        raise RuntimeError('No action other than "retrieve" should check for object permission.')
