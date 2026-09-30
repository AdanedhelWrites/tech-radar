"""cybernews/ayar_dogrulama.py: uretimde ornek/zayif SECRET_KEY ile acilmayi reddetme.

Test kesfi yalniz `news` altinda calistigi icin (manage.py test news) test burada durur.
"""
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from cybernews.ayar_dogrulama import (
    BILINEN_ORNEKLER, GELISTIRME_ANAHTARI, dogrulanmis_secret_key,
)

GUCLU = 'a3f1' * 16  # 64 karakter, openssl rand -hex 32 ciktisi uzunlugunda


class UretimdeReddetmeTest(SimpleTestCase):

    def test_bos_anahtar_reddedilir(self):
        for deger in (None, ''):
            with self.subTest(deger=deger), self.assertRaises(ImproperlyConfigured):
                dogrulanmis_secret_key(deger, debug=False)

    def test_bilinen_ornekler_reddedilir(self):
        for deger in BILINEN_ORNEKLER:
            with self.subTest(deger=deger), self.assertRaises(ImproperlyConfigured):
                dogrulanmis_secret_key(deger, debug=False)

    def test_depodaki_tum_ornekler_listede(self):
        """compose, helm, k8s, README ve kokteki values.yaml'da gecmis degerler."""
        self.assertLessEqual({
            'your-secret-key-here-change-in-production',
            'buraya-guclu-rastgele-secret-key-yazin-min-50-karakter',
            'min-50-karakter-rastgele-guclu-bir-key',
            'django-insecure-change-in-production',
        }, BILINEN_ORNEKLER)

    def test_django_insecure_onekli_reddedilir(self):
        with self.assertRaises(ImproperlyConfigured):
            dogrulanmis_secret_key('django-insecure-' + 'x' * 60, debug=False)

    def test_kisa_anahtar_reddedilir(self):
        with self.assertRaises(ImproperlyConfigured):
            dogrulanmis_secret_key('k' * 31, debug=False)

    def test_hata_mesaji_anahtari_icermez(self):
        with self.assertRaises(ImproperlyConfigured) as baglam:
            dogrulanmis_secret_key('gizli-ama-kisa', debug=False)
        self.assertNotIn('gizli-ama-kisa', str(baglam.exception))

    def test_guclu_anahtar_aynen_doner(self):
        self.assertEqual(dogrulanmis_secret_key(GUCLU, debug=False), GUCLU)


class GelistirmedeEsneklikTest(SimpleTestCase):

    def test_debug_bos_anahtarda_gelistirme_anahtari_doner(self):
        self.assertEqual(dogrulanmis_secret_key(None, debug=True), GELISTIRME_ANAHTARI)
        self.assertEqual(dogrulanmis_secret_key('', debug=True), GELISTIRME_ANAHTARI)

    def test_debug_verilen_anahtari_dogrulamadan_kullanir(self):
        self.assertEqual(dogrulanmis_secret_key('kisa', debug=True), 'kisa')
