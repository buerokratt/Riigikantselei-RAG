from django.apps import AppConfig


class UserProfileConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_profile'

    def ready(self) -> None:
        """When app is loaded, load signals"""
        import user_profile.signals  # type: ignore
