"""Bolum liste uclarinin sunucu tarafi suzme, siralama ve sayfalama testleri (2026-11-05 spec G2)."""
from datetime import date, timedelta
from itertools import count

from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)
from news.tests.base import LOCMEM_CACHE

_SAYAC = count(1)

ZARF_ANAHTARLARI = {'success', 'data', 'cached', 'count', 'toplam', 'sayfa', 'sayfa_sayisi', 'boyut'}


def _ortak(**ek):
    n = next(_SAYAC)
    return {'source': 'Test', 'original_title': f'Baslik {n}', 'original_description': 'X',
            'link': f'https://ornek.test/liste/{n}', **ek}


def _kayit(model, zaman=None, **alanlar):
    """Kayit olusturur; created_at auto_now_add oldugundan update() ile ayarlanir."""
    if model is NewsArticle:
        temel = _ortak(turkish_title='Baslik', date=date(2026, 11, 1), original_date='2026-11-01')
    elif model is CVEEntry:
        temel = _ortak(cve_id=f'CVE-2026-{next(_SAYAC):05d}', published_date=date(2026, 11, 1))
    else:
        temel = _ortak(published_date=date(2026, 11, 1))
    temel.update(alanlar)
    nesne = model.objects.create(**temel)
    if zaman is not None:
        model.objects.filter(pk=nesne.pk).update(created_at=zaman)
        nesne.refresh_from_db()
    return nesne


