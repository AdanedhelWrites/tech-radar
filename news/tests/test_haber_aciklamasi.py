"""Haber (NewsArticle) aciklamasinin kaybolmasi.

2026-09-15 bulgusu: scraper_multi.process_news ciktisinda `original_description`
yoktu; fetch_news_task bos yaziyordu. A3 retranslate bu bos orijinali cevirip
`turkish_description`'i bosla ezdi ("Icerik bulunmuyor", 18 kayit).
"""
from datetime import date
from unittest import mock

from django.test import SimpleTestCase

from news.models import NewsArticle
from news.tests.test_retranslate import RetranslateTestBase
from news.tests.test_translation import FakeTranslator


class RetranslateBosOrijinalTests(RetranslateTestBase):

    def _haber(self, orijinal_aciklama, turkce_aciklama):
        return NewsArticle.objects.create(
            source='The Hacker News', original_title='Story number 1 published',
            turkish_title='Story number 1 published',
            original_description=orijinal_aciklama, turkish_description=turkce_aciklama,
            link='https://ornek.test/haber/1', date=date(2026, 9, 14), original_date='2026-09-14',
            needs_translation=True)

    def test_bos_orijinal_turkce_aciklamayi_ezmez(self):
        self.use_translator(FakeTranslator({'Story number 1 published': '1 numaralı haber yayımlandı'}))
        kayit = self._haber('', 'Mevcut Türkçe gövde korunmalı.')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(sonuc['sections']['news']['translated'], 1)
        self.assertEqual(kayit.turkish_title, '1 numaralı haber yayımlandı')
        self.assertEqual(kayit.turkish_description, 'Mevcut Türkçe gövde korunmalı.')
        self.assertFalse(kayit.needs_translation)

    def test_dolu_orijinal_normal_cevrilir(self):
        self.use_translator(FakeTranslator({'Story number 1 published': '1 numaralı haber yayımlandı',
                                            'Body text for story 1.': '1. haberin gövde metni.'}))
        kayit = self._haber('Body text for story 1.', 'Body text for story 1.')

        self._calistir()

        kayit.refresh_from_db()
        # turkish_post_process cumle basini buyutur
        self.assertEqual(kayit.turkish_description, '1. Haberin gövde metni.')


class ProcessNewsOrijinalAciklamaTests(SimpleTestCase):

    def _makale(self):
        return {'title': 'Story number 1 published', 'description': 'Body text for story 1.',
                'link': 'https://ornek.test/haber/1', 'date': date(2026, 9, 14),
                'original_date': '2026-09-14', 'source': 'The Hacker News'}

    def test_process_news_orijinal_aciklamayi_verir(self):
        from scraper_multi import MultiSourceScraper
        with mock.patch('scraper_multi.translate_text', side_effect=lambda t: 'TR ' + t), \
             mock.patch('scraper_multi.translate_long_text', side_effect=lambda t: 'TR ' + t):
            cikti = list(MultiSourceScraper().process_news([self._makale()]))
        self.assertEqual(cikti[0]['original_description'], 'Body text for story 1.')
        self.assertEqual(cikti[0]['turkish_description'], 'TR Body text for story 1.')

    def test_hata_yolunda_da_orijinal_aciklama_verilir(self):
        from scraper_multi import MultiSourceScraper
        with mock.patch('scraper_multi.translate_text', side_effect=RuntimeError('patladi')), \
             mock.patch('scraper_multi.translate_long_text', side_effect=RuntimeError('patladi')):
            cikti = list(MultiSourceScraper().process_news([self._makale()]))
        self.assertEqual(cikti[0]['original_description'], 'Body text for story 1.')
        self.assertEqual(cikti[0]['turkish_description'], 'Body text for story 1.')
