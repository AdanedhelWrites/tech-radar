"""GET /api/saglik/ (2026-10-14 bakim dalgasi): anonim, dar, 60 sn cache'li saglik ozeti.

Neden: /api/v1/status/ token ister, arayuz anonimdir; sessiz kaynaklar curl rutinine kaldigi
icin 2026-10-08'den sonra kimse bakmadi. Bu uc yalniz tazelik + sessizlik verir; operator
alanlari (sources, total, by_provider, error) v1/status ve admin'de kalir.
"""
from datetime import date
from unittest import mock

from django.core.cache import cache

from news import gemini
from news import translation_utils as tu
from news.models import NewsArticle
from news.tests.base import V1TestCase
from news.tests.test_kaynak_sagligi import _tur


class SaglikUcuTests(V1TestCase):

    def setUp(self):
        super().setUp()
        cache.delete('saglik_ozeti')

    def test_tokensiz_200_ve_alti_bolum(self):
        yanit = self.client.get('/api/saglik/')

        self.assertEqual(yanit.status_code, 200)
        govde = yanit.json()
        self.assertIn('generated_at', govde)
        self.assertEqual(set(govde['sections']), {'news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai'})
        haber = govde['sections']['news']
        self.assertIsNone(haber['last_success_at'])
        self.assertIsNone(haber['last_status'])
        self.assertEqual(haber['silent_sources'], [])
        self.assertEqual(haber['pending_translation'], 0)

    def test_son_basarili_tur_ve_sessiz_kaynaklar(self):
        for i in range(4):
            _tur('news', {'Bleeping Computer': {'fetched': 0, 'saved': 0},
                          'The Hacker News': {'fetched': 5, 'saved': 1}}, i)
        NewsArticle.objects.create(source='The Hacker News', original_title='T', turkish_title='T',
                                   link='https://ornek.test/1', date=date(2026, 10, 14),
                                   original_date='2026-10-14', needs_translation=True)

        haber = self.client.get('/api/saglik/').json()['sections']['news']

        self.assertEqual(haber['last_status'], 'success')
        self.assertIsNotNone(haber['last_success_at'])
        self.assertEqual(haber['silent_sources'], ['Bleeping Computer'])
        self.assertEqual(haber['pending_translation'], 1)
        self.assertEqual(haber['translation_given_up'], 0)

    def test_son_tur_hatali_ama_son_basarili_ayri(self):
        _tur('cve', {'NVD': {'fetched': 3, 'saved': 1}}, 1)
        _tur('cve', {}, 0, status='failure')

        cve = self.client.get('/api/saglik/').json()['sections']['cve']

        self.assertEqual(cve['last_status'], 'failure')
        self.assertIsNotNone(cve['last_success_at'])

    def test_operator_alanlari_sizmaz(self):
        _tur('cve', {'NVD': {'fetched': 3, 'saved': 1}}, 0)

        cve = self.client.get('/api/saglik/').json()['sections']['cve']

        self.assertEqual(set(cve), {'last_success_at', 'last_status', 'pending_translation',
                                    'translation_given_up', 'upgrade_given_up', 'silent_sources'})

    def test_vazgecilen_yukseltmeleri_sayar(self):
        from news.retranslate import RETRANSLATE_MAX_ATTEMPTS

        def haber(slug, **ek):
            alanlar = dict(source='The Hacker News', original_title='T', turkish_title='T',
                           link=f'https://ornek.test/{slug}', date=date(2026, 11, 2),
                           original_date='2026-11-02', needs_translation=False,
                           translation_provider='libretranslate', translation_attempts=0)
            alanlar.update(ek)
            return NewsArticle.objects.create(**alanlar)

        haber('vazgecilen', translation_attempts=RETRANSLATE_MAX_ATTEMPTS)
        haber('denenen', translation_attempts=RETRANSLATE_MAX_ATTEMPTS - 1)
        haber('gemini', translation_provider='gemini', translation_attempts=RETRANSLATE_MAX_ATTEMPTS)
        haber('bekleyen', needs_translation=True, translation_attempts=RETRANSLATE_MAX_ATTEMPTS)

        sections = self.client.get('/api/saglik/').json()['sections']

        self.assertEqual(sections['news']['upgrade_given_up'], 1)
        self.assertEqual(sections['cve']['upgrade_given_up'], 0)

    def test_altmis_saniye_cache(self):
        self.client.get('/api/saglik/')
        _tur('sre', {'SRE Weekly': {'fetched': 1, 'saved': 0}}, 0)

        self.assertIsNone(self.client.get('/api/saglik/').json()['sections']['sre']['last_status'])
        cache.delete('saglik_ozeti')
        self.assertEqual(self.client.get('/api/saglik/').json()['sections']['sre']['last_status'], 'success')


