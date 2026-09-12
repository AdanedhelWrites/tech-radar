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
