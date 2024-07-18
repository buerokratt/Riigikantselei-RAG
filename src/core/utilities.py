from typing import List

from api.utilities.core_settings import get_core_setting


def parse_gpt_question_and_references(user_input: str, hits: List[dict]) -> dict:
    url_field = get_core_setting('ELASTICSEARCH_URL_FIELD')
    title_field = get_core_setting('ELASTICSEARCH_TITLE_FIELD')
    text_field = get_core_setting('ELASTICSEARCH_TEXT_CONTENT_FIELD')
    dataset_name_field = get_core_setting('ELASTICSEARCH_DATASET_NAME_FIELD')

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
            'dataset_name': source.get(dataset_name_field, ''),
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