class CeviriKuyruguTests(V1TestCase):
    """Bulgu 6 (2026-10-16): retranslate 3 gun ayni kayitta takili kaldi, serit her bolumu "ok" gosterdi.
    Serit artik ceviri kuyrugunu da gosterir: bekleyen (yeniden denenebilir) kayit ve son turlarin ilerlemesi."""

    def setUp(self):
        super().setUp()
        cache.delete('saglik_ozeti')

    def _haber(self, slug, deneme=0):
        return NewsArticle.objects.create(
            source='The Hacker News', original_title='T', turkish_title='T', link=f'https://ornek.test/{slug}',
            date=date(2026, 10, 21), original_date='2026-10-21', needs_translation=True,
            translation_attempts=deneme)

    def _retranslate(self, ilerleme, dakika_once, status='success'):
        from datetime import timedelta
        from django.utils import timezone
        from news.models import FetchRun
        kayit = FetchRun.objects.create(section='retranslate', status=status, saved_count=ilerleme)
        zaman = timezone.now() - timedelta(minutes=dakika_once)
        FetchRun.objects.filter(pk=kayit.pk).update(started_at=zaman, finished_at=zaman)

    def test_bos_kuyruk(self):
        kuyruk = self.client.get('/api/saglik/').json()['translation_queue']

        self.assertEqual(kuyruk, {'pending': 0, 'last_success_at': None, 'stalled': False})

    def test_bekleyen_yalniz_yeniden_denenebilir_kayitlari_sayar(self):
        from news.retranslate import RETRANSLATE_MAX_ATTEMPTS
        self._haber('a')
        self._haber('b', deneme=RETRANSLATE_MAX_ATTEMPTS)

        self.assertEqual(self.client.get('/api/saglik/').json()['translation_queue']['pending'], 1)

    def test_son_alti_tur_ilerlemediyse_takili(self):
        # Turlar saatlik (gunde 20): 6 tur ~6 saat ilerlemesizlik demektir.
        from news.fetch_runs import TAKILMA_TUR_SAYISI
        self.assertEqual(TAKILMA_TUR_SAYISI, 6)
        self._haber('a')
        self._retranslate(5, 600)
        for dk in (300, 240, 180, 120, 60, 5):
            self._retranslate(0, dk)

        kuyruk = self.client.get('/api/saglik/').json()['translation_queue']

        self.assertTrue(kuyruk['stalled'])
        self.assertIsNotNone(kuyruk['last_success_at'])

    def test_son_turlardan_biri_ilerlediyse_takili_degil(self):
        self._haber('a')
        for ilerleme, dk in ((0, 300), (0, 240), (3, 180), (0, 120), (0, 60), (0, 5)):
            self._retranslate(ilerleme, dk)

        self.assertFalse(self.client.get('/api/saglik/').json()['translation_queue']['stalled'])

    def test_bekleyen_yoksa_ilerlemesiz_turlar_takili_sayilmaz(self):
        for dk in (300, 240, 180, 120, 60, 5):
            self._retranslate(0, dk)

        self.assertFalse(self.client.get('/api/saglik/').json()['translation_queue']['stalled'])

    def test_retranslate_bolum_listesine_girmez(self):
        self._retranslate(1, 5)

        self.assertNotIn('retranslate', self.client.get('/api/saglik/').json()['sections'])


class _GeminiButceOrtami:
    """Butce ve kapi surec ici; canli Redis'e dokunulmaz."""

    def setUp(self):
        super().setUp()
        cache.delete('saglik_ozeti')
        for hedef, deger in (('_gate', tu._LocalGate()), ('_butce', gemini._LocalButce())):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)


