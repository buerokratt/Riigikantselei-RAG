# Create your tests here.
from rest_framework.test import APITestCase


class TestOpenAIWorkflows(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        pass

    def test_that_initial_query_to_openai_is_created_when_creating_conversation(self) -> None:
        pass

    def test_basic_workflow_functionality(self) -> None:
        pass

    def test_unauthenticated_users_being_denied_access_to(self) -> None:
        pass

    def test_that_messages_in_conversation_detail_are_in_proper_order(self) -> None:
        pass
