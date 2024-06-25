# Prevent using bad characters like various whitespace
import re

from rest_framework import serializers

_REASONABLE_CHARACTER_WITHOUT_SPACES_PATTERN = re.compile(
    r'[\w<>|,;.:\-_~+!"#¤%&/()=?@£€${\[\]}\\§\'*]*'
)
_REASONABLE_CHARACTER_WITH_SPACES_PATTERN = re.compile(
    r'[\w<>|,;.:\-_~+!"#¤%&/()=?@£€${\[\]}\\§\'* ]*'
)


def reasonable_character_without_spaces_validator(string: str) -> str:
    if not _REASONABLE_CHARACTER_WITHOUT_SPACES_PATTERN.fullmatch(string):
        raise serializers.ValidationError('The given value contains forbidden characters.')
    return string


def reasonable_character_with_spaces_validator(string: str) -> str:
    if not _REASONABLE_CHARACTER_WITH_SPACES_PATTERN.fullmatch(string):
        raise serializers.ValidationError('The given value contains forbidden characters.')
    return string
