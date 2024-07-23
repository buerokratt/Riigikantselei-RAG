from rest_framework.test import APITestCase

from core.mixins import ConversationMixin
from core.models import CoreVariable


class TestMixinComponents(APITestCase):
    def test_pruning_context_thats_too_large(self) -> None:
        CoreVariable.objects.create(name='OPENAI_CONTEXT_MAX_TOKEN_LIMIT', value=1)
        pruned_context, is_pruned = ConversationMixin.prune_context(context='hello world')
        self.assertEqual(is_pruned, True)
        self.assertEqual(pruned_context, 'hello')

    def test_pruning_isnt_overly_eager(self) -> None:
        context = 'How could a 5 ounce bird carry a 1 ounce coconut???'
        pruned_context, is_pruned = ConversationMixin.prune_context(context=context)
        self.assertEqual(is_pruned, False)
        self.assertEqual(pruned_context, context)
