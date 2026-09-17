"""Saklama (retention) davranisi — ADR-0005.

Silme olcusu `published_date` degil `updated_at`'tir: "bu kayda en son ne zaman
dokunduk". Eski yayimlanmis ama kaynagin dondurmeye devam ettigi kayitlar
(NVD Guncel akisi) artik her cekimde silinip yeni id ile geri yazilmaz.

Hicbir scraper agla konusmaz; hepsi mock'lanir ve bos liste dondurur, boylece
yalnizca task'in silme adimi calisir.
"""
from datetime import date, timedelta
from unittest import mock

from django.test import TestCase
from django.utils import timezone

from news import tasks
from news.models import AINewsEntry, CVEEntry, NewsArticle


def _eskit(model, pk, gun):
    """Kaydin updated_at'ini `gun` kadar geriye alir.

    `updated_at` auto_now oldugu icin save() her zaman simdiyi yazar; geriye
    almanin tek yolu auto_now'u atlayan QuerySet.update()'tir.
    """
    model.objects.filter(pk=pk).update(updated_at=timezone.now() - timedelta(days=gun))


class CVESaklamaTests(TestCase):
    """CVE bolumu: churn'un gozlendigi ve olculdugu bolum."""

    def setUp(self):
        yama = mock.patch('news.tasks.MultiCVEScraper')
        self.scraper = yama.start()
        self.addCleanup(yama.stop)
        self.scraper.return_value.fetch_all_cves.return_value = []

    def _cve(self, no, yayim_gun_once):
        return CVEEntry.objects.create(
            cve_id=f'CVE-2026-{no}', source='NVD Güncel',
            original_title=f'CVE-2026-{no} - Guvenlik Acigi',
            original_description='Ornek aciklama metni.',
            published_date=date.today() - timedelta(days=yayim_gun_once),
            link=f'https://ornek.test/cve/{no}')

    def test_eski_yayimli_ama_yeni_dokunulmus_kayit_silinmez(self):
        """Churn regresyonu: NVD Guncel Ocak'ta yayimlanmis CVE'leri donmeye devam ediyor."""
        kayit = self._cve('9001', yayim_gun_once=252)

        tasks.fetch_cve_task(days=7)

        self.assertTrue(CVEEntry.objects.filter(pk=kayit.pk).exists(),
                        'Yayim tarihi eski ama yeni dokunulmus kayit silinmemeliydi')

    def test_saklama_penceresinden_eski_kayit_silinir(self):
        kayit = self._cve('9002', yayim_gun_once=0)
        _eskit(CVEEntry, kayit.pk, 91)

        tasks.fetch_cve_task(days=7)

        self.assertFalse(CVEEntry.objects.filter(pk=kayit.pk).exists())

    def test_pencere_icinde_dokunulmus_kayit_silinmez(self):
        kayit = self._cve('9003', yayim_gun_once=200)
        _eskit(CVEEntry, kayit.pk, 89)

        tasks.fetch_cve_task(days=7)

        self.assertTrue(CVEEntry.objects.filter(pk=kayit.pk).exists())

    def test_cekim_penceresi_saklamayi_etkilemez(self):
        """`days` yalnizca kaynaktan ne kadar geriye gidilecegini belirler."""
        kayit = self._cve('9004', yayim_gun_once=300)

        tasks.fetch_cve_task(days=1)

        self.assertTrue(CVEEntry.objects.filter(pk=kayit.pk).exists())
        cagri = self.scraper.return_value.fetch_all_cves.call_args
        self.assertEqual(cagri.kwargs['days'], 1, 'Cekim penceresi task parametresinden gelmeli')


class DigerBolumlerSaklamaTests(TestCase):
    """Kural alti bolumde ayni. news ayrica `date__lt` kullaniyordu; o da kalkti."""

    def test_haber_saklamasi_updated_at_kullanir(self):
        yama = mock.patch('news.tasks.MultiSourceScraper')
        scraper = yama.start()
        self.addCleanup(yama.stop)
        scraper.return_value.fetch_all_news.return_value = []

        eski_tarihli = NewsArticle.objects.create(
            source='Test', original_title='Eski haber', turkish_title='Eski haber',
            link='https://ornek.test/haber/1', date=date.today() - timedelta(days=300),
            original_date='2026-01-01')
        dokunulmamis = NewsArticle.objects.create(
            source='Test', original_title='Bayat haber', turkish_title='Bayat haber',
            link='https://ornek.test/haber/2', date=date.today(), original_date='2026-09-17')
        _eskit(NewsArticle, dokunulmamis.pk, 91)

        tasks.fetch_news_task(days=7)

        self.assertTrue(NewsArticle.objects.filter(pk=eski_tarihli.pk).exists(),
                        'Yayim tarihi degil, son dokunma belirleyici olmali')
        self.assertFalse(NewsArticle.objects.filter(pk=dokunulmamis.pk).exists())

    def test_ai_saklamasi_updated_at_kullanir(self):
        yama = mock.patch('news.tasks.MultiAINewsScraper')
        scraper = yama.start()
        self.addCleanup(yama.stop)
        scraper.return_value.fetch_all.return_value = []

        kayit = AINewsEntry.objects.create(
            source='Test', original_title='Eski AI haberi',
            original_description='Govde.', link='https://ornek.test/ai/1',
            published_date=date.today() - timedelta(days=300))

        tasks.fetch_ai_news_task(days=30)

        self.assertTrue(AINewsEntry.objects.filter(pk=kayit.pk).exists())
