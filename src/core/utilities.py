import datetime
import re
from typing import Any, Dict, Iterable, Optional

from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError
from tiktoken import Encoding

from core.models import Dataset


def validate_min_max_years(min_year: int, max_year: int) -> None:
    if min_year and min_year > datetime.datetime.now().year:
        raise ValidationError(_('Minimum year must be lesser than currently running year!'))

    if min_year and max_year and min_year > max_year:
        raise ValidationError(_('Minimum year must be lesser than the maximum year restriction!'))


def get_n_tokens(text: str, encoder: Encoding) -> int:
    """
    Counts number of tokens.
    """
    n_tokens = len(encoder.encode(text))
    return n_tokens


def exceeds_token_limit(text: str, encoder: Encoding, token_limit: int = 10000) -> bool:
    """
    Checks, if text exceeds the allowed token limit or not.
    """
    n_tokens = get_n_tokens(text=text, encoder=encoder)
    if n_tokens > token_limit:
        return True
    return False


def prune_context(text: str, encoder: Encoding, token_limit: int = 10000) -> str:
    """
    Prunes context to `token_limit` tokens.
    """
    tokens = encoder.encode(text)
    pruned_tokens = tokens[:token_limit]
    pruned_context = encoder.decode(pruned_tokens)
    return pruned_context


def wildcard_to_regex(pattern: str) -> str:
    return re.escape(pattern).replace(r'\*', '.*')


# Function to match string with patterns and return corresponding value
def match_pattern(input_string: str, wildcard_to_data_map: Dict[str, Any]) -> Optional[Any]:
    for wildcard_pattern, data in wildcard_to_data_map.items():
        regex_pattern = wildcard_to_regex(wildcard_pattern)
        if re.fullmatch(regex_pattern, input_string):
            return data
    return None


def dataset_indexes_to_names(indexes: Iterable[str]) -> Iterable[str]:
    dataset_index_wildcard_to_name_map = {}
    for dataset in Dataset.objects.all():
        dataset_index_wildcard_to_name_map[dataset.index] = dataset.name

    for index in indexes:
        name = match_pattern(index, dataset_index_wildcard_to_name_map)
        yield name if name else 'Teadmata'
