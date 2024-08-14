import uuid
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
from core.models import CoreVariable, Dataset
from document_search.models import DocumentSearchConversation, DocumentSearchQueryResult
from document_search.tasks import parse_aggregation
from document_search.tests.test_settings import (
    AGGREGATION_PARSING_AS_SEVERAL,
    AGGREGATION_PARSING_MULTIPLE_DOCS_AS_ONE,
    DocumentSearchMockResponse,
)
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
            extra_document['index'] = f'rk_duos_index_{uuid.uuid4().hex}_{count}'
            extra_document['doc_id'] = 'random random random doc_id'

        elastic_core = ElasticCore()
        for document in self.documents + extra_documents:
            elastic_core.create_index(document['index'])
            elastic_core.add_vector_mapping(document['index'], field='vector')
            elastic_core.elasticsearch.index(index=document['index'], body=document)

    def setUp(self) -> None:
        self.documents = [
            {
                'index': f'rk_test_index_{uuid.uuid4().hex}',
                'text': 'See on ainult lihashaav.',
                'year': 2022,
                'url': 'http://lihashaav.ee',
                'reference': 'Lihashaavad ja nende roll ühiskonnas',
                'doc_id': 'dakföafgakfafköl',
            },
            {
                'index': f'rk_test_index_{uuid.uuid4().hex}',
                'text': 'Kas sa tahad õelda, et kookused migreeruvad?',
                'year': 2019,
                'url': 'http://kookus.ee',
                'reference': 'Migreeruvad kookused',
                'doc_id': 'admöakmfdöamlköf',
            },
        ]

        self.accepted_auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )

        self.conversation_uri = reverse('v1:document_search-list')

        token, _ = Token.objects.get_or_create(user=self.accepted_auth_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        self.indices = [('RK test', 'rk_test_index_*'), ('RK Duos', 'rk_duos_index_*')]
        for dataset_name, index_pattern in self.indices:
            Dataset(name=dataset_name, type='', index=index_pattern, description='').save()

    def tearDown(self) -> None:
        elastic_core = ElasticCore()
        for _, index_pattern in self.indices:
            elastic_core.elasticsearch.indices.delete(index=index_pattern, ignore=[400, 404])

    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_workflow_of_adding_aggregations_and_chatting_working(self) -> None:
        self._index_test_dataset()

        # Create the conversation which also creates the aggregations automatically.
        user_input = 'Kuidas saab piim kookuse sisse?'
        payload = {'user_input': user_input}
        post_response = self.client.post(self.conversation_uri, data=payload)
        self.assertEqual(post_response.status_code, status.HTTP_201_CREATED)

        # Get the response with detail since the immediate response doesn't include the
        # finished task state yet.
        conversation_pk = post_response.data['id']
        detail_uri = reverse('v1:document_search-detail', kwargs={'pk': conversation_pk})
        detail_response = self.client.get(detail_uri)
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        # Check that min_year and max_year are set to null in the beginning.
        self.assertEqual(detail_response.data['min_year'], None)
        self.assertEqual(detail_response.data['max_year'], None)

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
        mock_path = 'core.mixins.ChatGPT.chat'
        max_year = 2023
        min_year = 2000
        with mock.patch(mock_path, return_value=DocumentSearchMockResponse()):
            chat_response = self.client.post(
                chat_uri,
                data={
                    'user_input': user_input,
                    'dataset_name': target_dataset_name,
                    'min_year': min_year,
                    'max_year': max_year,
                },
            )
            self.assertEqual(chat_response.status_code, status.HTTP_200_OK)
            self.assertEqual(chat_response.data['min_year'], min_year)
            self.assertEqual(chat_response.data['max_year'], max_year)
            query_results = chat_response.data['query_results']
            self.assertEqual(len(query_results), 1)
            result = query_results[0]
            self.assertEqual(result['dataset_name'], target_dataset_name)
            self.assertEqual(result['celery_task']['status'], TaskStatus.SUCCESS)
            self.assertEqual(len(result['references']), 5)

        # Delete and assert nothing remains.
        delete_uri = reverse('v1:document_search-bulk-destroy')
        response = self.client.delete(delete_uri, data={'ids': [conversation_pk]})
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        self.assertTrue(DocumentSearchConversation.objects.get(id=conversation_pk).is_deleted)
        self.assertTrue(
            DocumentSearchQueryResult.objects.filter(conversation__id=conversation_pk).exists()
        )

    def test_chatting_being_denied_when_overreaching_spending_limit(self) -> None:
        self.accepted_auth_user.user_profile.custom_usage_limit_euros = 0
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

        # Do the actual changing.
        conversation_id = response.data['id']
        detail_uri = reverse('v1:document_search-set-title', kwargs={'pk': conversation_id})
        patched_title = 'KOOKUS'
        detail_response = self.client.post(detail_uri, data={'title': patched_title})
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data, None)

    def test_aggregation_of_two_segments_from_same_document_counted_as_one(self) -> None:
        year_field = CoreVariable.get_core_setting('ELASTICSEARCH_YEAR_FIELD')

        aggregations = parse_aggregation(AGGREGATION_PARSING_MULTIPLE_DOCS_AS_ONE)
        self.assertEqual(len(aggregations), 1)
        aggregation = aggregations[0]
        self.assertEqual(aggregation['count'], 2)

        years = [
            document['_source'][year_field]  # type: ignore
            for document in AGGREGATION_PARSING_MULTIPLE_DOCS_AS_ONE
        ]
        self.assertEqual(aggregation['min_year'], min(years))
        self.assertEqual(aggregation['max_year'], max(years))

    def test_aggregation_of_three_segments_where_two_are_of_same_parent(self) -> None:
        aggregations = parse_aggregation(AGGREGATION_PARSING_AS_SEVERAL)
        self.assertEqual(len(aggregations), 2)
        # Since the assumption is they are sorted, we can bravely
        # just use indices
        self.assertEqual(aggregations[0]['count'], 2)
        self.assertEqual(aggregations[1]['count'], 1)
