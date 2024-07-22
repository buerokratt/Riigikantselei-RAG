import datetime

from rest_framework.exceptions import ValidationError


def validate_min_max_years(min_year: int, max_year: int) -> None:
    if min_year and min_year > datetime.datetime.now().year:
        raise ValidationError('min_year must be lesser than currently running year!')

    if max_year and max_year > datetime.datetime.now().year:
        raise ValidationError('max_year must be lesser than currently running year!')

    if min_year and max_year and min_year > max_year:
        raise ValidationError('min_year must be lesser than max_year!')
