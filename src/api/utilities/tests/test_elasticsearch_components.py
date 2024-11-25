import uuid

from django.conf import settings
from rest_framework.exceptions import APIException
from rest_framework.test import APITestCase

from api.utilities.elastic import (
    ELASTIC_CONNECTION_ERROR_MESSAGE,
    ELASTIC_CONNECTION_TIMEOUT_MESSAGE,
    ElasticCore,
    ElasticKNN,
)
from api.utilities.testing import set_core_setting
from api.utilities.tests.test_settings import (
    BOTH_INDEX_EXPECTED_DOCUMENT_SET,
    BOTH_INDEXES_EXPECTED_HIT_COUNT,
    DOCUMENT_STRING,
    DOCUMENT_TEXT,
    DOCUMENT_TITLE,
    DOCUMENT_YEAR,
    EXPECTED_DOCUMENT_SUBSET,
    INDEX_1_EXPECTED_DOCUMENT_SET,
    INDEX_1_EXPECTED_HIT_COUNT,
    INDEX_2_EXPECTED_DOCUMENT_SET,
    INDEX_2_EXPECTED_HIT_COUNT,
    INDEX_NAME,
    INDEX_TEST_DOCUMENT_LIST,
    INDEX_TEST_INDEX_1_QUERY,
    INDEX_TEST_INDEX_2_QUERY,
    INDEX_TEST_INDEX_NAME_LIST,
    MAX_YEAR_ONLY_EXPECTED_DOCUMENT_SET,
    MAX_YEAR_ONLY_EXPECTED_HIT_COUNT,
    MAX_YEAR_ONLY_MIN_YEAR,
    MIDDLE_YEAR_ONLY_EXPECTED_DOCUMENT_SET,
    MIDDLE_YEAR_ONLY_EXPECTED_HIT_COUNT,
    MIDDLE_YEAR_ONLY_MAX_YEAR,
    MIDDLE_YEAR_ONLY_MIN_YEAR,
    MIN_YEAR_ONLY_EXPECTED_DOCUMENT_SET,
    MIN_YEAR_ONLY_EXPECTED_HIT_COUNT,
    MIN_YEAR_ONLY_MAX_YEAR,
    SEARCH_TEXT,
    TEXT_FIELD_NAME,
    TITLE_FIELD_NAME,
    URL_FIELD_NAME,
    VECTOR_FIELD_NAME,
    YEAR_FIELD_NAME,
    YEAR_TEST_DOCUMENT_LIST,
    YEAR_TEST_YEAR_LIST,
)
from api.utilities.vectorizer import Vectorizer
from core.models import CoreVariable

# pylint: disable=too-many-instance-attributes,too-many-arguments


