from base64 import b64encode
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
from typing import Any, Dict, Iterable, List

import matplotlib.pyplot as plt
from dateutil.relativedelta import relativedelta
from django.db.models import Q, QuerySet, Sum
from django.template.loader import render_to_string
from fpdf import FPDF

from core.mixins import ConversationMixin
from core.utilities import dataset_indexes_to_names
from document_search.models import DocumentSearchConversation, DocumentSearchQueryResult
from text_search.models import TextSearchConversation, TextSearchQueryResult
from user_profile.models import LogInEvent, LogOutEvent, UserProfile


def _paragraphize(text: str) -> List[str]:
    text_paragraphs = text.strip().split('\n')
    return [paragraph for paragraph in text_paragraphs if paragraph]


# TODO: ideally should be unit tested
def _build_conversation_context(
    conversation_title: str,
    message_dict_list: List[Dict[str, str]],
    reference_list_list: List[List[Dict[str, str]]],
) -> Dict[str, Any]:
    if len(message_dict_list) != len(reference_list_list):
        raise RuntimeError()

    messages_with_references: List[Dict[str, Any]] = []

    # pylint: disable=consider-using-enumerate
    for i in range(len(message_dict_list)):
        message_dict = message_dict_list[i]
        reference_list = reference_list_list[i]

        messages_with_references.append(
            {'role': 'Kasutaja', 'paragraphs': _paragraphize(message_dict['user'])}
        )
        messages_with_references.append(
            {
                'role': 'Vastus',
                'paragraphs': _paragraphize(message_dict['assistant']),
                'references': reference_list,
            }
        )

    return {
        'conversation_title': conversation_title,
        'messages_with_references': messages_with_references,
    }


def _queries_to_year_list(queries: QuerySet) -> Iterable[int]:
    year_lists = (
        range(min_year, max_year + 1)
        for min_year, max_year in queries.exclude(
            conversation__min_year__isnull=True, conversation__max_year__isnull=True
        ).values_list('conversation__min_year', 'conversation__max_year')
    )
    return (year for year_list in year_lists for year in year_list)


def _text_queries_to_dataset_list(text_queries: QuerySet) -> Iterable[str]:
    dataset_lists = (text_query.conversation.dataset_names for text_query in text_queries)
    return (dataset for dataset_list in dataset_lists for dataset in dataset_list)


def _document_queries_to_dataset_list(dataset_queries: QuerySet) -> Iterable[str]:
    return dataset_queries.values_list('dataset_name', flat=True)


def _references_to_value_list(references_query_set: QuerySet, key: str) -> Iterable[Any]:
    if key == 'dataset':
        # Dataset name is not in the database or reference and we have to map from index to dataset
        key = 'index'

    value_list: Iterable[Any] = (
        reference.get(key, 'Teadmata')
        for reference_list in references_query_set.all()
        for reference in reference_list
    )
    if key == 'index':
        value_list = dataset_indexes_to_names(value_list)

    return value_list


def _get_bar_chart_image_base_64_from_year_counter(counter: Counter) -> str:
    x_y_pairs = counter.most_common()
    x_y_pairs = sorted(x_y_pairs, key=lambda pair: pair[0])
    x_list, y_list = zip(*x_y_pairs) if x_y_pairs else ([], [])

    _, axis = plt.subplots()

    bar_graph = axis.bar(x_list, y_list)
    axis.bar_label(bar_graph)

    axis.set_xlabel('Aasta')
    axis.set_ylabel('Arv')

    image_bytes_buffer = BytesIO()
    plt.savefig(image_bytes_buffer)
    image_bytes_buffer.seek(0)
    return b64encode(image_bytes_buffer.read()).decode()


