"""GET /api/saglik/ (2026-10-14 bakim dalgasi): anonim, dar, 60 sn cache'li saglik ozeti.

Neden: /api/v1/status/ token ister, arayuz anonimdir; sessiz kaynaklar curl rutinine kaldigi
icin 2026-10-08'den sonra kimse bakmadi. Bu uc yalniz tazelik + sessizlik verir; operator
alanlari (sources, total, by_provider, error) v1/status ve admin'de kalir.
"""
from datetime import date

from django.core.cache import cache

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
                                    'translation_given_up', 'silent_sources'})

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

    def test_son_uc_tur_ilerlemediyse_takili(self):
        self._haber('a')
        self._retranslate(5, 400)
        for dk in (240, 120, 5):
            self._retranslate(0, dk)

        kuyruk = self.client.get('/api/saglik/').json()['translation_queue']

        self.assertTrue(kuyruk['stalled'])
        self.assertIsNotNone(kuyruk['last_success_at'])

    def test_son_turlardan_biri_ilerlediyse_takili_degil(self):
        self._haber('a')
        for ilerleme, dk in ((0, 240), (3, 120), (0, 5)):
            self._retranslate(ilerleme, dk)

        self.assertFalse(self.client.get('/api/saglik/').json()['translation_queue']['stalled'])

    def test_bekleyen_yoksa_ilerlemesiz_turlar_takili_sayilmaz(self):
        for dk in (240, 120, 5):
            self._retranslate(0, dk)

        self.assertFalse(self.client.get('/api/saglik/').json()['translation_queue']['stalled'])

    def test_retranslate_bolum_listesine_girmez(self):
        self._retranslate(1, 5)

        self.assertNotIn('retranslate', self.client.get('/api/saglik/').json()['sections'])
