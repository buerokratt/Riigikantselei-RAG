from django.conf import settings

CORE_VARIABLE_CHOICES = [(a, a) for a in settings.CORE_SETTINGS.keys()]
