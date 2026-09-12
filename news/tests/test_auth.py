"""v1 kimlik dogrulama testleri."""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token

from news.tests.base import V1TestCase


class HealthEndpointTests(V1TestCase):
    """health probe'lar icin acik olmali: token istemez, throttle uygulanmaz."""

    def test_tokensiz_erisilebilir(self):
        yanit = self.client.get('/api/v1/health/')
        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.json()['status'], 'ok')


class TokenAuthTests(V1TestCase):
    """v1 okuma uc noktalari token ister."""

    def setUp(self):
        super().setUp()
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


from unittest import mock


class HataBicimiTests(V1TestCase):
    """Tum v1 hatalari tek bicimde donmeli; tuketici tek bir ayristirici yazsin."""

    def setUp(self):
        super().setUp()
        kullanici = User.objects.create_user('hata-test', password='parola-yok-test')
        self.baslik = {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=kullanici).key}'}

    def test_401_tek_bicimde_doner(self):
        govde = self.client.get('/api/v1/ai/').json()
        self.assertEqual(govde['error']['code'], 'unauthorized')
        self.assertIn('message', govde['error'])

    def test_405_tek_bicimde_doner(self):
        yanit = self.client.post('/api/v1/ai/', **self.baslik)
        self.assertEqual(yanit.status_code, 405)
        self.assertEqual(yanit.json()['error']['code'], 'method_not_allowed')

    def test_429_retry_after_basligi_tasir(self):
        """Hiz siniri asildiginda tuketici ne kadar bekleyecegini bilmeli."""
        with mock.patch('rest_framework.throttling.ScopedRateThrottle.allow_request',
                        return_value=False), \
             mock.patch('rest_framework.throttling.ScopedRateThrottle.wait',
                        return_value=42):
            yanit = self.client.get('/api/v1/ai/', **self.baslik)
        self.assertEqual(yanit.status_code, 429)
        self.assertEqual(yanit.json()['error']['code'], 'throttled')
        self.assertEqual(yanit['Retry-After'], '42')

    def test_health_hata_bicimine_karismaz(self):
        yanit = self.client.get('/api/v1/health/')
        self.assertEqual(yanit.status_code, 200)
        self.assertNotIn('error', yanit.json())

    def test_beklenmeyen_hata_500_tek_bicimde_doner(self):
        """DRF'in taniyamadigi genel bir hata bile sozlesmedeki zarfa girmeli."""
        with mock.patch('news.api_v1.views.AIDeltaView.get_queryset',
                        side_effect=Exception('test')):
            yanit = self.client.get('/api/v1/ai/', **self.baslik)
        self.assertEqual(yanit.status_code, 500)
        govde = yanit.json()
        self.assertEqual(govde['error']['code'], 'internal')
        self.assertIn('message', govde['error'])
