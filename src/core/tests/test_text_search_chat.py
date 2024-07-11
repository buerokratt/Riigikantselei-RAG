from typing import List, Tuple
from unittest import mock

from django.conf import settings
from django.test import override_settings
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.test import APITransactionTestCase

from api.utilities.core_settings import get_core_setting
from api.utilities.elastic import ElasticCore
from api.utilities.vectorizer import Vectorizer
from core.choices import TaskStatus
from core.models import Task, TextSearchConversation, TextSearchQueryResult
from core.tests.test_settings import (
    BASE_CREATE_INPUT,
    CONTINUE_CONVERSATION_INPUT,
    EQUAL_DATES_INPUT,
    FIRST_CONVERSATION_START_INPUT,
    INVALID_MAX_YEAR_INPUT,
    INVALID_MIN_YEAR_INPUT,
    INVALID_YEAR_DIFFERENCE_INPUT,
    FirstChatInConversationMockResults,
    SecondChatInConversationMockResults,
)
from user_profile.utilities import create_test_user_with_user_profile

# pylint: disable=invalid-name


# We use APITransactionTestCase here because we're running a Celery task chain synchronously.
class TestTextSearchChat(APITransactionTestCase):
    def _create_test_indices(self, indices: List[str]) -> None:
        core = ElasticCore()
        for index in indices:
            core.create_index(index, shards=1, replicas=1)
            core.add_vector_mapping(index, 'vector')

    def _clear_indices(self, indices: List[str]) -> None:
        core = ElasticCore()
        for index in indices:
            core.elasticsearch.indices.delete(index=index, ignore=[400, 404])

    def _create_chat_with_mock_gpt(self, chat_endpoint_url: str, data: dict) -> Response:
        """
        Helper for when you want to create TextSearchResults but without
        any of the time-consuming tasks,
        helpful for checking the formating of references, cost etc.

        Initially wanted to mock both gpt and vectorizer for speed reason
        but that for some reason just created reace conditions where
        the references werent stored in the object causing tests to fail.

        :param chat_endpoint_url: Which conversation instance to chat with.
        :param data: What payload (user_input) to send to the endpoint.
        :return: Response of the web-request sent using the test request factory.
        """
        mock_output = FirstChatInConversationMockResults()
        gpt_mock = mock.patch('core.tasks.ChatGPT.chat', return_value=mock_output)
        with gpt_mock:
            response = self.client.post(chat_endpoint_url, data=data)
            result = response.data['query_results'][0]
            response_status = result['celery_task']['status']
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response_status, TaskStatus.SUCCESS)
            return response

    def _create_vector_data(self, text: str, index: str, body: dict) -> None:
        ec = ElasticCore()
        ec.add_vector_mapping(index=index, field='vector')

        vector = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )

        vector = vector.vectorize([text])['vectors'][0]
        body['vector'] = vector
        body['text'] = text
        ec.elasticsearch.index(
            index=index,
            document=body,
        )

    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.create_endpoint_url = reverse('v1:text_search-list')

        self.allowed_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )
        self.allowed_auth_user_2 = create_test_user_with_user_profile(
            self, 'tester2', 'tester2@email.com', 'password', is_manager=False
        )

        self.not_allowed_auth_user = create_test_user_with_user_profile(
            self, 'tester3', 'tester3@email.com', 'password', is_manager=False
        )
        not_allowed_user_profile = self.not_allowed_auth_user.user_profile
        not_allowed_user_profile.is_allowed_to_spend_resources = False
        not_allowed_user_profile.save()

        self.indices = [
            'a_1',
            'a_2',
            'b',
            'c_1',
            'c_2',
        ]

    def tearDown(self) -> None:
        self._clear_indices(self.indices)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_chat_and_used_cost_and_usage_permission(self) -> None:
        self._create_test_indices(self.indices)

        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create conversation to start chatting.
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']
        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': conversation_id})

        # Assert used cost is solidly at 0.
        self.assertEqual(self.allowed_auth_user.user_profile.used_cost, 0.0)

        first_response = FirstChatInConversationMockResults()
        second_response = SecondChatInConversationMockResults()
        with mock.patch('core.tasks.ChatGPT.chat', return_value=first_response):
            # Start conversing with OpenAI
            response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
            results = response.data['query_results']
            first_celery_status = results[-1]['celery_task']['status']
            self.assertEqual(len(results), 1)
            self.assertEqual(first_celery_status, TaskStatus.SUCCESS)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        with mock.patch('core.tasks.ChatGPT.chat', return_value=second_response):
            # Continue the conversation.
            response = self.client.post(chat_endpoint_url, data=CONTINUE_CONVERSATION_INPUT)
            results = response.data['query_results']
            second_celery_status = results[-1]['celery_task']['status']
            self.assertEqual(second_celery_status, TaskStatus.SUCCESS)
            self.assertEqual(len(results), 2)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Retrieve the conversation instance.
        retrieve_endpoint_url = reverse('v1:text_search-detail', kwargs={'pk': conversation_id})
        response = self.client.get(retrieve_endpoint_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Used cost after communicating with the OpenAI API.
        expected_used_cost = first_response.total_cost + second_response.total_cost
        self.allowed_auth_user.user_profile.refresh_from_db()
        self.assertEqual(self.allowed_auth_user.user_profile.used_cost, expected_used_cost)

        # Ensure that with lower usage restrictions, an exception is thrown to the user.
        user_profile = self.allowed_auth_user.user_profile
        user_profile.custom_usage_limit_euros = expected_used_cost - 0.5
        user_profile.save()
        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_that_only_successful_results_are_passed_into_openai(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        conversation_id = response.data['id']

        failure_instance = TextSearchQueryResult.objects.create(
            conversation_id=conversation_id, user_input='Why are you like this?'
        )
        Task.objects.create(
            result=failure_instance, status=TaskStatus.FAILURE, error='Something went wrong!'
        )

        success_input = 'What is your purpose?'
        response_message = 'This is the OpenAPI response etc etc.'
        success_instance = TextSearchQueryResult.objects.create(
            conversation_id=conversation_id, user_input=success_input, response=response_message
        )
        Task.objects.create(result=success_instance, status=TaskStatus.SUCCESS)

        # Check the context that the conversation instance creates.
        conversation = TextSearchConversation.objects.get(pk=conversation_id)
        messages = conversation.messages
        # System message, question message for success, response message.
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]['content'], get_core_setting('OPENAI_SYSTEM_MESSAGE'))

        self.assertEqual(messages[1]['role'], 'user')
        self.assertEqual(messages[1]['content'], success_input)

        self.assertEqual(messages[2]['content'], response_message)
        self.assertEqual(messages[2]['role'], 'assistant')

    def test_that_min_and_max_year_validations_prevent_faulty_values(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Test normal creation.
        conversation_response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(conversation_response.status_code, status.HTTP_201_CREATED)

        # Check validation for max_year
        response = self.client.post(self.create_endpoint_url, data=INVALID_MAX_YEAR_INPUT)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check validation for min_year
        response = self.client.post(self.create_endpoint_url, data=INVALID_MIN_YEAR_INPUT)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check validation for min_year being bigger than max_year
        response = self.client.post(self.create_endpoint_url, data=INVALID_YEAR_DIFFERENCE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Check that equal dates go through normally.
        response = self.client.post(self.create_endpoint_url, data=EQUAL_DATES_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_chat_fails_because_not_authed(self) -> None:
        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_chat_fails_because_not_allowed(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.not_allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': 1})

        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_chat_fails_because_not_exists(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': 999})

        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_chat_fails_because_other_user(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.assertIn('id', response.data)
        conversation_id = response.data['id']

        # Set title
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': conversation_id})

        response = self.client.post(chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_conversation_fails_because_bad_document_types(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        # Create
        response = self.client.post(
            self.create_endpoint_url,
            data={
                'user_input': 'How does the jam get into the candy?',
                'min_year': 2000,
                'max_year': 2024,
                'document_types': ['test_xyz'],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_references_being_stored_inside_results_for_successful_rag(self) -> None:
        self._create_test_indices(self.indices)
        self._create_vector_data(
            text='Sega kõik kokku ja elu on hea noh!',
            index=self.indices[0],
            body={
                'url': 'http://eesti.ee',
                'title': 'Eesti iseseivuse saladused!',
                'year': 2024,
            },
        )

        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        conversation = self.client.post(self.create_endpoint_url, data=BASE_CREATE_INPUT)
        self.assertEqual(conversation.status_code, status.HTTP_201_CREATED)

        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': conversation.data['id']})

        index_category, _ = self.indices[0].split('_')

        openai_mock_response = FirstChatInConversationMockResults()
        with mock.patch('core.tasks.ChatGPT.chat', return_value=openai_mock_response):
            response = self.client.post(
                chat_endpoint_url,
                data={
                    'user_input': 'Millal Eesti iseseivus?',
                    'min_year': 2024,
                    'max_year': 2024,
                    'document_types': [index_category],
                },
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            references = response.data['query_results'][0]['references']
            self.assertEqual(len(references), 1)

            fields = ['url', 'title', 'elastic_id', 'index']
            reference = references[0]
            for field in fields:
                self.assertIn(field, reference)
                self.assertIsNotNone(reference.get(field, None))

            # Check that the reference to a document in elasticsearch is correct.
            ec = ElasticCore()
            hit = ec.elasticsearch.get(index=reference['index'], id=reference['elastic_id'])
            self.assertEqual(hit['_id'], reference['elastic_id'])

    # TODO: Temporarily disabling these two as they drive me insane, will reenable when
    # when creating a proper testing dataset for this.
    # @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    # def test_only_min_year_value_filters(self) -> None:
    #     self._create_test_indices(self.indices)
    #
    #     token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
    #     self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    #     ec = ElasticCore()
    #     index = self.indices[0]
    #     matching_year = 2012
    #
    #     ec.elasticsearch.index(
    #         index=index,
    #         body={
    #             'year': matching_year,
    #             'title': 'Kookus',
    #             'url': 'http://kookus.ee',
    #             'text': 'lorem',
    #         },
    #     )
    #     ec.elasticsearch.index(
    #         index=index,
    #         body={'year': 1995, 'title': 'Orange', 'url': 'http://orange.com', 'text': 'lorem'},
    #     )
    #
    #     _, chat_endpoint_url = self._create_conversation(
    #         uri=self.create_endpoint_url, data=MIN_YEAR_WITHOUT_MAX_INPUT
    #     )
    #     response = self._create_chat_with_mock_gpt(
    #         chat_endpoint_url=chat_endpoint_url, data={'user_input': 'Kuidas sai Eesti iseseivuse?'}
    #     )
    #
    #     references = response.data['query_results'][0]['references']
    #     self.assertEqual(len(references), 1)
    #     index = references[0]['index']
    #     elastic_id = references[0]['elastic_id']
    #     document = ec.elasticsearch.get(index=index, id=elastic_id)
    #     self.assertEqual(document['_source']['year'], matching_year)
    #
    # @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    # def test_only_max_year_value_filters(self) -> None:
    #     self._create_test_indices(self.indices)
    #
    #     token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
    #     self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
    #     ec = ElasticCore()
    #     index = self.indices[0]
    #     matching_year = 1995
    #
    #     # Index the faux data.
    #     ec.elasticsearch.index(
    #         index=index,
    #         body={'year': 2012, 'title': 'Kookus', 'url': 'http://kookus.ee', 'text': 'lorem'},
    #     )
    #     ec.elasticsearch.index(
    #         index=index,
    #         body={
    #             'year': matching_year,
    #             'title': 'Orange',
    #             'url': 'http://orange.com',
    #             'text': 'lorem',
    #         },
    #     )
    #
    #     # Create the conversation.
    #     _, chat_endpoint_url = self._create_conversation(
    #         uri=self.create_endpoint_url, data=MAX_YEAR_WITHOUT_MAX_INPUT
    #     )
    #     response = self._create_chat_with_mock_gpt(
    #         chat_endpoint_url=chat_endpoint_url, data={'user_input': 'Kuidas sai Eesti iseseivuse?'}
    #     )
    #
    #     # Check the references for their integrity.
    #     references = response.data['query_results'][0]['references']
    #     self.assertEqual(len(references), 1)
    #     index = references[0]['index']
    #     elastic_id = references[0]['elastic_id']
    #     document = ec.elasticsearch.get(index=index, id=elastic_id)
    #     self.assertEqual(document['_source']['year'], matching_year)

    def _create_conversation(self, uri: str, data: dict) -> Tuple[str, str]:
        # Create conversation to start chatting.
        response = self.client.post(uri, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        conversation_id = response.data['id']
        chat_endpoint_url = reverse('v1:text_search-chat', kwargs={'pk': conversation_id})
        return conversation_id, chat_endpoint_url

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_deleting_conversations_with_results(self) -> None:
        self._create_test_indices(self.indices)
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        conversation_id, chat_endpoint_url = self._create_conversation(
            uri=self.create_endpoint_url, data=BASE_CREATE_INPUT
        )

        response = self._create_chat_with_mock_gpt(
            chat_endpoint_url=chat_endpoint_url, data=FIRST_CONVERSATION_START_INPUT
        )
        results = response.data['query_results']
        first_celery_status = results[-1]['celery_task']['status']
        self.assertEqual(len(results), 1)
        self.assertEqual(first_celery_status, TaskStatus.SUCCESS)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Delete and assert nothing remains.
        delete_uri = reverse('v1:text_search-bulk-destroy')
        response = self.client.delete(delete_uri, data={'ids': [conversation_id]})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertFalse(TextSearchConversation.objects.filter(pk=conversation_id).exists())
        self.assertFalse(
            TextSearchQueryResult.objects.filter(conversation__id=conversation_id).exists()
        )

    def test_not_being_able_to_delete_other_users_conversations(self) -> None:
        # Create the first conversation which should be protected from deletion.
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        protected_conversation_id, _ = self._create_conversation(
            uri=self.create_endpoint_url, data=BASE_CREATE_INPUT
        )

        # User making the deletion.
        token, _ = Token.objects.get_or_create(user=self.allowed_auth_user_2)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        to_delete_conversation_id, _ = self._create_conversation(
            uri=self.create_endpoint_url, data=BASE_CREATE_INPUT
        )

        # Delete and assert that only one of them has been destroyed.
        delete_uri = reverse('v1:text_search-bulk-destroy')
        data = {'ids': [protected_conversation_id, to_delete_conversation_id]}
        response = self.client.delete(delete_uri, data=data)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(
            TextSearchConversation.objects.filter(pk=to_delete_conversation_id).exists()
        )
        self.assertTrue(
            TextSearchConversation.objects.filter(pk=protected_conversation_id).exists()
        )
