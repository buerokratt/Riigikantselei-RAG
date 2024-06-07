# type: ignore
from django.contrib.auth.models import AnonymousUser
from rest_framework import permissions

_ADMIN_ONLY_ACTIONS = {'list'}


# TODO here: remove print statements from this file


class UserProfilePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if view.action == 'create':
            return not request.user.is_authenticated
        print(f'has_permission: action={view.action}, user={request.user}, ', end='')
        if not isinstance(request.user, AnonymousUser) and hasattr(request.user, 'user_profile'):
            print(
                f'admin={request.user.user_profile.is_admin}, '
                f'auth={request.user.is_authenticated}, '
                f'accepted={request.user.user_profile.is_accepted}.',
                end='',
            )
        print()
        if view.action == 'retrieve':
            return request.user.is_authenticated and request.user.user_profile.is_accepted
        if view.action in _ADMIN_ONLY_ACTIONS:
            return request.user.is_authenticated and request.user.user_profile.is_admin
        return False

    def has_object_permission(self, request, view, obj):
        print(f'has_object_permission: action={view.action}, user={request.user}, ', end='')
        if not isinstance(request.user, AnonymousUser) and hasattr(request.user, 'user_profile'):
            print(
                f'admin={request.user.user_profile.is_admin}, '
                f'auth={request.user.is_authenticated}, '
                f'accepted={request.user.user_profile.is_accepted}, ',
                f'object_user={obj.auth_user}.',
                end='',
            )
        print()

        if view.action == 'retrieve':
            return request.user.user_profile.is_admin or obj.auth_user == request.user

        raise RuntimeError('No action other than retrieve should check for object permission.')
