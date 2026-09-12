"""v1 kimlik dogrulama testleri."""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token


class HealthEndpointTests(TestCase):
    """health probe'lar icin acik olmali: token istemez, throttle uygulanmaz."""

    def test_tokensiz_erisilebilir(self):
        yanit = self.client.get('/api/v1/health/')
        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.json()['status'], 'ok')


class TokenAuthTests(TestCase):
    """v1 okuma uc noktalari token ister."""

    def setUp(self):
        self.kullanici = User.objects.create_user('entegrasyon', password='parola-yok-test')
        self.token = Token.objects.create(user=self.kullanici)

    def test_tokensiz_401(self):
        yanit = self.client.get('/api/v1/ai/')
        self.assertEqual(yanit.status_code, 401)

    def test_gecersiz_token_401(self):
        yanit = self.client.get('/api/v1/ai/', HTTP_AUTHORIZATION='Token gecersiz-deger')
        self.assertEqual(yanit.status_code, 401)

    def test_gecerli_token_200(self):
        yanit = self.client.get('/api/v1/ai/', HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.assertEqual(yanit.status_code, 200)
