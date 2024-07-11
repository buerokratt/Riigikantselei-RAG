import functools
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

import elasticsearch_dsl
from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as ElasticsearchConnectionError
from elasticsearch import ConnectionTimeout, Elasticsearch, NotFoundError, RequestError
from elasticsearch_dsl import Search
from rest_framework import status
from rest_framework.exceptions import APIException, AuthenticationFailed, NotFound

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


def _elastic_connection(func: Callable) -> Callable:
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except NotFoundError as exception:
            raise NotFound(ELASTIC_NOT_FOUND_MESSAGE) from exception

        except RequestError as exception:
            raise APIException(ELASTIC_REQUEST_ERROR_MESSAGE) from exception

        except ConnectionTimeout as exception:
            raise APIException(ELASTIC_CONNECTION_TIMEOUT_MESSAGE) from exception

        except AuthenticationException as exception:
            raise AuthenticationFailed(ELASTIC_AUTHENTICATION_ERROR_MESSAGE) from exception

        # Important to set the ConnectionError to the bottom of the chain
        # as it's one of the superclasses the other exceptions inherit.
        except ElasticsearchConnectionError as exception:
            if exception.__context__ and 'timed out' in str(exception.__context__):
                # urllib3.exceptions.ConnectTimeoutError can cause an
                # elasticsearch.exceptions.ConnectionError,
                # but we'd like to treat timing out separately
                raise APIException(ELASTIC_CONNECTION_TIMEOUT_MESSAGE) from exception

            raise APIException(ELASTIC_CONNECTION_ERROR_MESSAGE) from exception

        except Exception as exception:
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
            indices: str,
            elasticsearch_url: Optional[str] = None,
            timeout: Optional[int] = None,
            field: Optional[str] = None,
    ):
        self.indices = indices
        self.timeout = timeout or get_core_setting('ELASTICSEARCH_TIMEOUT')
        self.field = field or get_core_setting('ELASTICSEARCH_VECTOR_FIELD')
        self.elasticsearch_url = elasticsearch_url or get_core_setting('ELASTICSEARCH_URL')
        self.elasticsearch = Elasticsearch(self.elasticsearch_url, timeout=self.timeout)

    @staticmethod
    def create_date_query(min_year: Optional[int], max_year: Optional[int]) -> Optional[dict]:
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

    @_elastic_connection
    def knn_filter_and_aggregate(self, document_type_field: str, year_field: str, vector, search_query, num_candidates: int = 25, k: int = 5):
        search = self.generate_knn_with_filter(search_query, num_candidates, k, vector)
        search = search[0:0]  # We don't actually need any documents returned, just the aggregation.
        search.aggs.bucket("type_terms", "terms", field=f"{document_type_field}.keyword", size=100).bucket("dates", "stats", field=year_field)

        container = []
        response = search.execute()
        for hit in response.aggs.type_terms:
            hit = hit.to_dict()

            container.append(
                {
                    'document_type': hit["key"],
                    'count': hit["doc_count"],
                    'min_date': int(hit["dates"]["min"]),
                    'max_date': int(hit["dates"]["max"]),
                }
            )

        return container

    def generate_knn_with_filter(self, search_query: dict, vector: List[float], num_candidates: int = 20, k: int = 20, ) -> elasticsearch_dsl.Search:
        search = Search(using=self.elasticsearch, index=self.indices)

        if search_query:
            filter_search = Search(using=self.elasticsearch, index=self.indices)
            filter_search.update_from_dict(search_query)
            # Applying some pre-filtering.
            # https://www.elastic.co/guide/en/elasticsearch/reference/current/query-dsl-knn-query.html#knn-query-filtering
            pre_knn_filter = filter_search.query.to_dict()
            search = search.knn(
                field=self.field,
                k=k,
                num_candidates=num_candidates,
                query_vector=vector,
                filter=pre_knn_filter,
            )

        else:
            search = search.knn(
                field=self.field,
                k=k,
                num_candidates=num_candidates,
                query_vector=vector
            )

        return search

    @_elastic_connection
    def year_and_type_filter(self, year_field, document_type_field, document_type, min_year: Optional[int], max_year: Optional[int]):
        type_limitation = elasticsearch_dsl.Q("term", **{f"{document_type_field}.keyword": document_type})

        year_filter = {}
        if min_year:
            year_filter["gte"] = min_year
        if max_year:
            year_filter["lte"] = max_year

        year_limitation = elasticsearch_dsl.Q("range", **{year_field: year_filter})
        search = elasticsearch_dsl.Search(using=self.elasticsearch, index=self.indices)
        search = search.query(type_limitation & year_limitation)
        return search.to_dict()

    @_elastic_connection
    def search_vector(self, vector: List[float], search_query: Optional[dict] = None, k: int = 5, num_candidates: int = 25) -> Dict:
        # Define search interface
        search = self.generate_knn_with_filter(
            search_query=search_query,
            vector=vector,
            num_candidates=num_candidates,
            k=k
        )
        # Execute the query
        response = search.execute()
        return response

    def __str__(self) -> str:
        return self.elasticsearch_url
