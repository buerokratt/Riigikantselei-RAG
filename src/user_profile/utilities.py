from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase


# Creates the most common (permissive) manager or non manager user
# Restrictions can be applied later through auth_user.user_profile.update()
def create_test_user_with_user_profile(
        testcase: APITestCase, username: str, email: str, password: str, is_manager: bool = False, is_admin=False
) -> User:
    _url = reverse('v1:user_profile-list')
    _input = {
        'username': username,
        'email': email,
        'first_name': 'tester',
        'last_name': 'tester',
        'password': password,
    }

    response = testcase.client.post(_url, data=_input)
    testcase.assertEqual(response.status_code, status.HTTP_201_CREATED)
    testcase.assertIn('id', response.data)

    auth_user_id = response.data['id']
    auth_user = User.objects.get(id=auth_user_id)
    user_profile = auth_user.user_profile

    # Regular permissive settings
    user_profile.is_reviewed = True
    user_profile.is_accepted = True
    user_profile.is_allowed_to_spend_resources = True
    user_profile.save()

    if is_manager:
        user_profile.is_manager = True
        user_profile.save()

    if is_admin:
        auth_user.is_superuser = is_admin
        auth_user.is_staff = is_admin
        auth_user.save()

    return auth_user