def _get_bar_chart_image_base_64_from_dataset_counter(counter: Counter) -> str:
    x_y_pairs = counter.most_common()
    x_list, y_list = zip(*x_y_pairs) if x_y_pairs else ([], [])
    x_list = [x_value if len(x_list) < 50 else f'{x_value[:47]}...' for x_value in x_list]

    _, axis = plt.subplots()

    bar_graph = axis.barh(x_list, y_list)
    axis.invert_yaxis()
    axis.bar_label(bar_graph)
    axis.set_yticks([])
    for index, x_value in enumerate(x_list):
        plt.text(0, index, x_value, va='center')

    axis.set_ylabel('Andmestik')
    axis.set_xlabel('Arv')

    image_bytes_buffer = BytesIO()
    plt.savefig(image_bytes_buffer)
    image_bytes_buffer.seek(0)
    return b64encode(image_bytes_buffer.read()).decode()


# TODO: ideally refactor to decrease repetition.
#  For example, total and month can probably be 2 calls of 1 function
# pylint: disable=too-many-statements
def _build_statistics_context(year: int, month: int) -> Dict[str, Any]:
    context: Dict[str, Any] = {}

    context['year'] = year
    context['month'] = str(month).zfill(2)

    month_start_datetime = datetime(year=year, month=month, day=1, tzinfo=timezone.utc)
    month_end_datetime = month_start_datetime + relativedelta(months=1) - relativedelta(days=1)

    total_time_filter = Q(created_at__lte=month_end_datetime)
    month_time_filter = Q(created_at__lte=month_end_datetime, created_at__gte=month_start_datetime)

    context['log_in_count_total'] = LogInEvent.objects.filter(total_time_filter).count()
    context['log_in_count_month'] = LogInEvent.objects.filter(month_time_filter).count()
    context['log_out_count_total'] = LogOutEvent.objects.filter(total_time_filter).count()
    context['log_out_count_month'] = LogOutEvent.objects.filter(month_time_filter).count()

    text_queries_total = TextSearchQueryResult.objects.filter(total_time_filter)
    text_queries_month = TextSearchQueryResult.objects.filter(month_time_filter)
    document_queries_total = DocumentSearchQueryResult.objects.filter(total_time_filter)
    document_queries_month = DocumentSearchQueryResult.objects.filter(month_time_filter)

    text_queries_total_conversation_ids = set(
        text_queries_total.values_list('conversation__id', flat=True)
    )
    text_queries_month_conversation_ids = set(
        text_queries_month.values_list('conversation__id', flat=True)
    )
    document_queries_total_conversation_ids = set(
        document_queries_total.values_list('conversation__id', flat=True)
    )
    document_queries_month_conversation_ids = set(
        document_queries_month.values_list('conversation__id', flat=True)
    )

    text_conversations_total = TextSearchConversation.objects.filter(
        id__in=text_queries_total_conversation_ids
    )
    text_conversations_month = TextSearchConversation.objects.filter(
        id__in=text_queries_month_conversation_ids
    )
    document_conversations_total = DocumentSearchConversation.objects.filter(
        id__in=document_queries_total_conversation_ids
    )
    document_conversations_month = DocumentSearchConversation.objects.filter(
        id__in=document_queries_month_conversation_ids
    )

    text_conversations_total_user_ids = set(
        text_conversations_total.values_list('auth_user__id', flat=True)
    )
    text_conversations_month_user_ids = set(
        text_conversations_month.values_list('auth_user__id', flat=True)
    )
    document_conversations_total_user_ids = set(
        document_conversations_total.values_list('auth_user__id', flat=True)
    )
    document_conversations_month_user_ids = set(
        document_conversations_month.values_list('auth_user__id', flat=True)
    )

    user_with_query_count_total = len(
        text_conversations_total_user_ids | document_conversations_total_user_ids
    )
    user_with_query_count_month = len(
        text_conversations_month_user_ids | document_conversations_month_user_ids
    )

    context['user_count_total'] = UserProfile.objects.filter(total_time_filter).count()
    context['user_count_month'] = UserProfile.objects.filter(month_time_filter).count()
    context['user_with_query_count_total'] = user_with_query_count_total
    context['user_with_query_count_month'] = user_with_query_count_month

    text_query_cost_total = text_queries_total.aggregate(Sum('total_cost', default=0.0))[
        'total_cost__sum'
    ]
    text_query_cost_month = text_queries_month.aggregate(Sum('total_cost', default=0.0))[
        'total_cost__sum'
    ]
    document_query_cost_total = document_queries_total.aggregate(Sum('total_cost', default=0.0))[
        'total_cost__sum'
    ]
    document_query_cost_month = document_queries_month.aggregate(Sum('total_cost', default=0.0))[
        'total_cost__sum'
    ]

    cost_total = text_query_cost_total + document_query_cost_total
    cost_month = text_query_cost_month + document_query_cost_month

    context['cost_total'] = round(cost_total, 2)
    context['cost_month'] = round(cost_month, 2)
    context['cost_per_user_with_query_total'] = (
        round(cost_total / user_with_query_count_total, 4) if user_with_query_count_total else 0
    )
    context['cost_per_user_with_query_month'] = (
        round(cost_month / user_with_query_count_month, 4) if user_with_query_count_month else 0
    )

    query_count_total = text_queries_total.count() + document_queries_total.count()
    query_count_month = text_queries_month.count() + document_queries_month.count()

    conversation_count_total = (
        text_conversations_total.count() + document_conversations_total.count()
    )
    conversation_count_month = (
        text_conversations_month.count() + document_conversations_month.count()
    )

    context['query_count_total'] = query_count_total
    context['query_count_month'] = query_count_month
    context['query_count_per_user_with_query_total'] = (
        round(query_count_total / user_with_query_count_total, 2)
        if user_with_query_count_total
        else 0
    )
    context['query_count_per_user_with_query_month'] = (
        round(query_count_month / user_with_query_count_month, 2)
        if user_with_query_count_month
        else 0
    )
    context['query_count_per_conversation_total'] = (
        round(query_count_total / conversation_count_total, 2) if conversation_count_total else 0
    )
    context['query_count_per_conversation_month'] = (
        round(query_count_month / conversation_count_month, 2) if conversation_count_month else 0
    )

    context['text_search_query_proportion_total'] = (
        round(text_queries_total.count() / query_count_total * 100, 1) if query_count_total else 0
    )
    context['text_search_query_proportion_month'] = (
        round(text_queries_month.count() / query_count_month * 100, 1) if query_count_month else 0
    )
    context['document_search_query_proportion_total'] = (
        round(document_queries_total.count() / query_count_total * 100, 1)
        if query_count_total
        else 0
    )
    context['document_search_query_proportion_month'] = (
        round(document_queries_month.count() / query_count_month * 100, 1)
        if query_count_month
        else 0
    )

    year_usage_total_counts: Counter[int] = Counter()
    year_usage_month_counts: Counter[int] = Counter()

    year_usage_total_counts.update(_queries_to_year_list(text_queries_total))
    year_usage_total_counts.update(_queries_to_year_list(document_queries_total))
    year_usage_month_counts.update(_queries_to_year_list(text_queries_month))
    year_usage_month_counts.update(_queries_to_year_list(document_queries_month))

    dataset_usage_total_counts: Counter[str] = Counter()
    dataset_usage_month_counts: Counter[str] = Counter()

    dataset_usage_total_counts.update(_text_queries_to_dataset_list(text_queries_total))
    dataset_usage_total_counts.update(_document_queries_to_dataset_list(document_queries_total))
    dataset_usage_month_counts.update(_text_queries_to_dataset_list(text_queries_month))
    dataset_usage_month_counts.update(_document_queries_to_dataset_list(document_queries_month))

    text_references_total = text_queries_total.values_list('references', flat=True)
    text_references_month = text_queries_month.values_list('references', flat=True)
    document_references_total = document_queries_total.values_list('references', flat=True)
    document_references_month = document_queries_month.values_list('references', flat=True)

    year_reference_total_counts: Counter[int] = Counter()
    year_reference_month_counts: Counter[int] = Counter()

    year_reference_total_counts.update(_references_to_value_list(text_references_total, 'year'))
    year_reference_total_counts.update(_references_to_value_list(document_references_total, 'year'))
    year_reference_month_counts.update(_references_to_value_list(text_references_month, 'year'))
    year_reference_month_counts.update(_references_to_value_list(document_references_month, 'year'))

    dataset_reference_total_counts: Counter[str] = Counter()
    dataset_reference_month_counts: Counter[str] = Counter()

    dataset_reference_total_counts.update(
        _references_to_value_list(text_references_total, 'dataset')
    )
    dataset_reference_total_counts.update(
        _references_to_value_list(document_references_total, 'dataset')
    )
    dataset_reference_month_counts.update(
        _references_to_value_list(text_references_month, 'dataset')
    )
    dataset_reference_month_counts.update(
        _references_to_value_list(document_references_month, 'dataset')
    )

    # for testing purposes only
    context['year_usage_total_counts'] = dict(year_usage_total_counts)
    context['year_usage_month_counts'] = dict(year_usage_month_counts)
    context['year_reference_total_counts'] = dict(year_reference_total_counts)
    context['year_reference_month_counts'] = dict(year_reference_month_counts)
    # for testing purposes only
    context['dataset_usage_total_counts'] = dict(dataset_usage_total_counts)
    context['dataset_usage_month_counts'] = dict(dataset_usage_month_counts)
    context['dataset_reference_total_counts'] = dict(dataset_reference_total_counts)
    context['dataset_reference_month_counts'] = dict(dataset_reference_month_counts)

    context['year_usage_total_graph_base_64'] = _get_bar_chart_image_base_64_from_year_counter(
        year_usage_total_counts
    )
    context['year_usage_month_graph_base_64'] = _get_bar_chart_image_base_64_from_year_counter(
        year_usage_month_counts
    )
    context['year_reference_total_graph_base_64'] = _get_bar_chart_image_base_64_from_year_counter(
        year_reference_total_counts
    )
    context['year_reference_month_graph_base_64'] = _get_bar_chart_image_base_64_from_year_counter(
        year_reference_month_counts
    )

    context[
        'dataset_usage_total_graph_base_64'
    ] = _get_bar_chart_image_base_64_from_dataset_counter(dataset_usage_total_counts)
    context[
        'dataset_usage_month_graph_base_64'
    ] = _get_bar_chart_image_base_64_from_dataset_counter(dataset_usage_month_counts)
    context[
        'dataset_reference_total_graph_base_64'
    ] = _get_bar_chart_image_base_64_from_dataset_counter(dataset_reference_total_counts)
    context[
        'dataset_reference_month_graph_base_64'
    ] = _get_bar_chart_image_base_64_from_dataset_counter(dataset_reference_month_counts)

    return context


