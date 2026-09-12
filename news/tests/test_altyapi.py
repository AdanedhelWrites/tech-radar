"""Altyapi testleri: Celery uygulamasinin yuklenmesi ve test izolasyonu."""
from django.test import SimpleTestCase


class CeleryUygulamasiTests(SimpleTestCase):
    """Django sureci proje Celery uygulamasini yuklemeli.

    Aksi halde task'lar Celery'nin 'default' uygulamasina baglanir ve sonuc
    backend'i devre disi kalir: AsyncResult hicbir isin durumunu okuyamaz.
    """

    def test_tasklar_proje_uygulamasina_bagli(self):
        from news.tasks import fetch_cve_task
        self.assertEqual(fetch_cve_task.app.main, 'cybernews')

    def test_sonuc_backendi_redis(self):
        from news.tasks import fetch_cve_task
        self.assertEqual(type(fetch_cve_task.app.backend).__name__, 'RedisBackend')

    def test_started_durumu_izleniyor(self):
        from news.tasks import fetch_cve_task
        self.assertTrue(fetch_cve_task.app.conf.task_track_started)


from django.conf import settings
from django.core.cache import caches


class TestIzolasyonuTests(SimpleTestCase):
    """View testleri canli Redis'e yazmamali ve WhiteNoise yuklememeli."""

    databases = {'default'}

    def test_v1_test_tabani_canli_redisi_kullanmaz(self):
        from news.tests.base import V1TestCase

        class Ornek(V1TestCase):
            def test_bos(self):
                pass

        # override_settings class decorator'i setUpClass icinde etkinlesir;
        # instance'in kendi _pre_setup'i degil, once sinifin setUpClass'ini
        # cagirmak gerekir.
        Ornek.setUpClass()
        try:
            ornek = Ornek('test_bos')
            ornek._pre_setup()
            try:
                self.assertEqual(type(caches['default']).__name__, 'LocMemCache')
                self.assertFalse(any('whitenoise' in m.lower() for m in settings.MIDDLEWARE))
            finally:
                ornek._post_teardown()
        finally:
            Ornek.tearDownClass()
