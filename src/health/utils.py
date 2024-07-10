# pylint: disable=bare-except,broad-exception-caught,wrong-import-order
import logging
import os
import pathlib
from typing import Optional
from urllib.parse import urlparse

import redis

from api.settings import BASE_DIR, CELERY_BROKER_URL
from api.utilities.core_settings import get_core_setting
from api.utilities.elastic import ElasticCore

logger = logging.getLogger(__name__)


def get_version() -> str:
    """
    Imports version number from file system.
    :return: version as string.
    """
    try:
        directory = pathlib.Path(BASE_DIR).parent
        with open(os.path.join(directory, 'VERSION'), 'r', encoding='utf8') as f_handle:
            version = f_handle.read().strip()
    except IOError:
        version = 'unknown'
    return version


def get_elastic_status(uri: Optional[str] = None) -> dict:
    """
    Checks Elasticsearch connection status and version.
    """
    es_url = uri or get_core_setting('ELASTICSEARCH_URL')
    es_info = {'alive': False, 'url': es_url}
    try:
        es_core = ElasticCore(es_url)
        if es_core.check():
            es_info['alive'] = True
        return es_info
    except:
        return es_info


def get_redis_status() -> dict:
    """
    Checks status of Redis server.
    """

    redis_status = {'alive': False, 'url': CELERY_BROKER_URL}

    try:
        parser = urlparse(CELERY_BROKER_URL)
        r_inst = redis.Redis(host=parser.hostname, port=parser.port, socket_timeout=3)
        r_inst.info()
        redis_status['alive'] = True
        return redis_status
    except Exception as error:
        logger.error(str(error))
        return redis_status
