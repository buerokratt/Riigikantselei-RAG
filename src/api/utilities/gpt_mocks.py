from typing import Any, Dict

MOCK_RESPONSE = 'Hello! How can I assist you today?'

MOCK_HEADERS = {
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

MOCK_RESPONSE_DICT: Dict[str, Any] = {
    'id': 'chatcmpl-9WkWmu5OQwhsYRJvFArNzDwlBuhAa',
    'choices': [
        {
            'finish_reason': 'stop',
            'index': 0,
            'logprobs': None,
            'message': {
                'content': MOCK_RESPONSE,
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

MOCK_STATUS_CODE = 200
