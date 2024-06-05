from rest_framework import permissions

_ADMIN_ONLY_ACTIONS = {'list'}


class UserProfilePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if view.action == 'create':
            return not request.user.is_authenticated
        if view.action == 'retrieve':
            return request.user.is_authenticated
        if view.action in _ADMIN_ONLY_ACTIONS:
            return request.user.is_authenticated and request.user.user_profile.is_admin
        return False

    def has_object_permission(self, request, view, obj):
        # TODO here: i am assuming that we only reach here if has_permission was true, confirm
        if view.action == 'create':
            return True
        if view.action == 'retrieve':
            return request.user.user_profile.is_admin or obj.auth_user == request.user
        if view.action in _ADMIN_ONLY_ACTIONS:
            return True
        return False
