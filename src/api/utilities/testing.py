from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User

from core.models import CoreVariable
from core.serializers import CoreVariableSerializer


class IsType:
    def __init__(self, type_class: Any):
        self.type = type_class

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, self.type)


def create_test_user(username: str, email: str, password: str, is_superuser: bool = False) -> User:
    model = get_user_model()
    auth_user = model.objects.create_user(
        username=username,
        email=email,
        password=password,
        is_superuser=is_superuser,
        is_staff=is_superuser,
        is_active=True,
    )
    return auth_user


def set_core_setting(setting_name: str, setting_value: Any) -> None:
    """
    Set core settings outside of the API for testing.
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
