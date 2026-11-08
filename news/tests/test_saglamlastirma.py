"""2026-11-07 tam inceleme 4. dalga: saglamlastirma. Ag erisimi yok."""
import importlib
import uuid
from datetime import date, datetime
from unittest import mock

import requests
from django.apps import apps
from django.test import SimpleTestCase, TestCase

import scraper_multi
from news import gemini, tasks
from news.base_scraper import BaseRSSScraper, ay_tarihi_coz
from news.models import AINewsEntry, CVEEntry, NewsArticle
from news.tests.base import test_redis_client


class AyTarihiTests(SimpleTestCase):

    def test_metnin_icinden_ayiklar(self):
        for metin, beklenen in (
            ('Nov 07, 2026', datetime(2026, 11, 7)),     # The Hacker News ikon karakteri
            ('November 7, 2026', datetime(2026, 11, 7)),
            ('Sept. 3, 2026', datetime(2026, 9, 3)),
            ('Published on Feb 24 2026 by X', datetime(2026, 2, 24)),
        ):
            with self.subTest(metin):
                self.assertEqual(ay_tarihi_coz(metin), beklenen)

    def test_okunamayan_none(self):
        for metin in ('', None, 'dun', 'Feb 31, 2026', 'Nov 07, 202606'):
            with self.subTest(metin):
                self.assertIsNone(ay_tarihi_coz(metin))

    def test_haber_kaynagi_okunamayani_bugune_dusurur_ve_loglar(self):
        kaynak = scraper_multi.TheHackerNewsSource()
        self.assertEqual(kaynak._parse_date('Nov 05, 2026'), datetime(2026, 11, 5))
        with self.assertLogs('scraper_multi', level='WARNING') as kayit:
            sonuc = kaynak._parse_date('bilinmeyen')
        self.assertEqual(sonuc.date(), date.today())
        self.assertIn('Tarih okunamadi', kayit.output[0])


class HaberTarihiGocuTests(TestCase):

    def test_okunabilen_ve_farkli_tarih_duzeltilir(self):
        bozuk = NewsArticle.objects.create(
            source='The Hacker News', original_title='T', turkish_title='T', link='https://ornek.test/thn/1',
            date=date(2026, 11, 7), original_date='Nov 05, 2026')
        dogru = NewsArticle.objects.create(
            source='Bleeping Computer', original_title='T', turkish_title='T', link='https://ornek.test/bc/1',
            date=date(2026, 11, 6), original_date='November 6, 2026')
        okunamayan = NewsArticle.objects.create(
            source='X', original_title='T', turkish_title='T', link='https://ornek.test/x/1',
            date=date(2026, 11, 7), original_date='dun')
        once = NewsArticle.objects.get(pk=bozuk.pk).updated_at

        goc = importlib.import_module('news.migrations.0019_haber_tarihi_duzelt')
        goc.tarihleri_duzelt(apps, None)

        for kayit in (bozuk, dogru, okunamayan):
            kayit.refresh_from_db()
        self.assertEqual(bozuk.date, date(2026, 11, 5))
        self.assertEqual(bozuk.updated_at, once, 'Goc updated_at ilerletmez')
        self.assertEqual(dogru.date, date(2026, 11, 6))
        self.assertEqual(okunamayan.date, date(2026, 11, 7))


class RssDurumKoduTests(SimpleTestCase):

    def test_403_yaniti_loglanir_bos_doner(self):
        yanit = requests.Response()
        yanit.status_code = 403
        yanit._content = b'<html>Forbidden</html>'
        yanit.url = 'https://ornek.test/feed'
        scraper = BaseRSSScraper()
        with mock.patch.object(scraper.session, 'get', return_value=yanit), \
                self.assertLogs('news.base_scraper', level='WARNING') as kayit:
            self.assertEqual(scraper.fetch_standard_rss_entries('https://ornek.test/feed', 'Ornek'), [])
        self.assertIn('403', kayit.output[0])


def _ai(link, **ek):
    alanlar = {'source': 'S', 'original_title': 'Title', 'turkish_title': 'Başlık',
               'original_description': 'Body', 'turkish_description': 'Gövde', 'published_date': date(2026, 11, 7),
               'needs_translation': False, 'translation_provider': 'gemini'}
    alanlar.update(ek)
    return AINewsEntry.objects.create(link=link, **alanlar)


