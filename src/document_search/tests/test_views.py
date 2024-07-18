from unittest import mock

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITransactionTestCase

from api.utilities.elastic import ElasticCore
from api.utilities.vectorizer import Vectorizer
from core.choices import TaskStatus
from document_search.tests.test_settings import DocumentSearchMockResponse
from user_profile.utilities import create_test_user_with_user_profile


# Create your tests here.
class DocumentSearchTestCase(APITransactionTestCase):

    def __index_test_dataset(self):

        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )

        for document in self.documents:
            document['vector'] = vectorizer.vectorize([document['text']])['vectors'][0]

        ec = ElasticCore()
        for document in self.documents:
            ec.create_index(document['index'])
            ec.add_vector_mapping(document['index'], field='vector')
            ec.elasticsearch.index(index=document['index'], body=document)

    def setUp(self):
        self.documents = [
            {
                'index': 'rk_test_index_1',
                'text': 'See on ainult lihashaav.',
                'year': 2022,
                'url': 'http://lihashaav.ee',
                'title': 'Lihashaavad ja nende roll ühiskonnas'
            },
            {
                'index': 'rk_test_index_2',
                'text': 'Kas sa tahad õelda, et kookused migreeruvad?',
                'year': 2019,
                'url': 'http://kookus.ee',
                'title': 'Migreeruvad kookused'
            }
        ]

        self.accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )

        self.conversation_uri = reverse('v1:document_search-list')

        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

    def tearDown(self):
        ec = ElasticCore()
        for document in self.documents:
            ec.elasticsearch.indices.delete(index=document['index'], ignore=[400, 404])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_workflow_of_adding_aggregations_and_chatting_working(self):
        self.__index_test_dataset()

        # Create the conversation which also creates the aggregations automatically.
        payload = {'user_input': 'Kuidas saab piim kookuse sisse?'}
        post_response = self.client.post(self.conversation_uri, data=payload)
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)

        # Get the response with detail since the immediate response doesn't include the
        # finished task state yet.
        conversation_pk = post_response.data['id']
        detail_uri = reverse('v1:document_search-detail', kwargs={'pk': conversation_pk})
        detail_response = self.client.get(detail_uri)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        # Check that the aggregation state is as expected.
        aggregations = detail_response.data['aggregation_result']['aggregations']
        task = detail_response.data['aggregation_result']['celery_task']
        self.assertTrue(len(aggregations) >= 2)
        self.assertTrue(aggregations[0]['count'] >= 1)
        self.assertEqual(task['status'], TaskStatus.SUCCESS)

        # Mock the chat process with ChatGPT and check for state.
        target_index = aggregations[0]['index']
        chat_uri = reverse('v1:document_search-chat', kwargs={'pk': conversation_pk})
        with mock.patch('document_search.tasks.ChatGPT.chat', return_value=DocumentSearchMockResponse()):
            chat_response = self.client.post(chat_uri, data={'index': target_index})
            self.assertEqual(chat_response.status_code, status.HTTP_200_OK)
            query_results = chat_response.data['query_results']
            self.assertEqual(len(query_results), 1)
            result = query_results[0]
            self.assertEqual(result['celery_task']['status'], TaskStatus.SUCCESS)
            self.assertEqual(len(result['references']), 1)

    def test_chatting_being_denied_when_overreaching_spending_limit(self):
        self.accepted_auth_user.user_profile.used_cost = 5000
        self.accepted_auth_user.user_profile.custom_usage_limit_euros = 1
        self.accepted_auth_user.user_profile.save()

        payload = {'user_input': 'Kuidas saab piim kookuse sisse?'}
        post_response = self.client.post(self.conversation_uri, data=payload)

        conversation_pk = post_response.data['id']
        chat_uri = reverse('v1:document_search-chat', kwargs={'pk': conversation_pk})

        response = self.client.post(chat_uri, data={'index': 'something_random'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_that_you_can_edit_the_title(self):
        input_text = 'kuidas saab piim kookuse sisse?'
        response = self.client.post(self.conversation_uri, data={"user_input": input_text})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Check that the title is changed to include a first big letter.
        self.assertNotEqual(response.data['user_input'], response.data['title'])
        self.assertEqual(response.data['title'][0], input_text[0].upper())

        conversation_id = response.data['id']
        detail_uri = reverse('v1:document_search-detail', kwargs={'pk': conversation_id})
        patched_title = 'KOOKUS'
        detail_response = self.client.patch(detail_uri, data={'title': patched_title})
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['title'], patched_title)
        self.assertNotEqual(detail_response.data['title'], detail_response.data['user_input'])
