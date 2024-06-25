import uuid
from typing import Tuple

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.test import APITestCase

from api.utilities.elastic import (
    ELASTIC_CONNECTION_ERROR_MESSAGE,
    ELASTIC_CONNECTION_TIMEOUT_MESSAGE,
    ElasticCore,
)
from api.utilities.testing import set_core_setting
from api.utilities.vectorizer import Vectorizer


class TestElasticCore(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.index_name = 'test_ci_rk_vectors'
        self.vector_field_name = 'vector'

        # We wipe out all previous indices that have been created for the purpose of the test
        # because improper shutdowns etc may not reach tearDown and can cause stragglers.
        self.elastic_core = ElasticCore()
        self.elastic_core.elasticsearch.indices.delete(index=self.index_name, ignore=[404])

    def test_creating_index(self) -> None:
        response = self.elastic_core.create_index(self.index_name, shards=3, replicas=1)
        self.assertEqual(response['acknowledged'], True)
        self.assertEqual(response['index'], self.index_name)

    def _index_document_and_add_vector(self, text: str, vectorizer: Vectorizer) -> Tuple[str, dict]:
        document_id = uuid.uuid4().hex
        index_response = self.elastic_core.elasticsearch.index(
            index=self.index_name, id=document_id, document={'text': text}
        )
        self.assertEqual(index_response['result'], 'created')

        vector = vectorizer.vectorize([text])['vectors'][0]
        update_response = self.elastic_core.add_vector(
            index=self.index_name,
            vector=vector,
            document_id=document_id,
            field=self.vector_field_name,
        )
        self.assertEqual(update_response['result'], 'updated')

        return document_id, index_response

    def _check_document_integrity(self, document_id: str, text: str) -> None:
        # Let's check just in case the document follows the same integrity as expected.
        document = self.elastic_core.elasticsearch.get(index=self.index_name, id=document_id)
        self.assertTrue('text' in document['_source'] and document['_source']['text'] == text)
        self.assertTrue(self.vector_field_name in document['_source'])

    def test_errors_being_handled(self) -> None:
        try:
            set_core_setting('ELASTICSEARCH_URL', f'http://{uuid.uuid4().hex}:8888')
            ElasticCore().create_index(self.index_name, shards=3, replicas=1)
        except APIException as exception:
            self.assertEqual(ELASTIC_CONNECTION_ERROR_MESSAGE, str(exception))

    def test_timeout_setting_being_respected(self) -> None:
        try:
            set_core_setting('ELASTICSEARCH_TIMEOUT', 0.001)
            ElasticCore().create_index(self.index_name, shards=3, replicas=1)
        except APIException as exception:
            self.assertEqual(ELASTIC_CONNECTION_TIMEOUT_MESSAGE, str(exception))

    def test_that_adding_query_to_vector_limits_search_context(self) -> None:
        self.elastic_core.create_index(self.index_name, shards=1, replicas=0)
        self.elastic_core.add_vector_mapping(index=self.index_name, field=self.vector_field_name)
        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.MODEL_DIRECTORY,
        )

        # Add a document that we could search.
        text = 'Kas sa tahad öelda, et kookosed migreeruvad'
        document_id, _ = self._index_document_and_add_vector(text, vectorizer)

        self._check_document_integrity(document_id, text)

        self._index_document_and_add_vector('See on ainult lihas haav', vectorizer)
        self._index_document_and_add_vector(
            'Mingi märg eit kes loobib mõõku ei ole korralik alus valitsuse loomiseks!', vectorizer
        )

        search_vector = vectorizer.vectorize(['Miks sa tahad öelda, et kookosed migreeruvad'])[
            'vectors'
        ][0]
        search_response = self.elastic_core.search_vector(
            indices=self.index_name,
            search_query={'query': {'match': {'text': 'kookosed'}}},
            vector=search_vector,
            comparison_field=self.vector_field_name,
        )

        # Assert we only get a single hit with the query.
        hits = search_response['hits']['hits']
        self.assertTrue(len(hits) == 1)

        # Integrity check that without the query limitation we get more.
        search_response = self.elastic_core.search_vector(
            indices=self.index_name, vector=search_vector, comparison_field=self.vector_field_name
        )
        hits = search_response['hits']['hits']
        self.assertTrue(len(hits) > 1)

    def test_adding_vectors_and_searching_vectors(self) -> None:
        self.elastic_core.create_index(self.index_name, shards=1, replicas=0)
        self.elastic_core.add_vector_mapping(index=self.index_name, field=self.vector_field_name)
        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.MODEL_DIRECTORY,
        )

        # Add a document that we could search.
        text = 'Kas sa tahad öelda, et kookosed migreeruvad'
        document_id, _ = self._index_document_and_add_vector(text, vectorizer)

        self._check_document_integrity(document_id, text)

        search_vector = vectorizer.vectorize(['Miks sa tahad öelda, et kookosed migreeruvad'])[
            'vectors'
        ][0]
        search_response = self.elastic_core.search_vector(
            indices=self.index_name, vector=search_vector, comparison_field=self.vector_field_name
        )

        hits = search_response['hits']['hits']
        self.assertTrue(len(hits) > 0)
