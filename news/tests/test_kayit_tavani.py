"""Tur tavani yalniz yeni kayitlara uygulanir (2026-11-05).

Canli olay: 12 haber kaynagi x 5 = 60 kayit tarihe gore siralanip 36'ya kesiliyordu; kesme
_drop_existing'den ONCE oldugu icin CyberScoop / Dark Reading / Krebs'in tarihce geride kalan
YENI haberleri hic kaydedilmedi ve FetchRun.by_source bu kaynaklari 0 gosterdi.
"""
from datetime import date, timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase

import scraper_multi as sm
from news import tasks
from news.kaynaklar import kayit_tavani
from news.models import NewsArticle


def _kayit(kaynak, i, gun_once):
    return {'source': kaynak, 'title': f'{kaynak} {i}', 'original_title': f'{kaynak} {i}',
            'description': 'x', 'link': f'https://{kaynak}.test/{i}', 'original_date': '',
            'date': (date(2026, 11, 5) - timedelta(days=gun_once)).isoformat()}


class KayitTavaniTests(SimpleTestCase):

    def test_kaynak_basina_pay_ve_toplam_tavan(self):
        girdi = [_kayit(f'k{k}', i, i) for k in range(12) for i in range(10)]
        cikti = kayit_tavani(girdi, kaynak_sayisi=12)
        self.assertEqual(len(cikti), 36)            # max(30, 3 x 12)
        sayim = {}
        for e in cikti:
            sayim[e['source']] = sayim.get(e['source'], 0) + 1
        self.assertTrue(all(n <= 5 for n in sayim.values()))   # max(5, 36 // 12)

    def test_kaynagin_en_yeni_kayitlari_secilir_ve_tarihe_gore_siralanir(self):
        girdi = [_kayit('a', i, i) for i in range(8)] + [_kayit('b', 0, 3)]
        cikti = kayit_tavani(girdi, kaynak_sayisi=2)
        self.assertEqual([e['title'] for e in cikti if e['source'] == 'a'], [f'a {i}' for i in range(8)])
        # Toplam tavanin tabani 3 x kaynak sayisi
        self.assertEqual(len(kayit_tavani(girdi, kaynak_sayisi=2, max_total=3)), 6)
        self.assertEqual(len(kayit_tavani(girdi, kaynak_sayisi=1, max_total=3)), 3)
        self.assertEqual(cikti, sorted(cikti, key=lambda e: e['date'], reverse=True))

    def test_tavan_altinda_hepsi_kalir(self):
        girdi = [_kayit('a', 0, 0), _kayit('b', 0, 1)]
        self.assertEqual(kayit_tavani(girdi, kaynak_sayisi=2), girdi)
        self.assertEqual(kayit_tavani([], kaynak_sayisi=0), [])


class _SahteKaynak:
    def __init__(self, ad, adet):
        self._ad, self._adet = ad, adet

    def get_name(self):
        return self._ad

    def fetch_news(self, days=7):
        return [_kayit(self._ad, i, i) for i in range(self._adet)]


class FetchAllNewsSinirlaTests(SimpleTestCase):

    def test_sinirla_false_tum_kayitlari_dondurur(self):
        m = sm.MultiSourceScraper()
        m.sources = [_SahteKaynak(f'k{i}', 10) for i in range(12)]
        self.assertEqual(len(m.fetch_all_news(days=7, sinirla=False)), 120)
        self.assertEqual(len(m.fetch_all_news(days=7)), 36)


class HaberTaskTavanTests(TestCase):

    def _cek(self, girdi):
        def cevir(articles):
            for a in articles:
                yield dict(a, turkish_title=a['title'], turkish_description='', turkish_summary='')
        yama = mock.patch('news.tasks.MultiSourceScraper')
        scraper = yama.start()
        self.addCleanup(yama.stop)
        # Kaynak defteri yalniz sahte kaynaklari bilsin (gercek 12 ad kaynak sayisini sisirmesin)
        defter = mock.patch('news.kaynaklar.bolum_kaynaklari', return_value=[])
        defter.start()
        self.addCleanup(defter.stop)
        scraper.return_value.fetch_all_news.return_value = girdi
        scraper.return_value.process_news.side_effect = cevir
        sonuc = tasks.fetch_news_task(days=7)
        self.assertTrue(scraper.return_value.fetch_all_news.call_args.kwargs.get('sinirla') is False,
                        'Task tavani kendisi, mevcutlari ayikladiktan sonra uygulamali')
        return sonuc

    def test_tarihce_geride_kalan_yeni_haber_kaydedilir(self):
        """11 kaynagin en yeni 5'er haberi zaten kayitli; 'seyrek' kaynagin 3 gunluk haberi yeni."""
        girdi = [_kayit(f'k{k}', i, i // 3) for k in range(11) for i in range(5)]
        girdi.append(_kayit('seyrek', 0, 3))
        girdi.sort(key=lambda e: e['date'], reverse=True)
        for e in girdi:
            if e['source'] != 'seyrek':
                NewsArticle.objects.create(source=e['source'], original_title=e['title'],
                                           turkish_title=e['title'], link=e['link'],
                                           date=date.fromisoformat(e['date']), original_date='')

        sonuc = self._cek(girdi)

        self.assertTrue(NewsArticle.objects.filter(link='https://seyrek.test/0').exists())
        self.assertEqual(sonuc['count'], 1)
        self.assertEqual(sonuc['fetched_count'], 56, 'Gelen sayisi tavandan once sayilir')
        self.assertEqual(sonuc['by_source']['seyrek'], {'fetched': 1, 'saved': 1})

    def test_tavan_yeni_kayitlara_uygulanir(self):
        girdi = [_kayit(f'k{k}', i, i) for k in range(12) for i in range(10)]
        sonuc = self._cek(girdi)
        self.assertEqual(sonuc['count'], 36)
        self.assertEqual(sonuc['fetched_count'], 120)
