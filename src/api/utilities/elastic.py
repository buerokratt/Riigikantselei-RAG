import functools
import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import elasticsearch_dsl
from django.utils.translation import gettext as _
from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as ElasticsearchConnectionError
from elasticsearch import ConnectionTimeout, Elasticsearch, NotFoundError, RequestError
from elasticsearch_dsl import Search
from elasticsearch_dsl.response import Response
from rest_framework import status
from rest_framework.exceptions import APIException

from core.models import CoreVariable

logger = logging.getLogger(__name__)

MATCH_ALL_QUERY: Dict[str, Dict[str, dict]] = {'query': {'match_all': {}}}
ELASTIC_NOT_FOUND_MESSAGE = _('Could not find specified data from Elasticsearch!')
ELASTIC_REQUEST_ERROR_MESSAGE = _('Error executing Elasticsearch query! Bad query?')
ELASTIC_CONNECTION_TIMEOUT_MESSAGE = _(
    'Connection to Elasticsearch took too long, please try again later!'
)
ELASTIC_AUTHENTICATION_ERROR_MESSAGE = _('Could not authenticate with Elasticsearch!')
ELASTIC_UNKNOWN_ERROR_MESSAGE = _('Unexpected error from Elasticsearch!')
ELASTIC_CONNECTION_ERROR_MESSAGE = _(
    'Could not connect to Elasticsearch, is the location properly configured?'
)

K_DEFAULT = 5
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
        self.timeout = timeout or CoreVariable.get_core_setting('ELASTICSEARCH_TIMEOUT')
        self.elasticsearch_url = elasticsearch_url or CoreVariable.get_core_setting(
            'ELASTICSEARCH_URL'
        )
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
        text_field = CoreVariable.get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')
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
        self.timeout = timeout or CoreVariable.get_core_setting('ELASTICSEARCH_TIMEOUT')
        self.field = field or CoreVariable.get_core_setting('ELASTICSEARCH_VECTOR_FIELD')
        self.elasticsearch_url = elasticsearch_url or CoreVariable.get_core_setting(
            'ELASTICSEARCH_URL'
        )
        self.elasticsearch = Elasticsearch(self.elasticsearch_url, timeout=self.timeout)

    @staticmethod
    def create_date_query(
        min_year: Optional[int] = None, max_year: Optional[int] = None
    ) -> Optional[dict]:
        search = elasticsearch_dsl.Search()
        date_field = CoreVariable.get_core_setting('ELASTICSEARCH_YEAR_FIELD')

        date_filter = {}
        if min_year is None and max_year is None:
            return None
        if min_year:
            date_filter['gte'] = min_year
        if max_year:
            date_filter['lte'] = max_year

        search = search.query('range', **{date_field: date_filter})
        return search.to_dict()

    @staticmethod
    def create_doc_id_query(
        search_query: Optional[dict], parent_references: Iterable[str]
    ) -> Optional[dict]:
        if search_query and not parent_references:
            return search_query

        if search_query is None and not parent_references:
            return None

        parent_field = CoreVariable.get_core_setting('ELASTICSEARCH_PARENT_FIELD')
        doc_id_restriction = [
            elasticsearch_dsl.Q('term', **{parent_field: reference})
            for reference in parent_references
        ]
        parent_query = elasticsearch_dsl.Q('bool', should=doc_id_restriction)

        if search_query:
            search_wrapper = elasticsearch_dsl.Search.from_dict(search_query)
            previous_query = elasticsearch_dsl.Q(search_wrapper.query)
            query = elasticsearch_dsl.Q('bool', must=[parent_query, previous_query])
            return elasticsearch_dsl.Search().query(query).to_dict()

        search_wrapper = elasticsearch_dsl.Search()
        return search_wrapper.query(parent_query).to_dict()

    def _apply_filter_to_knn(
        self, index: str, search_query: Optional[dict] = None
    ) -> Optional[dict]:
        if search_query:
            filter_search = Search(using=self.elasticsearch, index=index)
            filter_search.update_from_dict(search_query)
            # Applying some pre-filtering.
            # https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-knn-query.html#knn-query-filtering
            pre_knn_filter = filter_search.query.to_dict()
            return pre_knn_filter

        return None

    def _generate_knn_with_filter(
        self,
        vector: List[float],
        indices: str,
        search_query: Optional[dict] = None,
        num_candidates: int = NUM_CANDIDATES_DEFAULT,
        k: int = K_DEFAULT,
    ) -> elasticsearch_dsl.Search:
        search = Search(using=self.elasticsearch, index=indices)

        search_filter = self._apply_filter_to_knn(indices, search_query)
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
        indices: Optional[List[str]] = None,
        search_query: Optional[dict] = None,
        k: int = K_DEFAULT,
        num_candidates: int = NUM_CANDIDATES_DEFAULT,
        source: Optional[list] = None,
        size: Optional[int] = None,
    ) -> Response:
        if indices is None:
            indices_str = '*'
        else:
            indices_str = ','.join(indices)

        # Define search interface
        search = self._generate_knn_with_filter(
            vector=vector,
            indices=indices_str,
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
