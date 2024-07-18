import functools
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import elasticsearch_dsl
from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as ElasticsearchConnectionError
from elasticsearch import ConnectionTimeout, Elasticsearch, NotFoundError, RequestError
from elasticsearch_dsl import Search
from rest_framework import status
from rest_framework.exceptions import APIException

from api.utilities.core_settings import get_core_setting

logger = logging.getLogger(__name__)

MATCH_ALL_QUERY: Dict[str, Dict[str, dict]] = {'query': {'match_all': {}}}
ELASTIC_NOT_FOUND_MESSAGE = 'Could not find specified data from Elasticsearch!'
ELASTIC_REQUEST_ERROR_MESSAGE = 'Error executing Elasticsearch query! Bad query?'
ELASTIC_CONNECTION_TIMEOUT_MESSAGE = (
    'Connection to Elasticsearch took too long, please try again later!'
)
ELASTIC_AUTHENTICATION_ERROR_MESSAGE = 'Could not authenticate with Elasticsearch!'
ELASTIC_UNKNOWN_ERROR_MESSAGE = 'Unexpected error from Elasticsearch!'
ELASTIC_CONNECTION_ERROR_MESSAGE = (
    'Could not connect to Elasticsearch, is the location properly configured?'
)

K_DEFAULT = 3
NUM_CANDIDATES_DEFAULT = 25


