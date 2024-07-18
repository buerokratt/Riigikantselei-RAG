import datetime
from typing import Dict

from api.utilities.core_settings import get_core_setting

BASE_CREATE_INPUT = {
    'user_input': 'Eesti iseseisvus',
    'min_year': 2020,
    'max_year': 2024,
    'indices': ['a_1'],
}

MIN_YEAR_WITHOUT_MAX_INPUT = {
    'user_input': 'How does the jam get into the candy?',
    'min_year': 2000,
}

MAX_YEAR_WITHOUT_MAX_INPUT = {
    'user_input': 'How does the jam get into the candy?',
    'max_year': 2000,
}

NO_DATE_RANGE_INPUT = {
    'user_input': 'How does the jam get into the candy?',
    'indices': ['a_1', 'a_2'],
}

FIRST_CONVERSATION_START_INPUT = {
    'user_input': 'Kuidas sai Eesti iseseivuse?',
    'indices': ['a_1', 'a_2'],
}

INVALID_MIN_YEAR_INPUT = {
    'min_year': datetime.datetime.now().year + 1,
    'max_year': 2024,
    'indices': ['a_1'],
    'user_input': 'Kuidas sai Eesti iseseivuse?',
}

INVALID_MAX_YEAR_INPUT = {
    'min_year': 2020,
    'max_year': datetime.datetime.now().year + 1,
    'indices': ['a_1'],
    'user_input': 'Kuidas sai Eesti iseseivuse?',
}

# Min year should not be bigger than max year.
INVALID_YEAR_DIFFERENCE_INPUT = {
    'min_year': 2024,
    'max_year': 2020,
    'indices': ['a_1'],
    'user_input': 'Kuidas sai Eesti iseseivuse?',
}

EQUAL_DATES_INPUT = {
    'min_year': 2024,
    'max_year': 2024,
    'indices': ['a_1'],
    'user_input': 'Kuidas sai Eesti iseseivuse?',
}

CONTINUE_CONVERSATION_INPUT = {
    'min_year': 2022,
    'max_year': 2023,
    'indices': ['a_1'],
    'user_input': 'Ok, aga anna siis infot Läti iseseivuse kohta.',
}

MIN_AND_MAX_YEAR_FUNCTIONALITY_INPUTS = {
    'user_input': 'Fruit migration',
    'min_year': 2021,
    'max_year': 2024,
    'indices': ['a_1'],
}


class FirstChatInConversationMockResults:
    RESPONSE: Dict[str, object] = {
        'model': 'gpt-4o-2024-05-13',
        'min_year': 2020,
        'max_year': 2024,
        'indices': 'a,c',
        'user_input': 'Kuidas sai Eesti iseseivuse?',
        'response': 'Vabandust, aga paistab, et konteksti ei ole antud. '
        'Kui annate mulle vajaliku teabe või konteksti, '
        'vastan rõõmuga teie küsimusele Eesti iseseisvuse kohta.',
        'input_tokens': 47,
        'output_tokens': 49,
        'total_cost': 0.0009699999999999999,
        'response_headers': {
            'date': 'Tue, 02 Jul 2024 16:25:27 GMT',
            'content-type': 'application/json',
            'transfer-encoding': 'chunked',
            'connection': 'keep-alive',
            'openai-organization': 'texta-o',
            'openai-processing-ms': '1182',
            'openai-version': '2020-10-01',
            'strict-transport-security': 'max-age=31536000; includeSubDomains',
            'x-ratelimit-limit-requests': '500',
            'x-ratelimit-limit-tokens': '30000',
            'x-ratelimit-remaining-requests': '499',
            'x-ratelimit-remaining-tokens': '29942',
            'x-ratelimit-reset-requests': '120ms',
            'x-ratelimit-reset-tokens': '116ms',
            'x-request-id': 'req_41d025b36784c6a22bfaab1ff47fa7f5',
            'cf-cache-status': 'DYNAMIC',
            'set-cookie': '...',
            'server': 'cloudflare',
            'cf-ray': '89cffddf2e3c5432-TLL',
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


class SecondChatInConversationMockResults:
    RESPONSE: Dict[str, object] = {
        'model': 'gpt-4o-2024-05-13',
        'min_year': 2022,
        'max_year': 2023,
        'indices': 'a,c',
        'user_input': 'Ok, aga anna siis infot Läti iseseivuse kohta.',
        'response': 'Läti iseseisvusprotsess on tihedalt seotud Esimese '
        'maailmasõja ja Vene impeeriumi lagunemisega.'
        '\n\n1. **Esimene maailmasõda ja Vene impeeriumi lagunemine:**\n   '
        '- 1917. aastal toimus Venemaal Oktoobrirevolutsioon, mis viis '
        'Vene impeeriumi kokkuvarisemiseni'
        ' ja bolševike võimuletulekuni.\n   - Selle tulemusena tekkisid '
        'võimalused erinevate rahvaste '
        'iseseisvuspüüdlusteks.\n\n2. **Iseseisvusdeklaratsioon:**\n   - '
        '18. novembril 1918 kuulutas '
        'Läti Rahvanõukogu Riias välja Läti iseseisvuse. See kuupäev '
        'tähistab Läti Vabariigi asutamist.\n\n3. '
        '**Vabadussõda:**\n   - Pärast iseseisvuse väljakuulutamist '
        'pidid läti rahvuslikud jõud võitlema nii '
        'Saksamaa kui ka Nõukogude Venemaa ja bolševike vastu, et '
        'säilitada oma iseseisvust.\n   - '
        'Läti Vabadussõda kestis kuni 1920. aastani, mil Läti '
        'sõlmis rahulepingu Nõukogude Venemaaga (Tartu rahu). '
        'Rahulepinguga tunnustas Nõukogude Venemaa '
        'Läti iseseisvust.\n\n4. **Rahvusvaheline tunnustamine:**\n   '
        '- 1921. aastal tunnustas ka Antanti Liit '
        '(Esimese maailmasõja võitjariigid) Läti iseseisvust de iure. '
        'Samal aastal võeti Läti ka Rahvasteliitu.\n\n'
        'Läti eliit integreerus maailmasõjalistesse ja '
        'diplomaatilistesse protsessidesse, '
        'et kindlustada oma riiklik iseseisvus ja rahvusvaheline tunnustamine.\n\n'
        'Kui teil on veel küsimusi või soovite täpsemaid '
        'üksikasju, andke endast teada!',
        'input_tokens': 118,
        'output_tokens': 445,
        'total_cost': 0.007265000000000001,
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