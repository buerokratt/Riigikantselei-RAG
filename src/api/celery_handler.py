import logging
import os

from celery import Celery, Task

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'api.settings')
app = Celery('taskman')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

logger = logging.getLogger(__name__)


@app.task(bind=True)
def debug_task(self: Task) -> None:
    logger.info(f'Request: {self.request!r}')
