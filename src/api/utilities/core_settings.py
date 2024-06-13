from typing import Any, Optional

from django.conf import settings

from core.models import CoreVariable
from core.serializers import CoreVariableSerializer


def is_float(value: str) -> bool:
    normalized_numbers = value.replace('.', '')
    if '.' in value and str.isdigit(normalized_numbers):
        return True

    return False


def get_core_setting(setting_name: str) -> Any:
    """
    Retrieves value for a variable from core settings.
    :param: str variable_name: Name for the variable whose value will be returned.
    """
    # pylint: disable=too-many-return-statements
    variable_match: Optional[CoreVariable] = CoreVariable.objects.filter(name=setting_name).first()

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


def set_core_setting(setting_name: str, setting_value: Any) -> None:
    """
    Set core settings outside of the API.
    :param: str setting name: Name of the variable to update.
    :param: str setting_value: New Value of the variable.
    """

    data = {'name': setting_name, 'value': setting_value}
    validated_data = CoreVariableSerializer().validate(data)
    setting_name = validated_data['name']
    setting_value = validated_data['value']
    variable_matches = CoreVariable.objects.filter(name=setting_name)

    if not variable_matches:
        # Add a new variable
        new_variable = CoreVariable(name=setting_name, value=setting_value)
        new_variable.save()

    else:
        # Change existing variable
        variable_match = variable_matches.first()
        variable_match.value = setting_value
        variable_match.save()
