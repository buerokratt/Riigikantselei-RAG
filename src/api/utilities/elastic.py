import functools
import logging
from typing import List, Optional

from elasticsearch import AuthenticationException
from elasticsearch import ConnectionError as ElasticsearchConnectionError
from elasticsearch import ConnectionTimeout, Elasticsearch, NotFoundError, RequestError
from rest_framework import status
from rest_framework.exceptions import APIException, AuthenticationFailed, NotFound

from api.utilities.core_settings import get_core_setting

logger = logging.getLogger('elastic_core')

MATCH_ALL_QUERY = {'query': {'match_all': {}}}
ELASTIC_NOT_FOUND_MESSAGE = 'Could not find specified data!'
ELASTIC_REQUEST_ERROR_MESSAGE = 'Could not connect to Elasticsearch!'
ELASTIC_CONNECTION_TIMEOUT_MESSAGE = (
    'Connection to Elasticsearch took too long, please try again later!'
)
ELASTIC_AUTHENTICATION_ERROR_MESSAGE = 'Could not authenticate with Elasticsearch!'
ELASTIC_UNKNOWN_ERROR_MESSAGE = 'Unexpected error from Elasticsearch!'
ELASTIC_CONNECTION_ERROR_MESSAGE = (
    'Could not connect to Elasticsearch, is the location properly configured?'
)


def elastic_connection(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except NotFoundError:
            logger.exception('Could not find Elasticsearch resource!')
            raise NotFound(ELASTIC_NOT_FOUND_MESSAGE)

        except RequestError:
            logger.exception(f'Could not connect to Elasticsearch!')
            raise APIException(ELASTIC_REQUEST_ERROR_MESSAGE)

        except ConnectionTimeout as e:
            logger.exception(
                'Connection to Elasticsearch timed out! '
                f'Info: {e.info}, '
                f'Status Code: {e.status_code}, '
                f'Error: {e.error}'
            )
            raise APIException(ELASTIC_CONNECTION_TIMEOUT_MESSAGE)

        except AuthenticationException:
            logger.exception('Could not authenticate Elasticsearch!')
            raise AuthenticationFailed(ELASTIC_AUTHENTICATION_ERROR_MESSAGE)

        # Important to set the ConnectionError to the bottom of the chain as it's one of the superclasses the other exceptions inherit.
        except ElasticsearchConnectionError as e:
            error_message = (
                f'{ELASTIC_CONNECTION_ERROR_MESSAGE} '
                f'Info: {e.info}, '
                f'Status Code: {e.status_code}, '
                f'Error: {e.error}'
            )
            logger.exception(error_message)
            raise APIException(ELASTIC_CONNECTION_ERROR_MESSAGE)

        except Exception:
            logger.exception('Unexpected exception occurred!')
            raise APIException(
                ELASTIC_UNKNOWN_ERROR_MESSAGE, code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return wrapper


class ElasticCore:
    def __init__(self, es_url: Optional[str] = None, timeout: Optional[int] = None):
        self.timeout = timeout or get_core_setting('ELASTICSEARCH_TIMEOUT')
        self.es_url = es_url or get_core_setting('ELASTICSEARCH_URL')
        self.es = Elasticsearch(self.es_url, timeout=self.timeout)

    @elastic_connection
    def create_index(
        self, index_name: str, shards: int = 3, replicas: int = 1, settings: Optional[dict] = None
    ):
        body = settings or {
            'number_of_shards': shards,
            'number_of_replicas': replicas,
        }
        return self.es.indices.create(index=index_name, settings=body, ignore=[400])

    @elastic_connection
    def add_vector_mapping(
        self, index: str, field: str, body: Optional[dict] = None, dims: int = 1024
    ):
        mapping = body or {'properties': {field: {'type': 'dense_vector', 'dims': dims}}}
        return self.es.indices.put_mapping(body=mapping, index=index)

    @elastic_connection
    def add_vector(self, index: str, document_id: str, vector: List[float], field: str):
        return self.es.update(
            index=index, id=document_id, body={'doc': {field: vector}}, refresh='wait_for'
        )

    @elastic_connection
    def search_vector(
        self,
        indices: str,
        vector: List[float],
        comparison_field: str,
        search_query: dict = MATCH_ALL_QUERY,
    ):
        query = {
            'query': {
                'script_score': {
                    **search_query,
                    'script': {
                        'source': f"cosineSimilarity(params.query_vector, '{comparison_field}') + 1.0",
                        'params': {'query_vector': vector},
                    },
                }
            }
        }

        response = self.es.search(body=query, index=indices)
        return response

    def __str__(self):
        return self.es_url
