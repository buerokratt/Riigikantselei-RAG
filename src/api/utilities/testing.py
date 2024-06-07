from django.contrib.auth import get_user_model
from django.contrib.auth.models import User


def create_test_user(username: str, email: str, password: str, is_superuser: bool = False) -> User:
    model = get_user_model()
    user = model.objects.create_user(
        username=username,
        email=email,
        password=password,
        is_superuser=is_superuser,
        is_staff=is_superuser,
        is_active=True
    )
    return user
