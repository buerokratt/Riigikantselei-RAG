from typing import Dict

import elasticsearch_dsl


def parse_hits_as_references(hits, text_field, url_field, title_field, user_input) -> Dict:
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
        # We remove the next now to avoid storing it in Redis.
        reference.pop('text', None)

    return {'context': query_with_context, 'references': context_documents_contents}
