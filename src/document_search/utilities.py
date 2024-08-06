from typing import List, Optional

from core.models import CoreVariable, Dataset
from core.utilities import match_pattern


def parse_aggregation(hits: List[dict]) -> List[dict]:
    year_field = CoreVariable.get_core_setting('ELASTICSEARCH_YEAR_FIELD')
    parent_field = CoreVariable.get_core_setting('ELASTICSEARCH_PARENT_FIELD')

    datasets = {}
    for dataset in Dataset.objects.all():
        datasets[dataset.index] = dataset

    # Since the year and indices are the same for every main
    # document we gather them in a single list in a structured fashion
    # and we remove duplicate segments from the same document by removing
    # all unique segments.
    values = []
    for hit in hits:
        index = hit['_index']
        dataset_orm: Optional[Dataset] = match_pattern(index, datasets)
        document = hit['_source']
        year = document.get(year_field, None)
        parent_reference = document.get(parent_field, None)
        int_year = int(year) if year else None

        # Testing shows that some documents are missing a year field.
        # Hence, we test for every value, even though the count
        # might be off by a bit.
        if int_year and parent_reference and dataset_orm:
            values.append((parent_reference, int_year, dataset_orm.name))

    unique_documents = set(values)
    dataset_years = {}

    for _, year, name in unique_documents:
        if name not in dataset_years:
            dataset_years[name] = [year]
        else:
            dataset_years[name].append(year)

    response = []
    for dataset, years in dataset_years.items():
        item = {
            'dataset_name': dataset,
            'min_year': min(years),
            'max_year': max(years),
            'count': len(years),
        }

        response.append(item)

    response.sort(key=lambda x: x['count'], reverse=True)
    return response