@override_settings(CACHES=LOCMEM_CACHE)
class ListeSorgusuTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.simdi = timezone.now()

    def _al(self, url, **sorgu):
        yanit = self.client.get(url, sorgu)
        self.assertEqual(yanit.status_code, 200)
        return yanit.json()

    def _coklu(self, model, adet, **alanlar):
        """created_at'i 1 dakika arayla azalan `adet` kayit; ilki en yeni."""
        return [_kayit(model, self.simdi - timedelta(minutes=i), **alanlar) for i in range(adet)]

    def test_parametresiz_istek_en_yeni_25(self):
        kayitlar = self._coklu(AINewsEntry, 30)
        govde = self._al('/api/ai/')
        self.assertEqual(govde['count'], 25)
        self.assertEqual(govde['toplam'], 30)
        self.assertEqual(govde['sayfa'], 1)
        self.assertEqual(govde['sayfa_sayisi'], 2)
        self.assertEqual(govde['boyut'], 25)
        self.assertIs(govde['cached'], False)
        self.assertEqual(govde['data'][0]['id'], kayitlar[0].id)

    def test_gun_suzmesi_created_at_ile(self):
        yeni = _kayit(AINewsEntry, self.simdi - timedelta(hours=2))
        _kayit(AINewsEntry, self.simdi - timedelta(days=3))
        govde = self._al('/api/ai/', gun=1)
        self.assertEqual(govde['toplam'], 1)
        self.assertEqual(govde['data'][0]['id'], yeni.id)

    def test_tumu_gun_yoksa_hepsi(self):
        _kayit(AINewsEntry, self.simdi - timedelta(days=80))
        _kayit(AINewsEntry, self.simdi)
        self.assertEqual(self._al('/api/ai/')['toplam'], 2)
        self.assertEqual(self._al('/api/ai/', gun=7)['toplam'], 1)

    def test_sirala_eski(self):
        kayitlar = self._coklu(SREEntry, 3)
        govde = self._al('/api/sre/', sirala='eski')
        self.assertEqual([k['id'] for k in govde['data']], [k.id for k in reversed(kayitlar)])

    def test_sirala_cvss_skorsuzlar_sonda(self):
        _kayit(CVEEntry, self.simdi, cvss_score=9.8)
        _kayit(CVEEntry, self.simdi - timedelta(minutes=1), cvss_score=None)
        _kayit(CVEEntry, self.simdi - timedelta(minutes=2), cvss_score=5.0)
        govde = self._al('/api/cve/', sirala='cvss')
        self.assertEqual([k['cvss_score'] for k in govde['data']], [9.8, 5.0, None])

    def test_cvss_siralamasi_cve_disinda_yok_sayilir(self):
        kayitlar = self._coklu(NewsArticle, 3)
        govde = self._al('/api/news/', sirala='cvss')
        self.assertEqual([k['id'] for k in govde['data']], [k.id for k in kayitlar])

    def test_onem_kritik_cvss_araligi(self):
        kritik = _kayit(CVEEntry, self.simdi, cvss_score=9.0)
        _kayit(CVEEntry, self.simdi, cvss_score=8.9)
        _kayit(CVEEntry, self.simdi, cvss_score=None)
        govde = self._al('/api/cve/', onem='kritik')
        self.assertEqual([k['id'] for k in govde['data']], [kritik.id])
        self.assertEqual(self._al('/api/cve/', onem='yuksek')['toplam'], 1)

    def test_onem_diger_araliklar(self):
        for skor in (7.0, 6.9, 4.0, 3.9, 0.0):
            _kayit(CVEEntry, self.simdi, cvss_score=skor)
        self.assertEqual(self._al('/api/cve/', onem='yuksek')['toplam'], 1)
        self.assertEqual(self._al('/api/cve/', onem='orta')['toplam'], 2)
        self.assertEqual(self._al('/api/cve/', onem='dusuk')['toplam'], 2)
        self.assertEqual(self._al('/api/cve/', onem='bilinmeyen')['toplam'], 5)

    def test_kaynak_birebir_ve_bilinmeyen_bos(self):
        nvd = _kayit(CVEEntry, self.simdi, source='NVD')
        kev = _kayit(CVEEntry, self.simdi, source='CISA KEV')
        _kayit(CVEEntry, self.simdi, source='Baska')
        govde = self._al('/api/cve/', kaynak='NVD')
        self.assertEqual([k['id'] for k in govde['data']], [nvd.id])
        self.assertEqual(self._al('/api/cve/', kaynak='NVD,CISA KEV')['toplam'], 2)
        self.assertEqual(self._al('/api/cve/', kaynak='nvd')['toplam'], 0)
        bos = self._al('/api/cve/', kaynak='Yok')
        self.assertEqual(bos['toplam'], 0)
        self.assertEqual(bos['data'], [])
        self.assertNotEqual(nvd.id, kev.id)

    def test_kategori_kubernetes(self):
        blog = _kayit(KubernetesEntry, self.simdi, category='blog')
        _kayit(KubernetesEntry, self.simdi, category='release')
        govde = self._al('/api/k8s/', kategori='blog')
        self.assertEqual([k['id'] for k in govde['data']], [blog.id])

    def test_kategori_baska_bolumlerde_yok_sayilir(self):
        self._coklu(DevToolsEntry, 3)
        self.assertEqual(self._al('/api/devtools/', kategori='release')['toplam'], 3)

    def test_sayfa_ve_boyut(self):
        self._coklu(AINewsEntry, 60)
        govde = self._al('/api/ai/', boyut=25, sayfa=3)
        self.assertEqual(govde['count'], 10)
        self.assertEqual(govde['toplam'], 60)
        self.assertEqual(govde['sayfa'], 3)
        self.assertEqual(govde['sayfa_sayisi'], 3)

    def test_boyut_ust_siniri_100(self):
        self._coklu(AINewsEntry, 3)
        self.assertEqual(self._al('/api/ai/', boyut=500)['boyut'], 100)

    def test_gecersiz_parametreler_varsayilana_duser(self):
        self._coklu(AINewsEntry, 30)
        govde = self._al('/api/ai/', gun='abc', sayfa=-3, sirala='x', boyut=0)
        self.assertEqual(govde['toplam'], 30)
        self.assertEqual(govde['sayfa'], 1)
        self.assertEqual(govde['boyut'], 25)
        # gun listede degilse de suzme yok
        self.assertEqual(self._al('/api/ai/', gun=5)['toplam'], 30)

    def test_asiri_sayfa_son_sayfaya_cekilir(self):
        self._coklu(AINewsEntry, 30)
        govde = self._al('/api/ai/', sayfa=99)
        self.assertEqual(govde['sayfa'], 2)
        self.assertEqual(govde['count'], 5)

    def test_bos_sonuc(self):
        govde = self._al('/api/ai/')
        self.assertEqual(govde['toplam'], 0)
        self.assertEqual(govde['sayfa'], 1)
        self.assertEqual(govde['sayfa_sayisi'], 1)
        self.assertEqual(govde['data'], [])
        self.assertEqual(govde['count'], 0)

    def test_ayni_zamanda_kayitlar_sayfa_sinirinda_tekrarlanmaz(self):
        for _ in range(30):
            _kayit(AINewsEntry, self.simdi)
        ilk = [k['id'] for k in self._al('/api/ai/', sayfa=1)['data']]
        ikinci = [k['id'] for k in self._al('/api/ai/', sayfa=2)['data']]
        self.assertEqual(len(set(ilk + ikinci)), 30)

    def test_liste_cache_okunmaz(self):
        from django.core.cache import cache
        kayit = _kayit(AINewsEntry, self.simdi)
        cache.set('ai_entries', [{'id': 999999, 'sahte': True}], 3600)
        govde = self._al('/api/ai/')
        self.assertEqual([k['id'] for k in govde['data']], [kayit.id])

    def test_alti_bolumun_hepsi_calisir(self):
        modeller = {'news': ('/api/news/', NewsArticle), 'cve': ('/api/cve/', CVEEntry),
                    'kubernetes': ('/api/k8s/', KubernetesEntry), 'sre': ('/api/sre/', SREEntry),
                    'devtools': ('/api/devtools/', DevToolsEntry), 'ai': ('/api/ai/', AINewsEntry)}
        for bolum, (url, model) in modeller.items():
            with self.subTest(bolum=bolum):
                _kayit(model, self.simdi)
                govde = self._al(url)
                self.assertEqual(set(govde), ZARF_ANAHTARLARI)
                self.assertEqual(govde['toplam'], 1)
                self.assertTrue(govde['success'])
