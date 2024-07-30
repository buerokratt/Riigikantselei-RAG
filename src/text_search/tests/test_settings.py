import datetime
from typing import List
from uuid import UUID

from api.utilities.testing import IsType
from core.choices import TaskStatus
from core.models import CoreVariable
from text_search.tasks import save_openai_results

# pylint: disable=unused-argument


# Conversation

CHAT_QUESTION_1 = 'Kuidas sai Eesti iseseisvuse?'
CHAT_QUESTION_2 = 'Ok, aga anna siis infot Läti iseseivuse kohta.'

BASE_CREATE_INPUT = {
    'user_input': CHAT_QUESTION_1,
    'min_year': 2020,
    'max_year': 2024,
    'dataset_names': ['a', 'c'],
}

BASE_SET_TITLE_INPUT = {
    'title': BASE_CREATE_INPUT['user_input'],
}

INVALID_DATASET_NAME_CREATE_INPUT = BASE_CREATE_INPUT | {'dataset_names': ['a', 'foo']}

INVALID_MIN_YEAR_CREATE_INPUT = BASE_CREATE_INPUT | {'min_year': datetime.datetime.now().year + 1}

# Min year should not be bigger than max year.
INVALID_YEAR_DIFFERENCE_CREATE_INPUT = BASE_CREATE_INPUT | {'min_year': 2024, 'max_year': 2020}

EQUAL_DATES_CREATE_INPUT = BASE_CREATE_INPUT | {'min_year': 2024}

NEITHER_DATE_CREATE_INPUT = dict(BASE_CREATE_INPUT)
NEITHER_DATE_CREATE_INPUT.pop('min_year')
NEITHER_DATE_CREATE_INPUT.pop('max_year')

# Chat

CHAT_INPUT_1 = {
    'user_input': CHAT_QUESTION_1,
}

CHAT_INPUT_2 = {
    'user_input': CHAT_QUESTION_2,
}

CHAT_CHAIN_EXPECTED_ARGUMENTS_1 = {
    'user_input': CHAT_INPUT_1['user_input'],
    'dataset_index_queries': ['a_*', 'c_*'],
    'conversation_id': IsType(str),
    'result_uuid': IsType(UUID),
}

CHAT_CHAIN_EXPECTED_ARGUMENTS_2 = CHAT_CHAIN_EXPECTED_ARGUMENTS_1 | {
    'user_input': CHAT_INPUT_2['user_input'],
}

CHAT_ANSWER_1 = 'response_text_1'
CHAT_ANSWER_2 = 'response_text_2'

CHAT_REFERENCES_1 = [
    {
        'text': 'reference_text_1',
        'elastic_id': 'elastic_id_1',
        'index': 'elastic_id_1',
        'title': 'title_1',
        'url': 'url_1',
        'dataset_name': 'Dataset Name',
    },
    {
        'text': 'reference_text_2',
        'elastic_id': 'elastic_id_2',
        'index': 'elastic_id_2',
        'title': 'title_2',
        'url': 'url_2',
        'dataset_name': 'Dataset Name',
    },
]

CHAT_CHAIN_RESULTS_DICT_1 = {
    'model': 'model_name',
    'user_input': CHAT_INPUT_1['user_input'],
    'response': CHAT_ANSWER_1,
    'is_context_pruned': False,
    'input_tokens': 10,
    'output_tokens': 20,
    'total_cost': 0.05,
    'response_headers': {},
    'references': CHAT_REFERENCES_1,
}

CHAT_CHAIN_RESULTS_DICT_2 = CHAT_CHAIN_RESULTS_DICT_1 | {
    'user_input': CHAT_INPUT_2['user_input'],
    'response': CHAT_ANSWER_2,
    'input_tokens': 20,
    'output_tokens': 40,
    'total_cost': 0.10,
}

CHAT_CHAIN_EXPECTED_QUERY_RESULTS_1 = {
    'user_input': CHAT_CHAIN_RESULTS_DICT_1['user_input'],
    'response': CHAT_CHAIN_RESULTS_DICT_1['response'],
    'references': CHAT_CHAIN_RESULTS_DICT_1['references'],
    'total_cost': CHAT_CHAIN_RESULTS_DICT_1['total_cost'],
    'is_context_pruned': CHAT_CHAIN_RESULTS_DICT_1['is_context_pruned'],
    'created_at': IsType(str),
    'celery_task': {
        'status': TaskStatus.SUCCESS,
        'error': '',
        'created_at': IsType(str),
        'modified_at': IsType(str),
    },
}

CHAT_CHAIN_EXPECTED_QUERY_RESULTS_2 = CHAT_CHAIN_EXPECTED_QUERY_RESULTS_1 | {
    'user_input': CHAT_CHAIN_RESULTS_DICT_2['user_input'],
    'response': CHAT_CHAIN_RESULTS_DICT_2['response'],
    'references': CHAT_CHAIN_RESULTS_DICT_2['references'],
    'total_cost': CHAT_CHAIN_RESULTS_DICT_2['total_cost'],
}


def chat_chain_side_effect_1(
    user_input: str,
    dataset_index_queries: List[str],
    conversation_id: int,
    result_uuid: str,
) -> None:
    # type: ignore
    # pylint: disable=no-value-for-parameter
    save_openai_results.apply([CHAT_CHAIN_RESULTS_DICT_1, conversation_id, result_uuid])


def chat_chain_side_effect_2(
    user_input: str,
    dataset_index_queries: List[str],
    conversation_id: int,
    result_uuid: str,
) -> None:
    # type: ignore
    # pylint: disable=no-value-for-parameter
    save_openai_results.apply([CHAT_CHAIN_RESULTS_DICT_2, conversation_id, result_uuid])


# Messages and references (@property)

EXPECTED_MESSAGES = [
    {
        'role': 'system',
        'content': CoreVariable.get_core_setting('OPENAI_SYSTEM_MESSAGE'),
    },
    {
        'role': 'user',
        'content': CHAT_QUESTION_1,
    },
    {
        'role': 'assistant',
        'content': CHAT_ANSWER_1,
    },
]

EXPECTED_MESSAGES_FOR_PDF = [
    {
        'user': CHAT_QUESTION_1,
        'assistant': CHAT_ANSWER_1,
    },
]

EXPECTED_REFERENCES_FOR_PDF = [CHAT_REFERENCES_1]
