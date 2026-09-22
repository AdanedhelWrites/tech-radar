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

from news.models import NewsArticle


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
