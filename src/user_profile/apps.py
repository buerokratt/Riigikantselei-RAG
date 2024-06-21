from django.apps import AppConfig


class UserProfileConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_profile'

    def ready(self) -> None:
        """When app is loaded, load signals"""
        # pylint: disable=import-outside-toplevel,unused-import
        import user_profile.signals
