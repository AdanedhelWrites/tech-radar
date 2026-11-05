"""Cache testleri.

2026-11-05: Bolum basina liste cache'i (`cybersecurity_news`, `cve_entries` ...;
eski news/cache_utils.py) kaldirildi. Liste uclari veritabanindan sayfalanir
(news/liste_sorgusu.py); cache'i yalniz istatistiklerdeki `cached` bayragi okuyordu.
Ayni temizlikte arayuzun artik cagirmadigi /api/*/export/ uclari da kaldirildi.
"""
from datetime import date
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from news import tasks
from news.tests.base import LOCMEM_CACHE, V1TestCase
from news.tests.test_translation import FakeTranslator, TranslationGateMixin

# Kaldirilan liste cache'inin anahtarlari: hicbir kod yolu bunlari yeniden yazmamali
ESKI_LISTE_ANAHTARLARI = (
    'cybersecurity_news', 'last_update', 'cve_entries', 'cve_last_update',
    'k8s_entries', 'k8s_last_update', 'sre_entries', 'sre_last_update',
    'devtools_entries', 'devtools_last_update', 'ai_entries', 'ai_last_update',
)

STATS_UCLARI = ('/api/stats/', '/api/cve/stats/', '/api/k8s/stats/', '/api/sre/stats/',
                '/api/devtools/stats/', '/api/ai/stats/')
EXPORT_UCLARI = ('/api/export/', '/api/cve/export/', '/api/k8s/export/', '/api/sre/export/',
                 '/api/devtools/export/', '/api/ai/export/')


@override_settings(CACHES=LOCMEM_CACHE)
class FetchListeCacheYazmazTests(TranslationGateMixin, TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        # Bilinmeyen metne hata sayfasi: ilk cagrida devre kesici acilir, test hizli kalir
        self.use_translator(FakeTranslator())

    def test_cekim_liste_cache_anahtari_yazmaz(self):
        girdiler = [{
            'title': f'Cache test haberi {i}', 'description': f'Cache test govdesi {i}.',
            'link': f'https://ornek.test/cache/{i}', 'date': date.today().strftime('%Y-%m-%d'),
            'source': 'MIT Tech Review AI',
        } for i in range(12)]
        with mock.patch.object(tasks.MultiAINewsScraper, 'fetch_all', return_value=girdiler):
            sonuc = tasks.fetch_ai_news_task(days=30)

        self.assertEqual(sonuc['count'], 12)
        self.assertEqual({a: cache.get(a) for a in ESKI_LISTE_ANAHTARLARI},
                         dict.fromkeys(ESKI_LISTE_ANAHTARLARI))


class EskiUclarTests(V1TestCase):

    def test_stats_cached_alani_tasimaz(self):
        for url in STATS_UCLARI:
            with self.subTest(url=url):
                govde = self.client.get(url).json()
                self.assertTrue(govde['success'])
                self.assertNotIn('cached', govde)
                self.assertIn('total', govde)

    def test_export_uclari_kaldirildi(self):
        for url in EXPORT_UCLARI:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)


class CacheSurumuTests(SimpleTestCase):

    def test_cache_anahtarlari_surumlu(self):
        """C3: serializer sekli degisince bu sayi artirilir; eski bloblar okunmaz."""
        self.assertEqual(settings.CACHES['default'].get('VERSION'), 3)
