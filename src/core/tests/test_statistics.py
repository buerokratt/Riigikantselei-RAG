from datetime import datetime
from typing import Any, Dict
from unittest import mock

from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

from api.utilities.testing import IsType
from core.models import Dataset
from core.pdf import _build_statistics_context
from document_search.models import DocumentSearchConversation, DocumentSearchQueryResult
from text_search.models import TextSearchConversation, TextSearchQueryResult
from user_profile.models import LogInEvent, LogOutEvent
from user_profile.utilities import create_test_user_with_user_profile


def _mock_time(replacement: datetime):  # type: ignore
    return mock.patch('django.utils.timezone.now', return_value=replacement)


class TestStatistics(APITestCase):
    @classmethod
    def setUpTestData(cls) -> None:  # pylint: disable=invalid-name
        cls.statistics_endpoint_url = reverse('v1:statistics')

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.year = 2024
        self.month = 7
        self.input_data = {
            'year': self.year,
            'month': self.month,
        }

        Dataset(name='a', type='', index='a_*', description='').save()
        Dataset(name='b', type='', index='b_*', description='').save()
        Dataset(name='c', type='', index='c_*', description='').save()

        before_date = datetime(year=self.year, month=self.month - 1, day=15)
        during_date = datetime(year=self.year, month=self.month, day=15)
        after_date = datetime(year=self.year, month=self.month + 1, day=15)

        # Users
        with _mock_time(before_date):
            self.admin_user = create_test_user_with_user_profile(
                self, 'admin', 'admin@email.com', 'password', is_manager=True, is_admin=True
            )
        with _mock_time(after_date):
            self.non_admin_user = create_test_user_with_user_profile(
                self, 'tester', 'tester@email.com', 'password', is_manager=True, is_admin=False
            )
        with _mock_time(during_date):
            user_1 = create_test_user_with_user_profile(
                self, 'tester1', 'tester1@email.com', 'password'
            )
            user_2 = create_test_user_with_user_profile(
                self, 'tester2', 'tester2@email.com', 'password'
            )
            create_test_user_with_user_profile(self, 'tester3', 'tester3@email.com', 'password')

        # Logins
        with _mock_time(before_date):
            LogInEvent.objects.create(auth_user=self.admin_user)
            LogOutEvent.objects.create(auth_user=self.admin_user)
        with _mock_time(after_date):
            LogInEvent.objects.create(auth_user=self.non_admin_user)
            LogOutEvent.objects.create(auth_user=self.non_admin_user)
        with _mock_time(during_date):
            LogInEvent.objects.create(auth_user=self.admin_user)
            LogInEvent.objects.create(auth_user=user_1)
            LogOutEvent.objects.create(auth_user=user_1)
            LogInEvent.objects.create(auth_user=user_2)
            LogOutEvent.objects.create(auth_user=user_2)

        # Conversations

        a_c_t_1 = TextSearchConversation.objects.create(  # 2, 1
            title='',
            auth_user=self.admin_user,
            system_input='',
            min_year=2020,
            max_year=2024,
            dataset_names_string='a,c',
        )
        a_c_d_1 = DocumentSearchConversation.objects.create(  # 2, 1
            title='',
            auth_user=self.admin_user,
            system_input='',
            min_year=2022,
            max_year=2024,
            user_input='',
        )

        n_c_t_1 = TextSearchConversation.objects.create(  # 0, 0
            title='',
            auth_user=self.non_admin_user,
            system_input='',
            min_year=2020,
            max_year=2024,
            dataset_names_string='a,c',
        )
        n_c_d_1 = DocumentSearchConversation.objects.create(  # 0, 0
            title='',
            auth_user=self.non_admin_user,
            system_input='',
            min_year=2022,
            max_year=2024,
            user_input='',
        )

        u1_c_t_1 = TextSearchConversation.objects.create(  # 1, 1
            title='',
            auth_user=user_1,
            system_input='',
            min_year=2020,
            max_year=2024,
            dataset_names_string='a,b',
        )
        u1_c_d_1 = DocumentSearchConversation.objects.create(  # 1, 1
            title='', auth_user=user_1, system_input='', min_year=2022, max_year=2024, user_input=''
        )

        u1_c_t_2 = TextSearchConversation.objects.create(  # 3, 3
            title='',
            auth_user=user_1,
            system_input='',
            min_year=2022,
            max_year=2023,
            dataset_names_string='b,c',
        )
        u1_c_d_2 = DocumentSearchConversation.objects.create(  # 1, 1
            title='', auth_user=user_1, system_input='', min_year=2022, max_year=2023, user_input=''
        )

        # Queries

        with _mock_time(before_date):
            TextSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2020, 'index': 'a_1'}, {'year': 2021, 'index': 'c_1'}],
                conversation=a_c_t_1,
            )
            DocumentSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2022, 'index': 'a_1'}, {'year': 2023, 'index': 'a_9'}],
                conversation=a_c_d_1,
                dataset_name='a',
            )

        with _mock_time(after_date):
            TextSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2021, 'index': 'a_1'}, {'year': 2024, 'index': 'c_1'}],
                conversation=n_c_t_1,
            )
            DocumentSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2022, 'index': 'b_1'}, {'year': 2023, 'index': 'b_9'}],
                conversation=n_c_d_1,
                dataset_name='b',
            )

        with _mock_time(during_date):
            TextSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2022, 'index': 'a_1'}, {'year': 2023, 'index': 'c_1'}],
                conversation=a_c_t_1,
            )
            DocumentSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2024, 'index': 'a_1'}, {'year': 2023, 'index': 'a_2'}],
                conversation=a_c_d_1,
                dataset_name='a',
            )

            TextSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2020, 'index': 'a_1'}, {'year': 2021, 'index': 'b_1'}],
                conversation=u1_c_t_1,
            )
            DocumentSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2023, 'index': 'b_1'}, {'year': 2024, 'index': 'b_2'}],
                conversation=u1_c_d_1,
                dataset_name='b',
            )

            TextSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2022, 'index': 'b_1'}, {'year': 2023, 'index': 'c_1'}],
                conversation=u1_c_t_2,
            )
            DocumentSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2022, 'index': 'c_1'}, {'year': 2023, 'index': 'c_2'}],
                conversation=u1_c_d_2,
                dataset_name='c',
            )

            TextSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2022, 'index': 'b_1'}, {'year': 2023, 'index': 'c_1'}],
                conversation=u1_c_t_2,
            )
            TextSearchQueryResult.objects.create(
                total_cost=0.01,
                references=[{'year': 2022, 'index': 'b_1'}, {'year': 2023, 'index': 'c_1'}],
                conversation=u1_c_t_2,
            )

        self.expected_context: Dict[str, Any] = {
            'year': self.year,
            'month': '07',
            #
            'log_in_count_total': 4,
            'log_in_count_month': 3,
            'log_out_count_total': 3,
            'log_out_count_month': 2,
            #
            'user_count_total': 4,
            'user_count_month': 3,
            'user_with_query_count_total': 2,
            'user_with_query_count_month': 2,
            #
            'cost_total': 0.10,
            'cost_month': 0.08,
            'cost_per_user_with_query_total': 0.10 / 2,
            'cost_per_user_with_query_month': 0.08 / 2,
            #
            'query_count_total': 10,
            'query_count_month': 8,
            'query_count_per_user_with_query_total': 5.0,
            'query_count_per_user_with_query_month': 4.0,
            'query_count_per_conversation_total': round(10 / 6, 2),
            'query_count_per_conversation_month': round(8 / 6, 2),
            #
            'text_search_query_proportion_total': round(6 / (6 + 4) * 100, 1),
            'text_search_query_proportion_month': round(5 / (5 + 3) * 100, 1),
            'document_search_query_proportion_total': round(4 / (6 + 4) * 100, 1),
            'document_search_query_proportion_month': round(3 / (5 + 3) * 100, 1),
            #
            'year_usage_total_counts': {2020: 3, 2021: 3, 2022: 10, 2023: 10, 2024: 6},
            'year_usage_month_counts': {2020: 2, 2021: 2, 2022: 8, 2023: 8, 2024: 4},
            'year_reference_total_counts': {2020: 2, 2021: 2, 2022: 6, 2023: 8, 2024: 2},
            'year_reference_month_counts': {2020: 1, 2021: 1, 2022: 5, 2023: 7, 2024: 2},
            #
            'dataset_usage_total_counts': {'a': 5, 'b': 5, 'c': 6},
            'dataset_usage_month_counts': {'a': 3, 'b': 5, 'c': 5},
            'dataset_reference_total_counts': {'a': 7, 'b': 6, 'c': 7},
            'dataset_reference_month_counts': {'a': 4, 'b': 6, 'c': 6},
            #
            'year_usage_total_graph_base_64': IsType(str),
            'year_usage_month_graph_base_64': IsType(str),
            'year_reference_total_graph_base_64': IsType(str),
            'year_reference_month_graph_base_64': IsType(str),
            #
            'dataset_usage_total_graph_base_64': IsType(str),
            'dataset_usage_month_graph_base_64': IsType(str),
            'dataset_reference_total_graph_base_64': IsType(str),
            'dataset_reference_month_graph_base_64': IsType(str),
        }

    def test_statistics_view(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.statistics_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_statistics_view_fails_because_not_admin(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.non_admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.statistics_endpoint_url, data=self.input_data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_statistics_view_fails_because_bad_input(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        input_data = self.input_data | {'year': 2023}

        response = self.client.post(self.statistics_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        input_data = self.input_data | {'year': 2030}

        response = self.client.post(self.statistics_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        input_data = self.input_data | {'month': 0}

        response = self.client.post(self.statistics_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        input_data = self.input_data | {'month': 13}

        response = self.client.post(self.statistics_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        input_data = {'year': 2024, 'month': 6}

        response = self.client.post(self.statistics_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        input_data = self.input_data | {'month': 9}

        response = self.client.post(self.statistics_endpoint_url, data=input_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_build_statistics_context(self) -> None:
        context = _build_statistics_context(self.year, self.month)
        self.assertEqual(context, self.expected_context)
