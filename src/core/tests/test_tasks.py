from time import sleep

from django.test import TestCase, override_settings

from api.utilities.core_settings import get_core_setting
from api.utilities.elastic import ElasticCore
from api.utilities.gpt import MOCK_HEADERS, MOCK_RESPONSE
from core.models import TextSearchConversation
from core.tasks import async_call_celery_task_chain
from user_profile.utilities import create_test_user_with_user_profile


class TestTaskChain(TestCase):
    # The combination of unit tests, Django DB and Celery does not work well,
    # so we use eager execution for this test.
    # Real Celery connection gets tested in src/api/utilities/tests/test_celery.py.
    @override_settings(CELERY_TASK_ALWAYS_EAGER=True)
    def test_output_format(self) -> None:
        index_names = ['test_a_1', 'test_a_2']

        # We wipe out all previous indices that have been created for the purpose of the test
        # because improper shutdowns etc may not reach tearDown and can cause stragglers.
        elastic_core = ElasticCore()
        for index_name in index_names:
            elastic_core.elasticsearch.indices.delete(index=index_name, ignore=[404])

            elastic_core.create_index(index_name, shards=3, replicas=1)

        auth_user = create_test_user_with_user_profile(
            self, 'tester', 'tester@email.com', 'password', is_manager=False
        )
        conversation = TextSearchConversation.objects.create(
            auth_user=auth_user, system_input=get_core_setting('OPENAI_SYSTEM_MESSAGE'), title=''
        )

        async_result = async_call_celery_task_chain(
            min_year=2020,
            max_year=2024,
            user_input='Asking about a topic',
            document_indices=index_names,
            conversation_id=conversation.id,
            document_types_string='a',
        )
        expected_output = {
            'conversation': conversation.id,
            'celery_task_id': async_result.task_id,
            'model': 'gpt-4o-2024-05-13',
            'min_year': 2020,
            'max_year': 2024,
            'document_types_string': 'a',
            'user_input': 'Asking about a topic',
            'response': MOCK_RESPONSE,
            'input_tokens': 20,
            'output_tokens': 9,
            'total_cost': 0.00023500000000000002,
            'response_headers': MOCK_HEADERS,
        }

        counter = 0
        while True:
            sleep(1)

            counter += 1
            if counter > 20:
                raise RuntimeError()

            if async_result.status in ['PENDING', 'STARTED']:
                continue

            if async_result.status == 'SUCCESS':
                self.assertEqual(async_result.result, expected_output)
                break

            raise RuntimeError(async_result.result)
