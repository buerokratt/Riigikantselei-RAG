from typing import Any, Dict

from api.utilities.core_settings import get_core_setting
from api.utilities.testing import IsType

# GPT

GPT_HEADERS = {
    'date': 'Wed, 05 Jun 2024 12:59:36 GMT',
    'content-type': 'application/json',
    'transfer-encoding': 'chunked',
    'connection': 'keep-alive',
    'openai-organization': 'texta-o',
    'openai-processing-ms': '500',
    'openai-version': '2020-10-01',
    'strict-transport-security': 'max-age=15724800; includeSubDomains',
    'x-ratelimit-limit-requests': '500',
    'x-ratelimit-limit-tokens': '30000',
    'x-ratelimit-remaining-requests': '499',
    'x-ratelimit-remaining-tokens': '29972',
    'x-ratelimit-reset-requests': '120ms',
    'x-ratelimit-reset-tokens': '56ms',
    'x-request-id': 'req_b74e6ad94b04367098b39f1c3acf54b2',
    'cf-cache-status': 'DYNAMIC',
    'set-cookie': (
        '__cf_bm=LDZOZXQfvCDzOrqomiWkkMMZ4eqrPsvPSpM2M9NYKZs-1717592376-1.0.1.1-60MKAcfYU'
        'o50.hDcIfIfgz8zR4psKcCnGCMwGyOBWwJv1OgmRUHEuL4puwiuUb_2JeMy3d_fn0fvmKsxKxXmbA; '
        'path=/; '
        'expires=Wed, 05-Jun-24 13:29:36 GMT; '
        'domain=.api.openai.com; '
        'HttpOnly; '
        'Secure; '
        'SameSite=None, '
        '_cfuvid=_9iq19utMBYd3JjR8OQZ2OVFHI16qkFU4GPF6FLNSRo-1717592376822-0.0.1.1-'
        '604800000; '
        'path=/; '
        'domain=.api.openai.com; '
        'HttpOnly; '
        'Secure; '
        'SameSite=None'
    ),
    'server': 'cloudflare',
    'cf-ray': '88f0573e1a507125-TLL',
    'content-encoding': 'gzip',
    'alt-svc': 'h3=":443"; ma=86400',
}

GPT_RESPONSE = 'Hello! How can I assist you today?'

GPT_RESPONSE_DICT: Dict[str, Any] = {
    'id': 'chatcmpl-9WkWmu5OQwhsYRJvFArNzDwlBuhAa',
    'choices': [
        {
            'finish_reason': 'stop',
            'index': 0,
            'logprobs': None,
            'message': {
                'content': GPT_RESPONSE,
                'role': 'assistant',
            },
        }
    ],
    'created': 1717592376,
    'model': 'gpt-4o-2024-05-13',
    'object': 'chat.completion',
    'system_fingerprint': 'fp_319be4768e',
    'usage': {'completion_tokens': 9, 'prompt_tokens': 20, 'total_tokens': 29},
}

GPT_STATUS_CODE = 200

# Elastic

INDEX_NAME = 'test_index'
SEARCH_TEXT = 'Search text'

VECTOR_FIELD_NAME = get_core_setting('ELASTICSEARCH_VECTOR_FIELD')
TEXT_FIELD_NAME = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')
TITLE_FIELD_NAME = get_core_setting('ELASTICSEARCH_TITLE_FIELD')
URL_FIELD_NAME = get_core_setting('ELASTICSEARCH_URL_FIELD')
YEAR_FIELD_NAME = get_core_setting('ELASTICSEARCH_YEAR_FIELD')
DATASET_NAME_FIELD_NAME = get_core_setting('ELASTICSEARCH_DATASET_NAME_FIELD')

DOCUMENT_TEXT = 'Text string'
DOCUMENT_TITLE = 'title_string'
DOCUMENT_STRING = 'url_string'
DOCUMENT_YEAR = 2024
DOCUMENT_DATASET_NAME = 'Dataset string'

EXPECTED_DOCUMENT_SUBSET = {
    '_index': INDEX_NAME,
    '_source': {
        TEXT_FIELD_NAME: DOCUMENT_TEXT,
        VECTOR_FIELD_NAME: IsType(list),
        TITLE_FIELD_NAME: DOCUMENT_TITLE,
        URL_FIELD_NAME: DOCUMENT_STRING,
        YEAR_FIELD_NAME: DOCUMENT_YEAR,
        DATASET_NAME_FIELD_NAME: DOCUMENT_DATASET_NAME,
    },
}

# Elastic - index filtering

INDEX_TEST_INDEX_1_QUERY = 'test_index_1_*'
INDEX_TEST_INDEX_2_QUERY = 'test_index_2_*'
INDEX_TEST_INDEX_NAME_LIST = [
    'test_index_1_a',
    'test_index_1_b',
    'test_index_2_a',
    'test_index_2_b',
]
INDEX_TEST_DOCUMENT_LIST = [
    f'Document that lives in {index}' for index in INDEX_TEST_INDEX_NAME_LIST
]

INDEX_1_EXPECTED_DOCUMENT_SET = {INDEX_TEST_DOCUMENT_LIST[0], INDEX_TEST_DOCUMENT_LIST[1]}
INDEX_2_EXPECTED_DOCUMENT_SET = {INDEX_TEST_DOCUMENT_LIST[2], INDEX_TEST_DOCUMENT_LIST[3]}
BOTH_INDEX_EXPECTED_DOCUMENT_SET = INDEX_1_EXPECTED_DOCUMENT_SET | INDEX_2_EXPECTED_DOCUMENT_SET

INDEX_1_EXPECTED_HIT_COUNT = 2
INDEX_2_EXPECTED_HIT_COUNT = 2
# 4 eligible, but we only return 3
BOTH_INDEXES_EXPECTED_HIT_COUNT = 3

# Elastic - year filtering

YEAR_TEST_YEAR_LIST = [2021, 2022, 2023]
YEAR_TEST_DOCUMENT_LIST = [f'Document that is from year {year}' for year in YEAR_TEST_YEAR_LIST]

MAX_YEAR_ONLY_MIN_YEAR = 2023
MIN_YEAR_ONLY_MAX_YEAR = 2021
MIDDLE_YEAR_ONLY_MIN_YEAR = 2022
MIDDLE_YEAR_ONLY_MAX_YEAR = 2022

MAX_YEAR_ONLY_EXPECTED_HIT_COUNT = 1
MIN_YEAR_ONLY_EXPECTED_HIT_COUNT = 1
MIDDLE_YEAR_ONLY_EXPECTED_HIT_COUNT = 1

MAX_YEAR_ONLY_EXPECTED_DOCUMENT_SET = {YEAR_TEST_DOCUMENT_LIST[2]}
MIN_YEAR_ONLY_EXPECTED_DOCUMENT_SET = {YEAR_TEST_DOCUMENT_LIST[0]}
MIDDLE_YEAR_ONLY_EXPECTED_DOCUMENT_SET = {YEAR_TEST_DOCUMENT_LIST[1]}
