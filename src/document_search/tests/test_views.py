from copy import deepcopy
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
from core.models import Dataset
from document_search.tests.test_settings import DocumentSearchMockResponse
from user_profile.utilities import create_test_user_with_user_profile

# pylint: disable=invalid-name

# TODO: copy tests from text_search, remove the irrelevant ones, add the document search-only ones.
#  Follow test_elasticsearch_components.py for Elastic usage.


class DocumentSearchTestCase(APITransactionTestCase):
    def _index_test_dataset(self) -> None:
        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )

        for document in self.documents:
            vectorization_result = vectorizer.vectorize([document['text']])  # type: ignore
            document['vector'] = vectorization_result['vectors'][0]

        # Lets do some funny business to avoid pointless vectorization
        extra_documents = deepcopy(self.documents)
        for count, extra_document in enumerate(extra_documents):
            extra_document['index'] = f'rk_duos_index_{count}'

        elastic_core = ElasticCore()
        for document in self.documents + extra_documents:
            elastic_core.create_index(document['index'])
            elastic_core.add_vector_mapping(document['index'], field='vector')
            elastic_core.elasticsearch.index(index=document['index'], body=document)

    def setUp(self) -> None:
        self.documents = [
            {
                'index': 'rk_test_index_1',
                'text': 'See on ainult lihashaav.',
                'year': 2022,
                'url': 'http://lihashaav.ee',
                'title': 'Lihashaavad ja nende roll ühiskonnas',
            },
            {
                'index': 'rk_test_index_2',
                'text': 'Kas sa tahad õelda, et kookused migreeruvad?',
                'year': 2019,
                'url': 'http://kookus.ee',
                'title': 'Migreeruvad kookused',
            },
        ]

        self.accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )

        self.conversation_uri = reverse('v1:document_search-list')

        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        Dataset(name='RK test', type='', index='rk_test_index_*', description='').save()
        Dataset(name='RK Duos', type='', index='rk_duos_index_*', description='').save()

    def tearDown(self) -> None:
        elastic_core = ElasticCore()
        for document in self.documents:
            elastic_core.elasticsearch.indices.delete(index=document['index'], ignore=[400, 404])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_workflow_of_adding_aggregations_and_chatting_working(self) -> None:
        self._index_test_dataset()

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
        # This checks that two separate indices under a common Dataset
        # are counted in one.
        self.assertTrue(aggregations[0]['count'] >= 2)
        self.assertEqual(task['status'], TaskStatus.SUCCESS)

        # Mock the chat process with ChatGPT and check for state.
        target_dataset_name = aggregations[0]['dataset_name']
        chat_uri = reverse('v1:document_search-chat', kwargs={'pk': conversation_pk})
        mock_path = 'document_search.tasks.ChatGPT.chat'
        with mock.patch(mock_path, return_value=DocumentSearchMockResponse()):
            chat_response = self.client.post(chat_uri, data={'dataset_name': target_dataset_name})
            self.assertEqual(chat_response.status_code, status.HTTP_200_OK)
            query_results = chat_response.data['query_results']
            self.assertEqual(len(query_results), 1)
            result = query_results[0]
            self.assertEqual(result['celery_task']['status'], TaskStatus.SUCCESS)
            self.assertEqual(len(result['references']), 3)

    def test_chatting_being_denied_when_overreaching_spending_limit(self) -> None:
        self.accepted_auth_user.user_profile.used_cost = 5000
        self.accepted_auth_user.user_profile.custom_usage_limit_euros = 1
        self.accepted_auth_user.user_profile.save()

        payload = {'user_input': 'Kuidas saab piim kookuse sisse?'}
        post_response = self.client.post(self.conversation_uri, data=payload)

        conversation_pk = post_response.data['id']
        chat_uri = reverse('v1:document_search-chat', kwargs={'pk': conversation_pk})

        response = self.client.post(chat_uri, data={'dataset_name': 'something_random'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_that_you_can_edit_the_title(self) -> None:
        input_text = 'kuidas saab piim kookuse sisse?'
        response = self.client.post(self.conversation_uri, data={'user_input': input_text})
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