def get_conversation_pdf_file_bytes(conversation: ConversationMixin) -> BytesIO:
    context = _build_conversation_context(
        conversation_title=conversation.title,
        message_dict_list=conversation.messages_for_pdf,
        reference_list_list=conversation.references_for_pdf,
    )
    # https://py-pdf.github.io/fpdf2/HTML.html#supported-html-features
    html = render_to_string(template_name='conversation.html', context=context)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica')
    pdf.set_text_color(0, 0, 0)
    pdf.write_html(html)

    # You can uncomment this and run tests to look at the produced PDF
    # if conversation.references_for_pdf:
    #     pdf.output('messages.pdf')

    # BytesIO is necessary for Django's FileResponse class to return a proper file to the front-end
    bytes_buffer = BytesIO(pdf.output())
    bytes_buffer.seek(0)
    return bytes_buffer


def get_statistics_pdf_file_bytes(year: int, month: int) -> BytesIO:
    context = _build_statistics_context(year, month)
    # https://py-pdf.github.io/fpdf2/HTML.html#supported-html-features
    html = render_to_string(template_name='statistics.html', context=context)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('Helvetica')
    pdf.set_text_color(0, 0, 0)
    pdf.write_html(html)

    # You can uncomment this and run tests to look at the produced PDF
    # pdf.output('statistics.pdf')

    # BytesIO is necessary for Django's FileResponse class to return a proper file to the front-end
    bytes_buffer = BytesIO(pdf.output())
    bytes_buffer.seek(0)
    return bytes_buffer
