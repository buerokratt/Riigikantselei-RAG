from django.conf import settings

CORE_VARIABLE_CHOICES = [(a, a) for a in settings.CORE_SETTINGS.keys()]


class TaskStatus:
    PENDING = 'PENDING'
    STARTED = 'STARTED'
    SUCCESS = 'SUCCESS'
    FAILURE = 'FAILURE'


TASK_STATUS_CHOICES = [
    (TaskStatus.PENDING, TaskStatus.PENDING),
    (TaskStatus.STARTED, TaskStatus.STARTED),
    (TaskStatus.SUCCESS, TaskStatus.SUCCESS),
    (TaskStatus.FAILURE, TaskStatus.FAILURE),
]
