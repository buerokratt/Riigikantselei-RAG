import datetime

import tiktoken
from rest_framework.exceptions import ValidationError


def validate_min_max_years(min_year: int, max_year: int) -> None:
    if min_year and min_year > datetime.datetime.now().year:
        raise ValidationError('min_year must be lesser than currently running year!')

    if max_year and max_year > datetime.datetime.now().year:
        raise ValidationError('max_year must be lesser than currently running year!')

    if min_year and max_year and min_year > max_year:
        raise ValidationError('min_year must be lesser than max_year!')


def get_n_tokens(text: str, model: str = 'gpt-4o') -> int:
    """
    Counts number of tokens.
    """
    enc = tiktoken.encoding_for_model(model)
    n_tokens = len(enc.encode(text))
    return n_tokens


def exceeds_token_limit(text: str, model: str, token_limit: int = 10000) -> bool:
    """
    Checks, if text exceeds the allowed token limit or not.
    """
    n_tokens = get_n_tokens(text=text, model=model)
    if n_tokens > token_limit:
        return True
    return False


def prune_context(text: str, model: str = 'gpt-4o', token_limit: int = 10000) -> str:
    """
    Prunes context to `token_limit` tokens.
    """
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(text)
    pruned_tokens = tokens[:token_limit]
    pruned_context = enc.decode(pruned_tokens)
    return pruned_context
