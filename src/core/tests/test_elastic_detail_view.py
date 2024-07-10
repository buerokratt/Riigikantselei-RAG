import uuid

from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from api.utilities.elastic import ELASTIC_NOT_FOUND_MESSAGE, ElasticCore
from user_profile.utilities import create_test_user_with_user_profile


class TestElasticDetailView(APITestCase):
    def setUp(self) -> None:  # pylint: disable=invalid-name
        self.test_index = 'test_riigikantselei_elastic_detail_view'
        self.elastic_core = ElasticCore()
        self.elastic_core.create_index(self.test_index, shards=1, replicas=1)

        self.user = create_test_user_with_user_profile(
            self, 'user', 'user@email.com', 'Par@@l1234', is_manager=False
        )

        self.text = 'Yes, this is the content.'
        self.document_id = uuid.uuid4().hex

        self.elastic_core.elasticsearch.index(
            index=self.test_index,
            id=self.document_id,
            document={'text': self.text},
            refresh='wait_for',
        )

    def tearDown(self) -> None:  # pylint: disable=invalid-name
        self.elastic_core.elasticsearch.indices.delete(index=self.test_index, ignore=[400])

    def test_document_being_fetched_properly(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        detail_uri = reverse(
            'v1:document_detail', kwargs={'document_id': self.document_id, 'index': self.test_index}
        )
        response = self.client.get(detail_uri)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['text'], self.text)

    def test_false_index_throwing_404(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        detail_uri = reverse(
            'v1:document_detail',
            kwargs={'document_id': self.document_id, 'index': self.test_index[:-1]},
        )
        response = self.client.get(detail_uri)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], ELASTIC_NOT_FOUND_MESSAGE)

    def test_false_document_id_throwing_404(self) -> None:
        token, _ = Token.objects.get_or_create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')

        detail_uri = reverse(
            'v1:document_detail',
            kwargs={'document_id': self.document_id[:-1], 'index': self.test_index},
        )
        response = self.client.get(detail_uri)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.data['detail'], ELASTIC_NOT_FOUND_MESSAGE)