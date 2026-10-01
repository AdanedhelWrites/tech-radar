"""cybernews/ayar_dogrulama.py: uretimde ornek/zayif SECRET_KEY ile acilmayi reddetme.

Test kesfi yalniz `news` altinda calistigi icin (manage.py test news) test burada durur.
"""
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test import SimpleTestCase

from cybernews.ayar_dogrulama import (
    BILINEN_ORNEKLER, GELISTIRME_ANAHTARI, dogrulanmis_secret_key, veritabani_ayari,
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


KOK = Path('/uygulama')


class VeritabaniAyariTest(SimpleTestCase):
    """Faz B1 (spec 5.1): DB_HOST doluysa PostgreSQL; bossa yalniz DEBUG=True iken SQLite."""

    def test_db_host_doluysa_postgresql(self):
        ayar = veritabani_ayari({
            'DB_HOST': 'teknoloji-postgres', 'DB_NAME': 'ad', 'DB_USER': 'kul',
            'DB_PASSWORD': 'p', 'DB_PORT': '6543',
        }, debug=False, base_dir=KOK)['default']
        self.assertEqual(ayar['ENGINE'], 'django.db.backends.postgresql')
        self.assertEqual(
            (ayar['HOST'], ayar['NAME'], ayar['USER'], ayar['PASSWORD'], ayar['PORT']),
            ('teknoloji-postgres', 'ad', 'kul', 'p', '6543'))
        self.assertEqual(ayar['CONN_MAX_AGE'], 600)
        self.assertTrue(ayar['CONN_HEALTH_CHECKS'])
        self.assertEqual(ayar['OPTIONS'], {'connect_timeout': 10})

    def test_postgresql_varsayilanlari(self):
        ayar = veritabani_ayari({'DB_HOST': 'h'}, debug=False, base_dir=KOK)['default']
        self.assertEqual(
            (ayar['NAME'], ayar['USER'], ayar['PASSWORD'], ayar['PORT']),
            ('cybernews', 'cybernews', '', '5432'))

    def test_uretimde_db_host_yoksa_reddedilir(self):
        for ortam in ({}, {'DB_HOST': ''}, {'DB_HOST': '   '}):
            with self.subTest(ortam=ortam), self.assertRaises(ImproperlyConfigured):
                veritabani_ayari(ortam, debug=False, base_dir=KOK)

    def test_hata_mesaji_parolayi_icermez(self):
        with self.assertRaises(ImproperlyConfigured) as baglam:
            veritabani_ayari({'DB_PASSWORD': 'cok-gizli-parola'}, debug=False, base_dir=KOK)
        self.assertNotIn('cok-gizli-parola', str(baglam.exception))

    def test_gelistirmede_sqlite(self):
        ayar = veritabani_ayari({}, debug=True, base_dir=KOK)['default']
        self.assertEqual(ayar['ENGINE'], 'django.db.backends.sqlite3')
        self.assertEqual(ayar['NAME'], KOK / 'db.sqlite3')

    def test_database_url_okunmaz(self):
        """Eski settings DATABASE_URL doluysa PostgreSQL'e geciyor ama degerini hic okumuyordu."""
        ayar = veritabani_ayari({'DATABASE_URL': 'postgresql'}, debug=True, base_dir=KOK)['default']
        self.assertEqual(ayar['ENGINE'], 'django.db.backends.sqlite3')
        with self.assertRaises(ImproperlyConfigured):
            veritabani_ayari({'DATABASE_URL': 'postgresql'}, debug=False, base_dir=KOK)

    def test_test_ortami_postgresql(self):
        """settings.py fonksiyona bagli mi: testler yalniz PostgreSQL'de kosar (CI, pg_test.sh)."""
        self.assertEqual(connection.vendor, 'postgresql')
