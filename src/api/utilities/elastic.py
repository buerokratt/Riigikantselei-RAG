import functools
import logging
from typing import Any, Callable, Dict, List, Optional

from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as ElasticsearchConnectionError
from elasticsearch import ConnectionTimeout, Elasticsearch, NotFoundError, RequestError
from rest_framework import status
from rest_framework.exceptions import APIException, AuthenticationFailed, NotFound

from api.utilities.core_settings import get_core_setting

logger = logging.getLogger(__name__)

MATCH_ALL_QUERY: Dict[str, Dict[str, dict]] = {'query': {'match_all': {}}}
ELASTIC_NOT_FOUND_MESSAGE = 'Could not find specified data from Elasticsearch!'
ELASTIC_REQUEST_ERROR_MESSAGE = 'Could not connect to Elasticsearch!'
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

            connection_pool = getattr(exception.info, 'pool', None)
            uri = f'{connection_pool.host}:{connection_pool.port}' if connection_pool else None
            message = (
                f'{ELASTIC_CONNECTION_ERROR_MESSAGE} ({uri})'
                if uri
                else ELASTIC_CONNECTION_ERROR_MESSAGE
            )
            raise APIException(message) from exception

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
    def create_index(
        self, index_name: str, shards: int = 3, replicas: int = 1, settings: Optional[dict] = None
    ) -> Dict:
        body = settings or {
            'number_of_shards': shards,
            'number_of_replicas': replicas,
        }
        return self.elasticsearch.indices.create(index=index_name, settings=body, ignore=[400])

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
    def search_vector(
        self,
        indices: str,
        vector: List[float],
        comparison_field: str,
        search_query: Optional[dict] = None,
    ) -> Dict:
        if search_query is None:
            search_query = MATCH_ALL_QUERY

        query = {
            'query': {
                'script_score': {
                    **search_query,
                    'script': {
                        'source': (
                            f"cosineSimilarity(params.query_vector, '{comparison_field}')" ' + 1.0'
                        ),
                        'params': {'query_vector': vector},
                    },
                }
            }
        }

        response = self.elasticsearch.search(body=query, index=indices)
        return response

    def __str__(self) -> str:
        return self.elasticsearch_url
