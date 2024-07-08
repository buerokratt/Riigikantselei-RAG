from time import sleep
from unittest import TestCase

from django.test import override_settings

from api.celery_handler import debug_task


class TestCelery(TestCase):
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_celery_connection(self) -> None:
        debug_task.delay()

        async_result = debug_task.apply_async()
        counter = 0

        while True:
            sleep(0.1)

            counter += 1
            if counter > 20:
                raise RuntimeError('Time out!')

            if async_result.status in ['PENDING', 'STARTED']:
                continue

            if async_result.status == 'SUCCESS':
                break

            raise RuntimeError(async_result.result)
