from typing import Any, List, Optional

from django.conf import settings
from django.db import models
from rest_framework.exceptions import ValidationError

from api.utilities.core_settings import is_float


class CoreVariable(models.Model):
    name = models.CharField(max_length=100)
    value = models.TextField(default=None, null=True)

    def __str__(self) -> str:
        return f'{self.name} - {self.value}'

    @staticmethod
    def get_core_setting(setting_name: str) -> Any:
        """
        Retrieves value for a variable from core settings.
        :param: str variable_name: Name for the variable whose value will be returned.
        """
        # pylint: disable=too-many-return-statements
        variable_match: Optional[CoreVariable] = CoreVariable.objects.filter(
            name=setting_name
        ).first()

        if not variable_match:
            # return value from env if no setting record in db
            if setting_name in settings.CORE_SETTINGS:
                return settings.CORE_SETTINGS[setting_name]
            return None

        # return value from db
        value = variable_match.value

        if is_float(value):
            return float(value)
        if str.isnumeric(value):
            return int(value)
        if value.lower() == 'false':
            return False
        if value.lower() == 'true':
            return True
        return value


class Dataset(models.Model):
    # Name of the dataset, for example 'Riigi teataja'
    name = models.CharField(max_length=100, unique=True)
    # Type of dataset, for example 'Arengukava'
    type = models.CharField(max_length=100)
    # Elasticsearch wildcard string describing names of all indexes used by this dataset.
    # For example, to cover 'riigiteataja_1' and 'riigiteataja_2', use 'riigiteataja_*'.
    index = models.CharField(max_length=100)
    # Description of dataset contents
    description = models.TextField(default='')

    @staticmethod
    def get_all_dataset_values(field: str = 'name') -> List[str]:
        return list(Dataset.objects.values_list(field, flat=True))

    @staticmethod
    def validate_dataset_names(dataset_names: List[str]) -> None:
        known_dataset_names = Dataset.get_all_dataset_values()
        bad_dataset_names = []
        for dataset_name in dataset_names:
            if dataset_name not in known_dataset_names:
                bad_dataset_names.append(dataset_name)

        if bad_dataset_names:
            raise ValidationError(f'Unknown dataset names: [{", ".join(bad_dataset_names)}]')
