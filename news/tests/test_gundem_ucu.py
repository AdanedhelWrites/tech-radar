"""GET /api/gundem/ ucu testleri (Gundem puani, Task 2)."""
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)
from news.tests.base import LOCMEM_CACHE, TEST_MIDDLEWARE

URL = '/api/gundem/'


def _uret(model, n, source, baslik, saat_once=1.0, yayin_gun_once=0, **ekstra):
    """Kayit olusturur; created_at auto_now_add oldugu icin update ile ayarlanir."""
    simdi = timezone.now()
    alan = 'date' if model is NewsArticle else 'published_date'
    veri = {
        'source': source, 'original_title': baslik, 'turkish_title': f'TR {baslik}',
        'link': f'https://ornek.test/{model.__name__}/{n}',
        alan: (simdi - timedelta(days=yayin_gun_once)).date(),
    }
    if model is NewsArticle:
        veri['original_date'] = 'x'
    else:
        veri['original_description'] = 'a'
    veri.update(ekstra)
    kayit = model.objects.create(**veri)
    model.objects.filter(pk=kayit.pk).update(created_at=simdi - timedelta(hours=saat_once))
    return kayit


@override_settings(CACHES=LOCMEM_CACHE, MIDDLEWARE=TEST_MIDDLEWARE)
class GundemUcuTests(TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.istemci = APIClient()

    def _cok_kaynakli(self):
        _uret(NewsArticle, 1, 'The Hacker News', 'Zorbex9shell backdoor hits servers', 2)
        _uret(KubernetesEntry, 2, 'BleepingComputer', 'Zorbex9shell backdoor found in clusters', 1)

    def test_yanit_bicimi(self):
        self._cok_kaynakli()
        _uret(SREEntry, 3, 'Google Cloud SRE', 'Totally unrelated postmortem notes', 3)
        yanit = self.istemci.get(URL)
        self.assertEqual(yanit.status_code, 200)
        govde = yanit.json()
        self.assertTrue(govde['success'])
        self.assertIn('hesaplandi', govde)
        olaylar = govde['olaylar']
        self.assertEqual(len(olaylar), 2)
        ilk = olaylar[0]
        self.assertEqual(
            set(ilk), {'bolum', 'kayit', 'kaynak_sayisi', 'kaynaklar', 'diger_kaynaklar', 'makale_sayisi',
                       'bolumler', 'puan', 'ilk', 'son'})
        self.assertEqual(ilk['kaynak_sayisi'], 2)
        self.assertEqual(ilk['kaynaklar'], ['BleepingComputer', 'The Hacker News'])
        self.assertEqual(ilk['makale_sayisi'], 2)
        self.assertEqual(ilk['bolumler'], ['kubernetes', 'news'])
        self.assertIn(ilk['bolum'], ('news', 'kubernetes'))
        self.assertEqual(ilk['puan'], round(ilk['puan'], 2))
        self.assertLess(ilk['ilk'], ilk['son'])
        dolgu = olaylar[1]
        self.assertEqual(dolgu['bolum'], 'sre')
        self.assertEqual(dolgu['kaynak_sayisi'], 1)
        self.assertEqual(dolgu['makale_sayisi'], 1)
        self.assertEqual(dolgu['bolumler'], ['sre'])

    def test_diger_kaynaklar_baglanti_tasir(self):
        # Kart "N kaynak" diyordu ama yalniz temsilcinin baglantisi vardi (2026-11-07)
        self._cok_kaynakli()
        _uret(AINewsEntry, 4, 'TechCrunch AI', 'Zorbex9shell backdoor targets AI labs', 1.5)
        olay = self.istemci.get(URL).json()['olaylar'][0]
        temsilci_kaynagi = olay['kayit']['source']
        diger = olay['diger_kaynaklar']
        self.assertEqual(len(diger), olay['kaynak_sayisi'] - 1)
        self.assertNotIn(temsilci_kaynagi, [d['kaynak'] for d in diger])
        self.assertEqual([d['kaynak'] for d in diger], sorted(d['kaynak'] for d in diger))
        for d in diger:
            self.assertEqual(set(d), {'kaynak', 'baslik', 'link', 'bolum', 'id'})
            self.assertTrue(d['link'].startswith('https://ornek.test/'))
            self.assertTrue(d['baslik'].startswith('TR '), 'Turkce baslik tercih edilir')

    def test_cve_girmez(self):
        _uret(CVEEntry, 1, 'NVD', 'CVE-2026-0001 critical flaw in widget', 1, cve_id='CVE-2026-0001')
        govde = self.istemci.get(URL).json()
        self.assertTrue(govde['success'])
        self.assertEqual(govde['olaylar'], [])

    def test_eski_yayin_tarihli_kayit_pencere_disi(self):
        # created_at yeni ama yayin tarihi 10 gun once: yeni eklenen kaynagin eski yazisi
        _uret(DevToolsEntry, 1, 'Yeni Kaynak', 'Eski surum notu', 1, yayin_gun_once=10)
        _uret(AINewsEntry, 2, 'AI Blog', 'Taze yazi', 2, yayin_gun_once=0)
        olaylar = self.istemci.get(URL).json()['olaylar']
        self.assertEqual([o['bolum'] for o in olaylar], ['ai'])

    def test_onbellek_120_sn(self):
        self._cok_kaynakli()
        from news import gundem
        with mock.patch.object(gundem, 'olaylari_sec', wraps=gundem.olaylari_sec) as sec:
            ilk = self.istemci.get(URL).json()
            ikinci = self.istemci.get(URL).json()
        self.assertEqual(sec.call_count, 1)
        self.assertEqual(ilk, ikinci)
        sahte = mock.MagicMock()
        sahte.get.return_value = None
        with mock.patch('news.views.cache', sahte):
            self.istemci.get(URL)
        sahte.set.assert_called_once()
        self.assertEqual(sahte.set.call_args.args[0], 'gundem_ozeti')
        self.assertEqual(sahte.set.call_args.args[2], 120)

    def test_hesap_hatasinda_200_ve_bos(self):
        self._cok_kaynakli()
        with mock.patch('news.gundem.olaylari_sec', side_effect=RuntimeError('patladi')):
            yanit = self.istemci.get(URL)
        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.json(), {'success': False, 'olaylar': []})
        # hata onbellege yazilmaz: bir sonraki istek yeniden dener
        self.assertIsNone(cache.get('gundem_ozeti'))

    def test_anonim_erisim(self):
        # Kimlik bilgisi yok: 401/403 degil 200
        self.assertEqual(APIClient().get(URL).status_code, 200)

    def test_kayit_bolum_serilestiricisiyle(self):
        _uret(AINewsEntry, 1, 'AI Blog', 'Taze yazi', 1, translation_provider='gemini')
        kayit = self.istemci.get(URL).json()['olaylar'][0]['kayit']
        self.assertEqual(kayit['turkish_title'], 'TR Taze yazi')
        self.assertEqual(kayit['translation_provider'], 'gemini')
        self.assertIn('created_at', kayit)
        self.assertEqual(kayit['original_title'], 'Taze yazi')
