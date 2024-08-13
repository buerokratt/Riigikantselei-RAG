# pylint: skip-file

import datetime
import json
import os

import django

# Initialize django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'src.api.settings')
django.setup()

from document_search.models import DocumentSearchQueryResult
from text_search.models import TextSearchQueryResult
from user_profile.models import LogInEvent, LogOutEvent


def parse_references(result):
    reference_container = []

    references = getattr(result, 'references', [])
    references = references if references else []  # Since this can be None.
    for reference in references:
        reference_container.append(
            {
                'id': reference.get('id', ''),
                'index': reference['index'],
                'parent': reference.get('parent', ''),
            }
        )
    return reference_container


def get_login_logout_events():
    container = []
    for login in LogInEvent.objects.all():
        login.event = 'log-in'
        container.append(login)

    for logout in LogOutEvent.objects.all():
        logout.event = 'log-out'
        container.append(logout)

    return container


def parse_user_input(result):
    text_search_datasets = getattr(result.conversation, 'dataset_names', None)
    document_search_dataset = getattr(result, 'dataset_name', None)
    datasets = text_search_datasets or document_search_dataset

    event = (
        'text-search' if result.__class__.__name__ == 'TextSearchQueryResult' else 'document-search'
    )

    data = {
        'user': result.conversation.auth_user.username,
        'user_input': result.user_input,
        'gpt_response': result.response,
        'created_at': str(result.created_at),
        'input_tokens': result.input_tokens,
        'output_tokens': result.output_tokens,
        'datasets': datasets,
        'total_cost': result.total_cost,
        'is_context_pruned': result.is_context_pruned,
        'min_year': getattr(result.conversation, 'min_year', None),
        'max_year': getattr(result.conversation, 'max_year', None),
        'model': result.model,
        'references': references,
        'event': event,
    }

    return data


def parse_login_logout_event(event):
    return {
        'created_at': str(event.created_at),
        'event': event.event,
        'user': event.auth_user.username,
    }


if __name__ == '__main__':
    text_results = list(TextSearchQueryResult.objects.all())
    document_results = list(DocumentSearchQueryResult.objects.all())

    user_inputs = text_results + document_results
    login_logout_events = get_login_logout_events()

    all_events = user_inputs + login_logout_events
    all_events.sort(key=lambda x: x.created_at, reverse=True)

    today = datetime.date.today()
    date_string = today.strftime('%Y-%m-%d')
    with open(f'{date_string}-dump.jsonl', 'w+', encoding='utf-8') as fp:
        for event in all_events:
            class_name = event.__class__.__name__
            if class_name in ('LogInEvent', 'LogOutEvent'):
                data = parse_login_logout_event(event)
            else:
                references = parse_references(event)
                data = parse_user_input(event)

            data = json.dumps(data, ensure_ascii=False)
            fp.write(f'{data}\n')