class CeviriButcesiTests(_GeminiButceOrtami, V1TestCase):
    """Serit Gemini gunluk butcesini gosterir (2026-11-02): anahtar/kimlik alani asla yanita girmez."""

    def test_saglik_gemini_butcesini_gosterir(self):
        for _ in range(57):
            gemini._get_butce().artir(gemini.butce_anahtari())

        govde = self.client.get('/api/saglik/').json()

        butce = govde['translation_budget']['gemini']
        self.assertEqual(butce['used'], 57)
        self.assertEqual(butce['limit'], 450)
        self.assertEqual(butce['period'], 'day')
        self.assertIn('available', butce)
        self.assertIn('cooldown', butce)
        self.assertFalse(butce['cooldown'])
        self.assertEqual(set(butce), {'used', 'limit', 'period', 'available', 'cooldown'})
        ham = self.client.get('/api/saglik/').content.decode().lower()
        self.assertNotIn('key', ham)
        self.assertNotIn('api', ham)

    def test_butce_ozeti_devre_kesici_acikken_cooldown_doner(self):
        gemini._get_gate().start_cooldown(60)

        self.assertTrue(gemini.butce_ozeti()['cooldown'])
        self.assertFalse(gemini.butce_ozeti()['available'])

    def test_butce_ozeti_anahtar_sizdirmaz(self):
        with self.settings(GEMINI_API_KEY='gizli-anahtar-degeri'):
            ozet = gemini.butce_ozeti()

        self.assertNotIn('gizli-anahtar-degeri', str(ozet))
        self.assertTrue(ozet['available'])

    def test_butce_ozeti_redis_dusunce_cokmez(self):
        class Bozuk:
            def oku(self, anahtar):
                raise ConnectionError('redis yok')

            def cooldown_active(self):
                raise ConnectionError('redis yok')

        with mock.patch.object(gemini, '_butce', Bozuk()), mock.patch.object(gemini, '_gate', Bozuk()):
            ozet = gemini.butce_ozeti()

        self.assertEqual(ozet, {'used': 0, 'limit': 450, 'period': 'day',
                                'available': False, 'cooldown': False})


class YedekButceleriTests(_GeminiButceOrtami, V1TestCase):
    """PR-C (G7): translation_budget ayarli yedekleri de listeler; ayarsiz yedek ve anahtar degeri yanita girmez."""

    def setUp(self):
        super().setUp()
        from news import kayit_cevirmenleri as kc
        self.kc = kc
        for cevirmen in kc.YEDEKLER:
            for hedef, deger in (('_gate', tu._LocalGate()), ('_butce', gemini._LocalButce())):
                yama = mock.patch.object(cevirmen, hedef, deger)
                yama.start()
                self.addCleanup(yama.stop)

    def _butce(self):
        cache.delete('saglik_ozeti')
        return self.client.get('/api/saglik/').json()['translation_budget']

    def test_anahtarsiz_yalniz_gemini(self):
        self.assertEqual(set(self._butce()), {'gemini'})

    def test_ayarli_yedekler_listelenir_anahtar_sizmaz(self):
        self.kc.OPENROUTER._sayac().artir(self.kc.OPENROUTER._donem_anahtari())
        with self.settings(GEMINI_API_KEY='gizli-gemini-degeri', OPENROUTER_API_KEY='gizli-or-degeri',
                           DEEPL_API_KEY='gizli-deepl-degeri'), \
                mock.patch.object(self.kc.GEMINI2, 'model', 'gemini-yedek-model'), \
                mock.patch.object(self.kc.OPENROUTER, 'model', 'ornek/model:free'):
            butce = self._butce()
            ham = self.client.get('/api/saglik/').content.decode()

        self.assertEqual(set(butce), {'gemini', 'gemini2', 'openrouter', 'deepl'})
        self.assertEqual(butce['openrouter']['used'], 1)
        self.assertEqual(butce['deepl']['period'], 'month')
        for ozet in butce.values():
            self.assertEqual(set(ozet), {'used', 'limit', 'period', 'available', 'cooldown'})
        for gizli in ('gizli-gemini-degeri', 'gizli-or-degeri', 'gizli-deepl-degeri', 'gemini-yedek-model'):
            self.assertNotIn(gizli, ham)

    def test_modeli_bos_yedek_listelenmez(self):
        """Anahtar dolu ama model bos (GEMINI_FALLBACK_MODEL / OPENROUTER_MODEL): ayarsiz sayilir."""
        with self.settings(GEMINI_API_KEY='gizli', OPENROUTER_API_KEY='gizli', DEEPL_API_KEY=''), \
                mock.patch.object(self.kc.GEMINI2, 'model', ''), \
                mock.patch.object(self.kc.OPENROUTER, 'model', ''):
            self.assertEqual(set(self._butce()), {'gemini'})
