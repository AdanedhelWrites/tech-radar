"""Cache testleri (spec bolum 10, A3 plani netlestirme 11-13)."""
from datetime import date
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from news import tasks
from news.models import AINewsEntry
from news.tests.base import LOCMEM_CACHE, V1TestCase
from news.tests.test_translation import FakeTranslator, TranslationGateMixin


@override_settings(CACHES=LOCMEM_CACHE)
class FetchCacheYenilemeTests(TranslationGateMixin, TestCase):
    """C1: cache her kayitta degil, her 10 kayitta bir ve cekim sonunda kurulur."""

    def setUp(self):
        super().setUp()
        cache.clear()
        # Bilinmeyen metne hata sayfasi: ilk cagrida devre kesici acilir, test hizli kalir
        self.use_translator(FakeTranslator())

    def _cek(self, adet):
        girdiler = [{
            'title': f'Cache test haberi {i}', 'description': f'Cache test govdesi {i}.',
            'link': f'https://ornek.test/cache/{i}', 'date': date.today().strftime('%Y-%m-%d'),
            'source': 'MIT Tech Review AI',
        } for i in range(adet)]
        from news import cache_utils
        with mock.patch.object(tasks.MultiAINewsScraper, 'fetch_all', return_value=girdiler), \
             mock.patch('news.tasks.cache_yenile', wraps=cache_utils.cache_yenile) as casus:
            sonuc = tasks.fetch_ai_news_task(days=30)
        return sonuc, casus

    def test_25_kayitta_cache_uc_kez_kurulur(self):
        sonuc, casus = self._cek(25)
        self.assertEqual(sonuc, {'success': True, 'count': 25})
        self.assertEqual(casus.call_count, 3)  # 10. kayit, 20. kayit, cekim sonu
        self.assertTrue(all(cagri.args == ('ai',) for cagri in casus.call_args_list))

    def test_cekim_sonunda_cache_tum_kayitlari_icerir(self):
        self._cek(25)
        self.assertEqual(len(cache.get('ai_entries')), 25)
        self.assertIsNotNone(cache.get('ai_last_update'))


@override_settings(CACHES=LOCMEM_CACHE)
class CacheYenileTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_liste_cache_en_yeni_100_kayitla_sinirlidir(self):
        """C5: bilincli sinir. Veritabanindaki fazlasi kayip degildir; v1 hepsini verir."""
        from news.cache_utils import CACHE_LISTE_SINIRI, cache_yenile
        for i in range(CACHE_LISTE_SINIRI + 5):
            AINewsEntry.objects.create(
                source='Test', original_title=f'Baslik {i}', original_description='X',
                link=f'https://ornek.test/sinir/{i}', published_date=date(2026, 9, 12))
        cache_yenile('ai')
        self.assertEqual(len(cache.get('ai_entries')), CACHE_LISTE_SINIRI)

    def test_bilinmeyen_bolum_reddedilir(self):
        from news.cache_utils import cache_yenile
        with self.assertRaises(KeyError):
            cache_yenile('olmayan')


class CacheSurumuTests(SimpleTestCase):

    def test_cache_anahtarlari_surumlu(self):
        """C3: serializer sekli degisince bu sayi artirilir; eski bloblar okunmaz."""
        self.assertEqual(settings.CACHES['default'].get('VERSION'), 3)


class V1CacheBagimsizligiTests(V1TestCase):
    """C2: v1 liste cache'ini okumaz. A1'de saglandi; bu test onu kilitler (ilk kosuda da gecer)."""

    def test_v1_cache_icerigini_kullanmaz(self):
        kayit = AINewsEntry.objects.create(
            source='Test', original_title='Gercek kayit', original_description='X',
            link='https://ornek.test/v1-cache', published_date=date(2026, 9, 12))
        cache.set('ai_entries', [{'id': 999999, 'sahte': True}], 3600)

        govde = self.client.get('/api/v1/ai/', **self.token_basligi()).json()

        self.assertEqual([k['id'] for k in govde['results']], [kayit.id])
