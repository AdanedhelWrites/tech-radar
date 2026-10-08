"""Admin girisinde kaba kuvvet korumasi (django-axes, 2026-10-08)."""
from axes.models import AccessAttempt
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings

from news.tests.base import LOCMEM_CACHE, TEST_MIDDLEWARE

PAROLA = 'dogru-parola-9f3a1c'


@override_settings(CACHES=LOCMEM_CACHE, MIDDLEWARE=TEST_MIDDLEWARE)
class AdminKilitTests(TestCase):

    def setUp(self):
        User.objects.create_superuser('yonetici', 'yonetici@ornek.test', PAROLA)
        User.objects.create_superuser('ikinci', 'ikinci@ornek.test', PAROLA)

    def _giris(self, kullanici, parola):
        return self.client.post('/admin/login/', {'username': kullanici, 'password': parola, 'next': '/admin/'})

    def test_ayarlar(self):
        self.assertIn('axes', settings.INSTALLED_APPS)
        self.assertEqual(settings.AUTHENTICATION_BACKENDS[0], 'axes.backends.AxesStandaloneBackend')
        self.assertIn('axes.middleware.AxesMiddleware', settings.MIDDLEWARE)
        self.assertEqual(settings.AXES_FAILURE_LIMIT, 5)
        self.assertEqual(settings.AXES_LOCKOUT_PARAMETERS, [['username', 'ip_address']])
        self.assertTrue(settings.AXES_RESET_ON_SUCCESS)

    def test_bes_yanlis_denemeden_sonra_dogru_parola_da_kilitli(self):
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self._giris('yonetici', 'yanlis')

        yanit = self._giris('yonetici', PAROLA)

        self.assertEqual(yanit.status_code, 429)  # AXES_HTTP_RESPONSE_CODE
        self.assertNotIn('_auth_user_id', self.client.session)
        self.assertGreaterEqual(AccessAttempt.objects.get(username='yonetici').failures_since_start,
                                settings.AXES_FAILURE_LIMIT)

    def test_limit_altinda_dogru_giris_calisir_ve_sayac_sifirlanir(self):
        for _ in range(settings.AXES_FAILURE_LIMIT - 1):
            self._giris('yonetici', 'yanlis')

        yanit = self._giris('yonetici', PAROLA)

        self.assertEqual(yanit.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)
        self.assertFalse(AccessAttempt.objects.filter(username='yonetici').exists())

    def test_kilit_baska_kullaniciyi_etkilemez(self):
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self._giris('yonetici', 'yanlis')

        yanit = self._giris('ikinci', PAROLA)

        self.assertEqual(yanit.status_code, 302)
        self.assertIn('_auth_user_id', self.client.session)
