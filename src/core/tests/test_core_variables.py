# Create your tests here.
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from core.models import CoreVariable
from user_profile.utilities import create_test_user_with_user_profile

SAMPLE_ES_VALUE = 'http://localhost:920000'


class TestCoreVariableViews(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.list_url = reverse('v1:core_settings-list')

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.manager_auth_user = create_test_user_with_user_profile(
            self, 'manager', 'manager@email.com', 'password', is_manager=True
        )
        self.non_manager_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )

        token, _ = Token.objects.get_or_create(user=self.manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    @override_settings(CORE_SETTINGS={'ELASTICSEARCH': SAMPLE_ES_VALUE})
    def test_pulling_uncreated_core_setting_returns_env_defaults(self) -> None:
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Asserting that everything is empty.
        self.assertEqual(len(response.data), 0)

        setting = CoreVariable.get_core_setting('ELASTICSEARCH')
        self.assertEqual(setting, SAMPLE_ES_VALUE)

    @override_settings(CORE_SETTINGS={'ELASTICSEARCH_URL': SAMPLE_ES_VALUE})
    def test_changed_core_settings_returns_expected_value(self) -> None:
        new_value = 'http://localhost:9200'
        data = {'name': 'ELASTICSEARCH_URL', 'value': new_value}

        response = self.client.post(self.list_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        setting = CoreVariable.get_core_setting('ELASTICSEARCH_URL')
        self.assertEqual(setting, new_value)

    def test_floats_and_integers_being_parsed_as_numbers_and_not_strings(self) -> None:
        float_value = 13.5
        data = {'name': 'OPENAI_API_TIMEOUT', 'value': float_value}

        response = self.client.post(self.list_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        setting = CoreVariable.get_core_setting('OPENAI_API_TIMEOUT')
        self.assertTrue(isinstance(setting, float))
        self.assertEqual(setting, float_value)

    def test_unknown_keys_being_rejected_by_validation(self) -> None:
        data = {'name': 'FAKE FAKE FAKE LEMON FAKE', 'value': 'Holy Handgrenade'}

        response = self.client.post(self.list_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_api_keys_and_secrets_being_censored(self) -> None:
        key_value = (
            'Please. This is supposed to be a happy occasion. '
            "Let's not bicker and argue over who killed who!"
        )
        data = {'name': 'OPENAI_API_KEY', 'value': key_value}

        response = self.client.post(self.list_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Setting we fetch must be the original value.
        setting = CoreVariable.get_core_setting('OPENAI_API_KEY')
        self.assertEqual(setting, key_value)

        # Let's check the representations in list/detail views.

        list_response = self.client.get(self.list_url)
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        censored_output = '************ho!'
        for variable in list_response.data:
            representation = variable['value']
            self.assertTrue(len(representation) != len(key_value))
            self.assertEqual(representation, censored_output)

        detail_id = list_response.data[0]['id']
        detail_url = reverse('v1:core_settings-detail', kwargs={'pk': detail_id})

        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        self.assertEqual(detail_response.data['name'], 'OPENAI_API_KEY')
        representation = detail_response.data['value']
        self.assertEqual(representation, censored_output)

    def test_simple_detail_view_access(self) -> None:
        key_name = 'ELASTICSEARCH_URL'
        key_value = 'http://localhost:3000'
        data = {'name': key_name, 'value': key_value}

        response = self.client.post(self.list_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        setting_id = response.data['id']
        detail_url = reverse('v1:core_settings-detail', kwargs={'pk': setting_id})

        detail_response = self.client.get(detail_url)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        self.assertEqual(detail_response.data['name'], key_name)
        self.assertEqual(detail_response.data['value'], key_value)

    def test_editing_core_variable(self) -> None:
        key_name = 'ELASTICSEARCH_URL'
        key_value = 'http://localhost:3000'
        new_value = 'http://localhost:9200000'
        data = {'name': key_name, 'value': key_value}

        response = self.client.post(self.list_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        setting_id = response.data['id']
        patch_url = reverse('v1:core_settings-detail', kwargs={'pk': setting_id})

        patch_response = self.client.patch(patch_url, data={'value': new_value})
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)

        setting = CoreVariable.get_core_setting(key_name)
        self.assertEqual(setting, new_value)

    @override_settings(CORE_SETTINGS={'ELASTICSEARCH_URL': SAMPLE_ES_VALUE})
    def test_deleting_core_variable(self) -> None:
        key_name = 'ELASTICSEARCH_URL'
        key_value = 'http://localhost:3000'
        data = {'name': key_name, 'value': key_value}

        response = self.client.post(self.list_url, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertEqual(response.data['value'], key_value)

        setting_id = response.data['id']
        patch_url = reverse('v1:core_settings-detail', kwargs={'pk': setting_id})

        delete_response = self.client.delete(patch_url)
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Since there is no more core variable set,
        # it should revert to the default value in the settings file.
        setting = CoreVariable.get_core_setting(key_name)
        self.assertEqual(setting, SAMPLE_ES_VALUE)

    def test_non_manager_users_not_having_access(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_manager_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # try get
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # try post
        payload = {'name': 'ELASTICSEARCH_URL', 'value': 'somerandomstring'}
        response = self.client.post(self.list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
