import uuid

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.test import APITestCase

from api.utilities.core_settings import set_core_setting
from api.utilities.elastic import ElasticCore, ELASTIC_CONNECTION_TIMEOUT_MESSAGE, ELASTIC_CONNECTION_ERROR_MESSAGE
from api.utilities.vectorizer import Vectorizer


class TestElasticCore(APITestCase):

    def setUp(self):
        # We add a little bit randomness here to ensure we always test in a clean state.
        self.index_prefix = 'test_ci_rk_vectors_'
        self.index_name = self.index_prefix + uuid.uuid4().hex
        self.vector_field_name = 'vector'
        self.ec = ElasticCore()

    # We wipe out all indices that have been created for the purpose of the test because
    # improper shutdowns etc may not reach tearDown and can cause stagglers.
    def tearDown(self):
        self.ec.es.indices.delete(index=self.index_prefix + "*", ignore=[404])

    def test_creating_index(self):
        response = self.ec.create_index(self.index_name, shards=3, replicas=1)
        self.assertEqual(response["acknowledged"], True)
        self.assertEqual(response["index"], self.index_name)

    def _index_document_and_add_vector(self, text: str, vectorizer: Vectorizer):
        document_id = uuid.uuid4().hex
        index_response = self.ec.es.index(index=self.index_name, id=document_id, document={"text": text})
        self.assertEqual(index_response["result"], "created")

        vector = vectorizer.vectorize([text])["vectors"][0]
        update_response = self.ec.add_vector(index=self.index_name, vector=vector, document_id=document_id, field=self.vector_field_name)
        self.assertEqual(update_response["result"], "updated")

        return document_id, index_response

    def _check_document_integrity(self, document_id, text):
        # Let's check just in case the document follows the same integrity as expected.
        document = self.ec.es.get(index=self.index_name, id=document_id)
        self.assertTrue("text" in document["_source"] and document["_source"]["text"] == text)
        self.assertTrue(self.vector_field_name in document["_source"])

    def test_errors_being_handled(self):
        try:
            set_core_setting("ELASTICSEARCH_URL", f"http://{uuid.uuid4().hex}:8888")
            ElasticCore().create_index(self.index_name, shards=3, replicas=1)
        except APIException as e:
            self.assertEquals(ELASTIC_CONNECTION_ERROR_MESSAGE, str(e))

    def test_timeout_setting_being_respected(self):
        try:
            set_core_setting("ELASTICSEARCH_TIMEOUT", 0.001)
            ElasticCore().create_index(self.index_name, shards=3, replicas=1)
        except APIException as e:
            self.assertEqual(ELASTIC_CONNECTION_TIMEOUT_MESSAGE, str(e))

    def test_that_adding_query_to_vector_limits_search_context(self):
        self.ec.create_index(self.index_name, shards=1, replicas=0)
        self.ec.add_vector_mapping(index=self.index_name, field=self.vector_field_name)
        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.MODEL_DIRECTORY
        )

        # Add a document that we could search.
        text = "Kas sa tahad öelda, et kookosed migreeruvad"
        document_id, index_response = self._index_document_and_add_vector(text, vectorizer)

        self._check_document_integrity(document_id, text)

        self._index_document_and_add_vector("See on ainult lihas haav", vectorizer)
        self._index_document_and_add_vector("Mingi märg eit kes loobib mõõku ei ole korralik alus valistuse loomiseks!", vectorizer)

        search_vector = vectorizer.vectorize(["Miks sa tahad öelda, et kookosed migreeruvad"])["vectors"][0]
        search_response = self.ec.search_vector(indices=self.index_name, search_query={"query": {"match": {"text": "kookosed"}}}, vector=search_vector, comparison_field=self.vector_field_name)

        # Assert we only get a single hit with the query.
        hits = search_response["hits"]["hits"]
        self.assertTrue(len(hits) == 1)

        # Integrity check that without the query limitation we get more.
        search_response = self.ec.search_vector(indices=self.index_name, vector=search_vector, comparison_field=self.vector_field_name)
        hits = search_response["hits"]["hits"]
        self.assertTrue(len(hits) > 1)

    def test_adding_vectors_and_searching_vectors(self):
        self.ec.create_index(self.index_name, shards=1, replicas=0)
        self.ec.add_vector_mapping(index=self.index_name, field=self.vector_field_name)
        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.MODEL_DIRECTORY
        )

        # Add a document that we could search.
        text = "Kas sa tahad öelda, et kookosed migreeruvad"
        document_id, index_response = self._index_document_and_add_vector(text, vectorizer)

        self._check_document_integrity(document_id, text)

        search_vector = vectorizer.vectorize(["Miks sa tahad öelda, et kookosed migreeruvad"])["vectors"][0]
        search_response = self.ec.search_vector(indices=self.index_name, vector=search_vector, comparison_field=self.vector_field_name)

        hits = search_response["hits"]["hits"]
        self.assertTrue(len(hits) > 0)
