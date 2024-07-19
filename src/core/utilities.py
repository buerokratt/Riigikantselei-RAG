import datetime
from typing import List

from rest_framework.exceptions import ValidationError

from api.utilities.core_settings import get_core_setting
from core.models import Dataset


def parse_gpt_question_and_references(user_input: str, hits: List[dict]) -> dict:
    url_field = get_core_setting('ELASTICSEARCH_URL_FIELD')
    title_field = get_core_setting('ELASTICSEARCH_TITLE_FIELD')
    text_field = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')

    context_documents_contents = []
    for hit in hits:
        source = hit['_source'].to_dict()
        content = source.get(text_field, '')
        reference = {
            'text': content,
            'elastic_id': hit['_id'],
            'index': hit['_index'],
            'title': source.get(title_field, ''),
            'url': source.get(url_field, ''),
        }
        if content:
            context_documents_contents.append(reference)

    context = '\n\n'.join([document[text_field] for document in context_documents_contents])
    query_with_context = (
        'Answer the following question using the provided context from below! '
        f'Question: ```{user_input}```'
        '\n\n'
        f'Context: ```{context}```'
    )

    for reference in context_documents_contents:
        reference.pop('text', None)

    return {'context': query_with_context, 'references': context_documents_contents}


def get_all_dataset_values(field: str = 'name') -> List[str]:
    return list(Dataset.objects.values_list(field, flat=True))


def validate_dataset_names(dataset_names: List[str]) -> None:
    known_dataset_names = get_all_dataset_values()
    bad_dataset_names = []
    for dataset_name in dataset_names:
        if dataset_name not in known_dataset_names:
            bad_dataset_names.append(dataset_name)

    if bad_dataset_names:
        raise ValidationError(f'Unknown dataset names: [{", ".join(bad_dataset_names)}]')


def validate_min_max_years(min_year: int, max_year: int) -> None:
    if min_year and min_year > datetime.datetime.now().year:
        raise ValidationError('min_year must be lesser than currently running year!')

    if max_year and max_year > datetime.datetime.now().year:
        raise ValidationError('max_year must be lesser than currently running year!')

    if min_year and max_year and min_year > max_year:
        raise ValidationError('min_year must be lesser than max_year!')
