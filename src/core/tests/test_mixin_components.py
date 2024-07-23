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

    def test_context_pruning_on_empty_string(self) -> None:
        context = ''
        pruned_context, is_pruned = ConversationMixin.prune_context(context=context)
        self.assertEqual(is_pruned, False)
        self.assertEqual(pruned_context, context)

    def test_that_a_single_prune_triggers_the_notifier(self) -> None:
        hits = [
            {'_id': '', '_index': '', '_source': {'text': ''}},
            {'_id': '', '_index': '', '_source': {'text': ''}},
            {'_id': '', '_index': '', '_source': {'text': 'hello world over there!'}},
        ]

        CoreVariable.objects.create(name='OPENAI_CONTEXT_MAX_TOKEN_LIMIT', value=1)
        question_references_prune = ConversationMixin.parse_gpt_question_and_references(
            user_input='coconuts', hits=hits
        )
        self.assertEqual(question_references_prune['is_context_pruned'], True)

    def test_that_every_singular_document_is_pruned(self) -> None:
        hits = [
            {'_id': '', '_index': '', '_source': {'text': 'hello world amigos'}},
        ]
        CoreVariable.objects.create(name='OPENAI_CONTEXT_MAX_TOKEN_LIMIT', value=1)
        hit_count = 3
        question_references_prune = ConversationMixin.parse_gpt_question_and_references(
            user_input='coconuts', hits=hits * hit_count
        )
        gpt_question = question_references_prune['context']
        self.assertEqual(question_references_prune['is_context_pruned'], True)
        self.assertEqual(gpt_question.count('hello'), hit_count)