class TestElasticsearchComponents(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.elastic_core = ElasticCore()

        # We wipe out all previous indices that have been created for the purpose of the test
        # because improper shutdowns etc may not reach tearDown and can cause stragglers.
        self.tearDown()

    def tearDown(self) -> None:  # pylint: disable=invalid-name
        self.elastic_core.elasticsearch.indices.delete(index=INDEX_NAME, ignore=[404])
        for index in INDEX_TEST_INDEX_NAME_LIST:
            self.elastic_core.elasticsearch.indices.delete(index=index, ignore=[404])

    def test_creating_index(self) -> None:
        response = self.elastic_core.create_index(INDEX_NAME, shards=1, replicas=0)
        self.assertEqual(response['acknowledged'], True)
        self.assertEqual(response['index'], INDEX_NAME)

    def test_errors_being_handled(self) -> None:
        try:
            set_core_setting('ELASTICSEARCH_URL', f'http://{uuid.uuid4().hex}:8888')
            ElasticCore().create_index(INDEX_NAME, shards=1, replicas=0)
        except APIException as exception:
            self.assertTrue(ELASTIC_CONNECTION_ERROR_MESSAGE in str(exception))

    def test_timeout_setting_being_respected(self) -> None:
        try:
            set_core_setting('ELASTICSEARCH_TIMEOUT', 0.001)
            ElasticCore().create_index(INDEX_NAME, shards=1, replicas=0)
        except APIException as exception:
            self.assertEqual(ELASTIC_CONNECTION_TIMEOUT_MESSAGE, str(exception))

    def _save_document(
        self,
        vectorizer: Vectorizer,
        index: str,
        text: str,
        title: str,
        url: str,
        year: int,
    ) -> str:
        # Save document to database
        document_id = uuid.uuid4().hex
        index_response = self.elastic_core.elasticsearch.index(
            index=index,
            id=document_id,
            document={
                TEXT_FIELD_NAME: text,
                TITLE_FIELD_NAME: title,
                URL_FIELD_NAME: url,
                YEAR_FIELD_NAME: year,
            },
        )
        self.assertEqual(index_response['result'], 'created')

        # Vectorize it and save the vector as well
        vector = vectorizer.vectorize([text])['vectors'][0]
        update_response = self.elastic_core.add_vector(
            index=index,
            vector=vector,
            document_id=document_id,
            field=VECTOR_FIELD_NAME,
        )
        self.assertEqual(update_response['result'], 'updated')

        return document_id

    def test_saving_and_searching_vectors(self) -> None:
        self.elastic_core.create_index(INDEX_NAME, shards=1, replicas=0)
        self.elastic_core.add_vector_mapping(index=INDEX_NAME, field=VECTOR_FIELD_NAME)

        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )

        # Add a document
        document_id = self._save_document(
            vectorizer,
            INDEX_NAME,
            DOCUMENT_TEXT,
            DOCUMENT_TITLE,
            DOCUMENT_STRING,
            DOCUMENT_YEAR,
        )

        # Check that the document exists in the expected form
        document = self.elastic_core.elasticsearch.get(index=INDEX_NAME, id=document_id)

        for key, expected_value in EXPECTED_DOCUMENT_SUBSET.items():
            self.assertEquals(document[key], expected_value)

        # Check that a query returns the document in the expected form
        search_vector = vectorizer.vectorize([SEARCH_TEXT])['vectors'][0]

        elastic_knn = ElasticKNN()
        search_response = elastic_knn.search_vector(vector=search_vector, indices=[INDEX_NAME])

        hits = search_response['hits']['hits']
        self.assertEqual(len(hits), 1)

        document = hits[0]
        for key, expected_value in EXPECTED_DOCUMENT_SUBSET.items():
            self.assertEquals(document[key], expected_value)

    def test_index_filtering(self) -> None:
        for index_name in INDEX_TEST_INDEX_NAME_LIST:
            self.elastic_core.create_index(index_name, shards=1, replicas=0)
            self.elastic_core.add_vector_mapping(index=index_name, field=VECTOR_FIELD_NAME)

        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )

        for index_number, index_name in enumerate(INDEX_TEST_INDEX_NAME_LIST):
            self._save_document(
                vectorizer,
                index_name,
                INDEX_TEST_DOCUMENT_LIST[index_number],
                '',
                '',
                2024,
            )

        search_vector = vectorizer.vectorize([SEARCH_TEXT])['vectors'][0]
        elastic_knn = ElasticKNN()

        # Check the set (ignoring ordering) of returned documents

        search_response = elastic_knn.search_vector(
            vector=search_vector, indices=[INDEX_TEST_INDEX_1_QUERY]
        )
        hits = search_response['hits']['hits']
        self.assertEqual(len(hits), INDEX_1_EXPECTED_HIT_COUNT)
        search_text_set = {hit['_source'][TEXT_FIELD_NAME] for hit in hits}
        self.assertEqual(search_text_set, INDEX_1_EXPECTED_DOCUMENT_SET)

        search_response = elastic_knn.search_vector(
            vector=search_vector, indices=[INDEX_TEST_INDEX_2_QUERY]
        )
        hits = search_response['hits']['hits']
        self.assertEqual(len(hits), INDEX_2_EXPECTED_HIT_COUNT)
        search_text_set = {hit['_source'][TEXT_FIELD_NAME] for hit in hits}
        self.assertEqual(search_text_set, INDEX_2_EXPECTED_DOCUMENT_SET)

        search_response = elastic_knn.search_vector(
            vector=search_vector, indices=[INDEX_TEST_INDEX_1_QUERY, INDEX_TEST_INDEX_2_QUERY]
        )
        hits = search_response['hits']['hits']
        self.assertEqual(len(hits), BOTH_INDEXES_EXPECTED_HIT_COUNT)
        search_text_set = {hit['_source'][TEXT_FIELD_NAME] for hit in hits}
        # Less texts returned than eligible
        self.assertTrue(search_text_set.issubset(BOTH_INDEX_EXPECTED_DOCUMENT_SET))

    def test_year_filtering(self) -> None:
        self.elastic_core.create_index(INDEX_NAME, shards=1, replicas=0)
        self.elastic_core.add_vector_mapping(index=INDEX_NAME, field=VECTOR_FIELD_NAME)

        vectorizer = Vectorizer(
            model_name=settings.VECTORIZATION_MODEL_NAME,
            system_configuration=settings.BGEM3_SYSTEM_CONFIGURATION,
            inference_configuration=settings.BGEM3_INFERENCE_CONFIGURATION,
            model_directory=settings.DATA_DIR,
        )

        for index_number, year in enumerate(YEAR_TEST_YEAR_LIST):
            self._save_document(
                vectorizer,
                INDEX_NAME,
                YEAR_TEST_DOCUMENT_LIST[index_number],
                '',
                '',
                year,
            )

        search_vector = vectorizer.vectorize([SEARCH_TEXT])['vectors'][0]
        elastic_knn = ElasticKNN()

        # Check the set (ignoring ordering) of returned documents

        search_query = ElasticKNN.create_date_query(min_year=MAX_YEAR_ONLY_MIN_YEAR)
        search_response = elastic_knn.search_vector(
            vector=search_vector, indices=[INDEX_NAME], search_query=search_query
        )
        hits = search_response['hits']['hits']
        self.assertEqual(len(hits), MAX_YEAR_ONLY_EXPECTED_HIT_COUNT)
        search_text_set = {hit['_source'][TEXT_FIELD_NAME] for hit in hits}
        self.assertEqual(search_text_set, MAX_YEAR_ONLY_EXPECTED_DOCUMENT_SET)

        search_query = ElasticKNN.create_date_query(max_year=MIN_YEAR_ONLY_MAX_YEAR)
        search_response = elastic_knn.search_vector(
            vector=search_vector, indices=[INDEX_NAME], search_query=search_query
        )
        hits = search_response['hits']['hits']
        self.assertEqual(len(hits), MIN_YEAR_ONLY_EXPECTED_HIT_COUNT)
        search_text_set = {hit['_source'][TEXT_FIELD_NAME] for hit in hits}
        self.assertEqual(search_text_set, MIN_YEAR_ONLY_EXPECTED_DOCUMENT_SET)

        search_query = ElasticKNN.create_date_query(
            min_year=MIDDLE_YEAR_ONLY_MIN_YEAR, max_year=MIDDLE_YEAR_ONLY_MAX_YEAR
        )
        search_response = elastic_knn.search_vector(
            vector=search_vector, indices=[INDEX_NAME], search_query=search_query
        )
        hits = search_response['hits']['hits']
        self.assertEqual(len(hits), MIDDLE_YEAR_ONLY_EXPECTED_HIT_COUNT)
        search_text_set = {hit['_source'][TEXT_FIELD_NAME] for hit in hits}
        self.assertEqual(search_text_set, MIDDLE_YEAR_ONLY_EXPECTED_DOCUMENT_SET)

    def test_that_when_year_query_exists_and_parents_dont_the_year_query_is_the_same(self) -> None:
        year_query = ElasticKNN.create_date_query(2000, 2024)
        self.assertTrue(year_query is not None)
        search_query = ElasticKNN.create_doc_id_query(year_query, set())
        self.assertEqual(search_query, year_query)

    def test_that_year_and_parent_query_being_empty_returns_none(self) -> None:
        year_query = ElasticKNN.create_date_query(None, None)
        self.assertEqual(year_query, None)
        search_query = ElasticKNN.create_doc_id_query(year_query, set())
        self.assertEqual(search_query, None)

    def test_parent_term_query_being_generated_on_empty_year_query(self) -> None:
        year_query = ElasticKNN.create_date_query(None, None)
        self.assertEqual(year_query, None)
        references = ['66554848489', '14549849865']
        search_query = ElasticKNN.create_doc_id_query(year_query, references)
        self.assertTrue(search_query is not None)
        restrictions = search_query['query']['bool']['should']  # type: ignore
        self.assertEqual(len(restrictions), len(references))

    def test_year_and_reference_querys_being_combined_under_a_must_restriction(self) -> None:
        references = ['66554848489', '14549849865', '41498498']
        min_year = 2000
        max_year = 2024
        year_field = CoreVariable.get_core_setting('ELASTICSEARCH_YEAR_FIELD')

        year_query = ElasticKNN.create_date_query(min_year, max_year)
        self.assertTrue(year_query is not None)
        search_query = ElasticKNN.create_doc_id_query(year_query, references)
        self.assertTrue(search_query is not None)

        restrictions = search_query['query']['bool']['must']  # type: ignore
        # One for the year range, the other for references.
        self.assertEqual(len(restrictions), 2)
        year_restrictions = [restriction for restriction in restrictions if 'range' in restriction]
        self.assertEqual(len(year_restrictions), 1)
        year_restriction = year_restrictions[0]
        self.assertEqual(year_restriction['range'][year_field]['gte'], min_year)
        self.assertEqual(year_restriction['range'][year_field]['lte'], max_year)

        reference_restrictions = [
            restriction for restriction in restrictions if 'bool' in restriction
        ]
        self.assertEqual(len(reference_restrictions), 1)
        reference_restriction = reference_restrictions[0]
        self.assertEqual(len(reference_restriction['bool']['should']), len(references))
