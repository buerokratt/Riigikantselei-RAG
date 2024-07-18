from typing import Dict

from api.utilities.core_settings import get_core_setting


class DocumentSearchMockResponse:
    RESPONSE: Dict[str, object] = {
        'model': 'gpt-4o-2024-05-13',
        'user_input': 'Kuidas saab piim kookuse sisse?',
        'response': 'Kas sa tahad öelda, et kookospähklid rändavad?',
        'input_tokens': 61,
        'output_tokens': 17,
        'total_cost': 0.0005600000000000001,
        'response_headers': {
            'date': 'Tue, 02 Jul 2024 16:35:30 GMT',
            'content-type': 'application/json',
            'transfer-encoding': 'chunked',
            'connection': 'keep-alive',
            'openai-organization': 'texta-o',
            'openai-processing-ms': '6661',
            'openai-version': '2020-10-01',
            'strict-transport-security': 'max-age=31536000; includeSubDomains',
            'x-ratelimit-limit-requests': '500',
            'x-ratelimit-limit-tokens': '30000',
            'x-ratelimit-remaining-requests': '499',
            'x-ratelimit-remaining-tokens': '29889',
            'x-ratelimit-reset-requests': '120ms',
            'x-ratelimit-reset-tokens': '222ms',
            'x-request-id': 'req_72a6017ec7fa658bd0783cbdb1d130ed',
            'cf-cache-status': 'DYNAMIC',
            'set-cookie': '...',
            'server': 'cloudflare',
            'cf-ray': '89d00c754c47abed-TLL',
            'content-encoding': 'gzip',
            'alt-svc': 'h3=":443"; ma=86400',
        },
    }
    headers = RESPONSE['response_headers']
    input_tokens = RESPONSE['input_tokens']
    message = RESPONSE['response']
    model = RESPONSE['model']
    response_tokens = RESPONSE['output_tokens']

    @property
    def total_cost(self) -> float:
        return self.input_tokens * get_core_setting(
            'EURO_COST_PER_INPUT_TOKEN'
        ) + self.response_tokens * get_core_setting('EURO_COST_PER_OUTPUT_TOKEN')