class KaydetYarisiTests(TestCase):
    """Scraper turu suresince retranslate'in yazdigi daha iyi ceviri ezilmez."""

    def _yaz(self, link, **ek):
        defaults = {'source': 'Yeni kaynak', 'original_title': 'Title', 'turkish_title': 'LT başlık',
                    'original_description': 'Body', 'turkish_description': 'LT gövde',
                    'published_date': date(2026, 11, 8), 'needs_translation': False,
                    'translation_provider': 'libretranslate'}
        defaults.update(ek)
        tasks._kaydet(AINewsEntry, link=link, defaults=defaults)
        return AINewsEntry.objects.get(link=link)

    def test_gemini_cevirisi_libretranslate_ile_ezilmez_diger_alanlar_yazilir(self):
        _ai('https://ornek.test/1')
        kayit = self._yaz('https://ornek.test/1')
        self.assertEqual((kayit.turkish_title, kayit.translation_provider), ('Başlık', 'gemini'))
        self.assertEqual((kayit.source, kayit.published_date), ('Yeni kaynak', date(2026, 11, 8)))

    def test_basarisiz_ceviri_cevrilmis_kaydi_ezmez(self):
        _ai('https://ornek.test/2', translation_provider='libretranslate')
        kayit = self._yaz('https://ornek.test/2', turkish_title='Title', needs_translation=True,
                          translation_provider='')
        self.assertEqual((kayit.turkish_title, kayit.needs_translation), ('Başlık', False))

    def test_ayni_kalite_ve_bekleyen_kayit_yazilir(self):
        _ai('https://ornek.test/3', translation_provider='libretranslate')
        self.assertEqual(self._yaz('https://ornek.test/3').turkish_title, 'LT başlık')
        _ai('https://ornek.test/4', needs_translation=True, translation_provider='')
        self.assertEqual(self._yaz('https://ornek.test/4').turkish_title, 'LT başlık')

    def test_yeni_kayit_olusur(self):
        self.assertEqual(self._yaz('https://ornek.test/5').turkish_title, 'LT başlık')

    def test_cve_yolu(self):
        CVEEntry.objects.create(
            cve_id='CVE-2026-7777', source='NVD', original_title='CVE-2026-7777 - Güvenlik Açığı',
            turkish_title='CVE-2026-7777 - Güvenlik Açığı', original_description='Body',
            turkish_description='Gemini gövde', published_date=date(2026, 11, 7), link='https://ornek.test/c',
            translation_provider='gemini')
        tasks._kaydet(CVEEntry, {'turkish_description': 'LT gövde', 'cvss_score': 9.1,
                                 'needs_translation': False, 'translation_provider': 'libretranslate'},
                      cve_id='CVE-2026-7777')
        kayit = CVEEntry.objects.get(cve_id='CVE-2026-7777')
        self.assertEqual((kayit.turkish_description, kayit.cvss_score), ('Gemini gövde', 9.1))


class RedisYedekDonusuTests(SimpleTestCase):
    """Redis yokken kurulan yerel yedek sayac kalici kaliyordu; Redis donunce paylasilan sayaca gecilmeli."""

    def setUp(self):
        self.onek = f'test-yedek-{uuid.uuid4().hex}'
        self.redis = test_redis_client()
        self.addCleanup(lambda: [self.redis.delete(k) for k in self.redis.scan_iter(f'{self.onek}:*')])

    def test_yedek_suresi_dolunca_redise_doner_ve_sayimi_aktarir(self):
        with mock.patch.object(gemini, '_redis_client', return_value=None):
            sayac = gemini._sayac_kur(None, self.onek, 60)
        self.assertIsInstance(sayac, gemini._LocalButce)
        sayac.artir('budget:2026-11-07', 3)
        self.assertFalse(gemini._yedek_suresi_doldu(sayac))

        sayac.kurulma -= gemini.REDIS_YENIDEN_DENEME_SN
        self.assertTrue(gemini._yedek_suresi_doldu(sayac))
        with mock.patch.object(gemini, '_redis_client', return_value=self.redis):
            yeni = gemini._sayac_kur(sayac, self.onek, 60)
        self.assertIsInstance(yeni, gemini._RedisButce)
        self.assertEqual(yeni.oku('budget:2026-11-07'), 3, 'Kesintide harcanan butce kaybolmaz')

    def test_redis_hala_yoksa_ayni_yedek_surer(self):
        with mock.patch.object(gemini, '_redis_client', return_value=None):
            sayac = gemini._sayac_kur(None, self.onek, 60)
            sayac.artir('budget:x', 2)
            sayac.kurulma -= gemini.REDIS_YENIDEN_DENEME_SN
            ayni = gemini._sayac_kur(sayac, self.onek, 60)
        self.assertIs(ayni, sayac)
        self.assertEqual(ayni.oku('budget:x'), 2)
        self.assertFalse(gemini._yedek_suresi_doldu(ayni))

    def test_testin_verdigi_yerel_sayac_yedek_sayilmaz(self):
        self.assertFalse(gemini._yedek_suresi_doldu(gemini._LocalButce()))

    def test_modul_sayaci_yedekten_doner(self):
        with mock.patch.object(gemini, '_butce', None), \
                mock.patch.object(gemini, '_redis_client', return_value=None):
            yedek = gemini._get_butce()
            self.assertIs(gemini._get_butce(), yedek)
            yedek.kurulma -= gemini.REDIS_YENIDEN_DENEME_SN
            with mock.patch.object(gemini, '_redis_client', return_value=self.redis):
                self.assertIsInstance(gemini._get_butce(), gemini._RedisButce)


class CveYukseltmeTavaniTests(SimpleTestCase):
    """2026-11-08: CVE bolumu ayri, daha yuksek yukseltme tavani alir (gunde ~600 yeni onemli CVE)."""

    def test_cve_kendi_tavanini_digerleri_genel_tavani_alir(self):
        from news import retranslate
        cagrilar = []

        def yukselt(ad, model, sinir, sonuc, bitis=None, tur=None):
            cagrilar.append((ad, sinir))
            return 0, 0

        with mock.patch.object(retranslate, '_bekleyenler', return_value=(0, 0, False)), \
                mock.patch.object(retranslate, '_yukselt', side_effect=yukselt), \
                mock.patch.object(retranslate.tu, 'herhangi_saglayici_hazir', return_value=True), \
                mock.patch.object(retranslate, 'RETRANSLATE_UPGRADE_BATCH', 40), \
                mock.patch.object(retranslate, 'RETRANSLATE_UPGRADE_BATCH_CVE', 150):
            retranslate.retranslate_pending(redis_client=mock.Mock(), tur=retranslate._Tur(10, 0))
            self.assertEqual(dict(cagrilar), {'cve': 150, 'news': 40, 'ai': 40, 'sre': 40, 'devtools': 40,
                                              'kubernetes': 40})
            # Cagiran tavan verirse (testler) butun bolumlere o uygulanir
            cagrilar.clear()
            retranslate.retranslate_pending(redis_client=mock.Mock(), tur=retranslate._Tur(10, 0), upgrade_batch=5)
            self.assertEqual({sinir for _, sinir in cagrilar}, {5})
