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
            # Django 4.2'de override_settings/modify_settings, setUpClass icinde
            # addClassCleanup ile kaydedilir; bu cleanup'lar normalde test suite'i
            # tearDownClass'tan SONRA doClassCleanups() cagirarak calistirir. Bu
            # test suite disinda setUpClass/tearDownClass'i elle tetikledigi icin
            # doClassCleanups() de elle cagrilmali; aksi halde CACHES/MIDDLEWARE
            # override'i geri alinmadan process'te kalir ve sonraki testleri
            # (ör. gercek settings.CACHES'i okuyan testler) bozar.
            Ornek.doClassCleanups()


from django.conf import settings as _ayarlar
from django.test import SimpleTestCase as _SimpleTestCase


class TestOrtamiIzolasyonuTests(_SimpleTestCase):
    """Testler canli LibreTranslate'e ve canli ceviri devre kesicisine dokunmamali.

    Dagitimdan sonra API konteynerinde LIBRETRANSLATE_URL tanimli olur ve testler
    ayni konteynerde kosar; bu testler o ortamda da gecmelidir.
    """

    def test_ozel_test_calistirici_ayarli(self):
        self.assertEqual(_ayarlar.TEST_RUNNER, 'news.test_runner.GuvenliTestRunner')

    def test_testlerde_libretranslate_kapali(self):
        self.assertEqual(_ayarlar.LIBRETRANSLATE_URL, '')

    def test_testlerde_libretranslate_devre_kesicisi_surec_ici(self):
        from news import translation_providers as tp
        from news import translation_utils as tu
        self.assertIsInstance(tp._get_lt_gate(), tu._LocalGate)

    def test_testlerde_gemini_surec_ici(self):
        from news import gemini
        from news import translation_utils as tu
        self.assertEqual(_ayarlar.GEMINI_API_KEY, '')
        self.assertIsInstance(gemini._get_gate(), tu._LocalGate)
        self.assertIsInstance(gemini._get_butce(), gemini._LocalButce)
