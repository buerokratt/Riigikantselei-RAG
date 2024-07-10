import logging
import pathlib
from urllib.parse import urlparse
import redis
import os

from api.utilities.elastic import ElasticCore
from api.utilities.core_settings import get_core_setting
from api.settings import BASE_DIR, CELERY_BROKER_URL


logger = logging.getLogger(__name__)


def get_version():
    """
    Imports version number from file system.
    :return: version as string.
    """
    try:
        dir = pathlib.Path(BASE_DIR).parent
        with open(os.path.join(dir, 'VERSION'), 'r') as fh:
            version = fh.read().strip()
    except IOError:
        version = 'unknown'
    return version



def get_elastic_status(uri=None):
    """
    Checks Elasticsearch connection status and version.
    """
    es_url = uri or get_core_setting("ELASTICSEARCH_URL")
    es_info = {"alive": False, "url": es_url}
    try:
        es_core = ElasticCore(es_url)
        if es_core.check():
            es_info["alive"] = True
        return es_info
    except:
        return es_info


def get_redis_status():
    """
    Checks status of Redis server.
    """

    redis_status = {"alive": False, "url": CELERY_BROKER_URL}

    try:
        parser = urlparse(CELERY_BROKER_URL)
        r = redis.Redis(host=parser.hostname, port=parser.port, socket_timeout=3)
        info = r.info()
        redis_status["alive"] = True
        return redis_status
    except Exception as e:
        logger.error(str(e))
        return redis_status
