from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from api.utilities.core_settings import get_core_setting
from user_profile.utilities import create_test_user_with_user_profile


# pylint: disable=too-many-instance-attributes,too-many-public-methods
class TestUserProfileEdit(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.manager_auth_user = create_test_user_with_user_profile(
            self, 'manager', 'manager@email.com', 'password', is_manager=True
        )
        self.non_manager_reviewed_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )
        self.non_manager_unreviewed_auth_user = create_test_user_with_user_profile(
            self, 'tester2', 'tester2@email.com', 'password', is_manager=False
        )

        non_manager_unreviewed_user_profile = self.non_manager_unreviewed_auth_user.user_profile
        non_manager_unreviewed_user_profile.is_reviewed = False
        non_manager_unreviewed_user_profile.is_accepted = False
        non_manager_unreviewed_user_profile.is_allowed_to_spend_resources = False
        non_manager_unreviewed_user_profile.save()

        self.accept_reviewed_endpoint_url = reverse(
            'v1:user_profile-accept', kwargs={'pk': self.non_manager_reviewed_auth_user.id}
        )
        self.accept_unreviewed_endpoint_url = reverse(
            'v1:user_profile-accept', kwargs={'pk': self.non_manager_unreviewed_auth_user.id}
        )
        self.decline_reviewed_endpoint_url = reverse(
            'v1:user_profile-decline', kwargs={'pk': self.non_manager_reviewed_auth_user.id}
        )
        self.decline_unreviewed_endpoint_url = reverse(
            'v1:user_profile-decline', kwargs={'pk': self.non_manager_unreviewed_auth_user.id}
        )

        self.ban_endpoint_url = reverse(
            'v1:user_profile-ban', kwargs={'pk': self.non_manager_reviewed_auth_user.id}
        )
        self.set_limit_endpoint_url = reverse(
            'v1:user_profile-set-limit', kwargs={'pk': self.non_manager_reviewed_auth_user.id}
        )

        self.new_limit = 20.123
        self.input_data = {'limit': self.new_limit}

    # Accept

    def test_accept(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.accept_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        updated_auth_user = User.objects.get(id=self.non_manager_unreviewed_auth_user.id)
        updated_user_profile = updated_auth_user.user_profile
        self.assertTrue(updated_user_profile.is_reviewed)
        self.assertTrue(updated_user_profile.is_accepted)

    def test_accept_fails_because_not_authed(self) -> None:
        response = self.client.post(self.accept_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_accept_fails_because_not_manager(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_manager_reviewed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.accept_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_accept_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        accept_endpoint_url = reverse('v1:user_profile-accept', kwargs={'pk': 999})

        response = self.client.post(accept_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_accept_fails_because_already_reviewed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.accept_reviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Decline

    def test_decline(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.decline_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        updated_auth_user = User.objects.get(id=self.non_manager_unreviewed_auth_user.id)
        updated_user_profile = updated_auth_user.user_profile
        self.assertTrue(updated_user_profile.is_reviewed)
        self.assertFalse(updated_user_profile.is_accepted)

    def test_decline_fails_because_not_authed(self) -> None:
        response = self.client.post(self.decline_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_decline_fails_because_not_manager(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_manager_reviewed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.decline_unreviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_decline_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        decline_endpoint_url = reverse('v1:user_profile-decline', kwargs={'pk': 999})

        response = self.client.post(decline_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_decline_fails_because_already_reviewed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.decline_reviewed_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # Ban

    def test_ban(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.ban_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        updated_auth_user = User.objects.get(id=self.non_manager_reviewed_auth_user.id)
        updated_user_profile = updated_auth_user.user_profile
        self.assertFalse(updated_user_profile.is_allowed_to_spend_resources)

    def test_ban_fails_because_not_authed(self) -> None:
        response = self.client.post(self.ban_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_ban_fails_because_not_manager(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_manager_reviewed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.ban_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_ban_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        ban_endpoint_url = reverse('v1:user_profile-ban', kwargs={'pk': 999})

        response = self.client.post(ban_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # set limit

    def test_set_limit(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        self.assertEqual(
            self.non_manager_reviewed_auth_user.user_profile.usage_limit,
            get_core_setting('DEFAULT_USAGE_LIMIT_EUROS'),
        )

        response = self.client.post(self.set_limit_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        updated_auth_user = User.objects.get(id=self.non_manager_reviewed_auth_user.id)
        updated_user_profile = updated_auth_user.user_profile
        self.assertEqual(updated_user_profile.custom_usage_limit_euros, self.new_limit)
        self.assertEqual(updated_user_profile.usage_limit, self.new_limit)

    def test_set_limit_fails_because_not_authed(self) -> None:
        response = self.client.post(self.set_limit_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_set_limit_fails_because_not_manager(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_manager_reviewed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.set_limit_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_set_limit_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        set_limit_endpoint_url = reverse('v1:user_profile-set-limit', kwargs={'pk': 999})

        response = self.client.post(set_limit_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_set_limit_fails_because_bad_limit(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        input_data = {'limit': 10_000.0}

        response = self.client.post(self.set_limit_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_setting_user_to_manager(self) -> None:
        admin = create_test_user_with_user_profile(
            self, 'admin', email='admin@gmail.com', password='1234', is_admin=True
        )
        plebian = create_test_user_with_user_profile(
            self,
            'plebian',
            email='plebian@gmail.com',
            password='1234',
            is_admin=False,
            is_manager=False,
        )

        # Login as admin
        token, _ = Token.objects.get_or_create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Make the request
        uri = reverse('v1:user_profile-set-manager', kwargs={'pk': plebian.id})
        response = self.client.post(uri, data={})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check the state.
        plebian.refresh_from_db()
        self.assertEqual(plebian.user_profile.is_manager, True)

        # Lets try switching it again.
        response = self.client.post(uri, data={})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plebian.refresh_from_db()
        self.assertEqual(plebian.user_profile.is_manager, False)

    def test_setting_user_to_superuser(self) -> None:
        admin = create_test_user_with_user_profile(
            self, 'admin', email='admin@gmail.com', password='1234', is_admin=True
        )
        plebian = create_test_user_with_user_profile(
            self,
            'plebian',
            email='plebian@gmail.com',
            password='1234',
            is_admin=False,
            is_manager=False,
        )

        # Login as admin
        token, _ = Token.objects.get_or_create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Make the request
        uri = reverse('v1:user_profile-set-superuser', kwargs={'pk': plebian.id})
        response = self.client.post(uri, data={})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check the state.
        plebian.refresh_from_db()
        self.assertEqual(plebian.is_staff, True)
        self.assertEqual(plebian.is_superuser, True)

        # Lets try switching it again.
        response = self.client.post(uri, data={})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        plebian.refresh_from_db()
        self.assertEqual(plebian.is_staff, False)
        self.assertEqual(plebian.is_superuser, False)

    def test_superusers_not_being_able_to_change_their_status(self) -> None:
        admin = create_test_user_with_user_profile(
            self, 'admin', email='admin@gmail.com', password='1234', is_admin=True
        )
        token, _ = Token.objects.get_or_create(user=admin)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        uri = reverse('v1:user_profile-set-superuser', kwargs={'pk': admin.id})
        response = self.client.post(uri, data={})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
