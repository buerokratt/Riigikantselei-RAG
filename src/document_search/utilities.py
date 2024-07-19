import re
from typing import Any, Optional


def wildcard_to_regex(pattern: str) -> str:
    return re.escape(pattern).replace(r'\*', '.*')


# Function to match string with patterns and return corresponding value
def match_pattern(input_string: str, data: dict) -> Optional[Any]:
    for wildcard_pattern, value in data.items():
        regex_pattern = wildcard_to_regex(wildcard_pattern)
        if re.fullmatch(regex_pattern, input_string):
            return value
    return None