def _elastic_connection(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except NotFoundError as exception:
            logger.exception(ELASTIC_NOT_FOUND_MESSAGE)
            raise APIException(ELASTIC_NOT_FOUND_MESSAGE) from exception

        except RequestError as exception:
            logger.exception(ELASTIC_REQUEST_ERROR_MESSAGE)
            raise APIException(ELASTIC_REQUEST_ERROR_MESSAGE) from exception

        except ConnectionTimeout as exception:
            logger.exception(ELASTIC_CONNECTION_TIMEOUT_MESSAGE)
            raise APIException(ELASTIC_CONNECTION_TIMEOUT_MESSAGE) from exception

        except AuthenticationException as exception:
            logger.exception(ELASTIC_AUTHENTICATION_ERROR_MESSAGE)
            raise APIException(ELASTIC_AUTHENTICATION_ERROR_MESSAGE) from exception

        # Important to set the ConnectionError to the bottom of the chain
        # as it's one of the superclasses the other exceptions inherit.
        except ElasticsearchConnectionError as exception:
            if exception.__context__ and 'timed out' in str(exception.__context__):
                # urllib3.exceptions.ConnectTimeoutError can cause an
                # elasticsearch.exceptions.ConnectionError,
                # but we'd like to treat timing out separately
                raise APIException(ELASTIC_CONNECTION_TIMEOUT_MESSAGE) from exception

            logger.exception(ELASTIC_CONNECTION_ERROR_MESSAGE)
            raise APIException(ELASTIC_CONNECTION_ERROR_MESSAGE) from exception

        except Exception as exception:
            logger.exception(ELASTIC_UNKNOWN_ERROR_MESSAGE)
            raise APIException(
                ELASTIC_UNKNOWN_ERROR_MESSAGE, code=status.HTTP_500_INTERNAL_SERVER_ERROR
            ) from exception

    return wrapper


class ElasticCore:
    def __init__(self, elasticsearch_url: Optional[str] = None, timeout: Optional[int] = None):
        self.timeout = timeout or get_core_setting('ELASTICSEARCH_TIMEOUT')
        self.elasticsearch_url = elasticsearch_url or get_core_setting('ELASTICSEARCH_URL')
        self.elasticsearch = Elasticsearch(self.elasticsearch_url, timeout=self.timeout)

    @_elastic_connection
    def check(self) -> bool:
        if self.elasticsearch.ping():
            return True
        return False

    @_elastic_connection
    def create_index(
        self,
        index_name: str,
        shards: int = 3,
        replicas: int = 1,
        settings: Optional[dict] = None,
        ignore: Tuple[int] = (400,),
    ) -> Dict:
        body = settings or {
            'number_of_shards': shards,
            'number_of_replicas': replicas,
        }
        return self.elasticsearch.indices.create(index=index_name, settings=body, ignore=ignore)

    @_elastic_connection
    def add_vector_mapping(
        self, index: str, field: str, body: Optional[dict] = None, dims: int = 1024
    ) -> Dict:
        mapping = body or {'properties': {field: {'type': 'dense_vector', 'dims': dims}}}
        return self.elasticsearch.indices.put_mapping(body=mapping, index=index)

    @_elastic_connection
    def add_vector(self, index: str, document_id: str, vector: List[float], field: str) -> Dict:
        return self.elasticsearch.update(
            index=index, id=document_id, body={'doc': {field: vector}}, refresh='wait_for'
        )

    @_elastic_connection
    def get_document_content(self, index: str, document_id: str) -> Dict:
        document = self.elasticsearch.get(index=index, id=document_id)
        text_field = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')
        text = document.body['_source'].get(text_field, '')
        return text

    def __str__(self) -> str:
        return self.elasticsearch_url


class ElasticKNN:
    def __init__(
        self,
        elasticsearch_url: Optional[str] = None,
        timeout: Optional[int] = None,
        field: Optional[str] = None,
    ):
        self.timeout = timeout or get_core_setting('ELASTICSEARCH_TIMEOUT')
        self.field = field or get_core_setting('ELASTICSEARCH_VECTOR_FIELD')
        self.elasticsearch_url = elasticsearch_url or get_core_setting('ELASTICSEARCH_URL')
        self.elasticsearch = Elasticsearch(self.elasticsearch_url, timeout=self.timeout)

    @staticmethod
    def create_date_query(
        min_year: Optional[int] = None, max_year: Optional[int] = None
    ) -> Optional[dict]:
        search = elasticsearch_dsl.Search()
        date_field = get_core_setting('ELASTICSEARCH_YEAR_FIELD')

        date_filter = {}
        if min_year is None and max_year is None:
            return None
        if min_year:
            date_filter['gte'] = min_year
        if max_year:
            date_filter['lte'] = max_year

        search = search.query('range', **{date_field: date_filter})
        return search.to_dict()

    def _apply_filter_to_knn(
        self, index_query: str, search_query: Optional[dict] = None
    ) -> Optional[dict]:
        if search_query:
            filter_search = Search(using=self.elasticsearch, index=index_query)
            filter_search.update_from_dict(search_query)
            # Applying some pre-filtering.
            # https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-knn-query.html#knn-query-filtering
            pre_knn_filter = filter_search.query.to_dict()
            return pre_knn_filter

        return None

    def _generate_knn_with_filter(
        self,
        vector: List[float],
        index_query: str,
        search_query: Optional[dict] = None,
        num_candidates: int = NUM_CANDIDATES_DEFAULT,
        k: int = K_DEFAULT,
    ) -> elasticsearch_dsl.Search:
        search = Search(using=self.elasticsearch, index=index_query)

        search_filter = self._apply_filter_to_knn(index_query, search_query)
        filter_kwargs = {'filter': search_filter} if search_filter else {}
        search = search.knn(
            field=self.field,
            k=k,
            num_candidates=num_candidates,
            query_vector=vector,
            **filter_kwargs
        )

        return search

    @_elastic_connection
    def search_vector(  # pylint: disable=too-many-arguments
        self,
        vector: List[float],
        index_queries: Optional[List[str]] = None,
        search_query: Optional[dict] = None,
        k: int = K_DEFAULT,
        num_candidates: int = NUM_CANDIDATES_DEFAULT,
        source: Optional[list] = None,
        size: Optional[int] = None,
    ) -> Dict:
        if index_queries is None:
            index_query = '*'
        else:
            index_query = ','.join(index_queries)

        # Define search interface
        search = self._generate_knn_with_filter(
            vector=vector,
            index_query=index_query,
            search_query=search_query,
            num_candidates=num_candidates,
            k=k,
        )

        # Which fields to include in case we want to save bandwidth (for the second workflow).
        if source:
            search = search.source(source)

        if size:
            search = search[:size]

        # Execute the query
        response = search.execute()
        return response

    def __str__(self) -> str:
        return self.elasticsearch_url
