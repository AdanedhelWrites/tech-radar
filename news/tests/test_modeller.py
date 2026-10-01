"""Model duzeyindeki veri butunlugu kisitlari.

`NewsArticle.link` uzerindeki tekillik kisiti: yazma yolu (news/tasks.py)
`update_or_create(link=...)` ile calisir, yani link'in tekil oldugunu ZATEN
varsayar. Diger bes bolumde (CVEEntry.cve_id ve Kubernetes/SRE/DevTools/
AINews.link) bu kisit semada da vardi; NewsArticle istisnaydi. Sema garanti
etmedigi surece iki es zamanli cekim ayni link'i iki kayit olarak yazabilir
ve tuketicinin upsert anahtari (ADR-0005) sessizce bozulur.
"""
from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase

from news.models import CVEEntry, KubernetesEntry, NewsArticle


class NewsArticleLinkTekilligiTests(TestCase):

    def _kayit(self, link):
        return NewsArticle.objects.create(
            source='test',
            original_title='baslik',
            turkish_title='baslik',
            link=link,
            date=date(2026, 1, 1),
            original_date='2026-01-01',
        )

    def test_ayni_link_ikinci_kez_eklenemez(self):
        self._kayit('https://ornek.test/haber-1')
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._kayit('https://ornek.test/haber-1')

    def test_farkli_linkler_eklenebilir(self):
        self._kayit('https://ornek.test/haber-1')
        self._kayit('https://ornek.test/haber-2')
        self.assertEqual(NewsArticle.objects.count(), 2)


class LinkUzunluguTests(TestCase):
    """Faz B1 / 0013: PostgreSQL max_length uygular (SQLite uygulamazdi); uc bolumde link 500."""

    UZUN = 'https://ornek.com/' + 'a' * 450

    def test_alan_sinirlari(self):
        for model in (NewsArticle, CVEEntry, KubernetesEntry):
            with self.subTest(model=model.__name__):
                self.assertEqual(model._meta.get_field('link').max_length, 500)

    def test_uzun_link_yazilir(self):
        NewsArticle.objects.create(
            source='Ornek', original_title='t', turkish_title='t', link=self.UZUN,
            date=date(2026, 9, 18), original_date='18 Sep 2026')
        CVEEntry.objects.create(
            cve_id='CVE-2026-9999', source='NVD', original_title='t', original_description='d',
            published_date=date(2026, 9, 18), link=self.UZUN)
        KubernetesEntry.objects.create(
            source='Kubernetes', original_title='t', original_description='d', link=self.UZUN,
            published_date=date(2026, 9, 18))
        self.assertEqual(KubernetesEntry.objects.get().link, self.UZUN)
