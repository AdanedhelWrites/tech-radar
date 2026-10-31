"""GET /api/ozet/ (2026-10-31 arayuz yenileme): ana sayfa Zafiyet Durumu ozeti.

Pencereler: kritik = cvss >= 9.0 ve son 24 sa; yuksek = 7.0 <= cvss < 9.0 ve son 7 gun;
KEV = kev_added_date son 7 gun (created_at'tan bagimsiz).
"""
import itertools
from datetime import datetime, timedelta, timezone as dt_timezone

from django.core.cache import cache
from django.utils import timezone

from news.models import CVEEntry
from news.ozet import ozet_hesapla, yeni_kayit_sayisi
from news.tests.base import V1TestCase

_sayac = itertools.count(1)


def _cve(skor, saat_once=1, kev_gun_once=None):
    """created_at'i `saat_once` saat geriye cekilmis bir CVE kaydi olusturur."""
    n = next(_sayac)
    kev = timezone.now().date() - timedelta(days=kev_gun_once) if kev_gun_once is not None else None
    kayit = CVEEntry.objects.create(
        cve_id=f'CVE-2026-{n:05d}', source='NVD', original_title=f'T{n}', original_description='D',
        cvss_score=skor, published_date=timezone.now().date(), link=f'https://ornek.test/{n}',
        kev_added_date=kev)
    CVEEntry.objects.filter(pk=kayit.pk).update(created_at=timezone.now() - timedelta(hours=saat_once))
    return kayit


class OzetUcuTests(V1TestCase):

    def setUp(self):
        super().setUp()
        cache.delete('ozet_govdesi')

    def test_bos_veritabani(self):
        g = self.client.get('/api/ozet/').json()

        self.assertEqual((g['critical_count'], g['high_count'], g['kev_count']), (0, 0, 0))
        self.assertEqual((g['priority'], g['chart'], g['unscored_count']), ([], [], 0))
        self.assertGreater(g['sources']['total'], 0)
        self.assertIn('next_at', g['fetch'])
        self.assertIsNone(g['fetch']['last_success_at'])
        self.assertNotIn('new_since_count', g)

    def test_pencereler(self):
        _cve(9.8, saat_once=2)           # kritik
        _cve(9.1, saat_once=30)          # 24 saat disinda: kritik degil; 9.1 >= 9 oldugu icin yuksek de degil
        _cve(8.6, saat_once=72)          # yuksek
        _cve(7.5, saat_once=8 * 24)      # 7 gun disinda: hicbiri
        kev = _cve(6.5, saat_once=48, kev_gun_once=3)

        g = self.client.get('/api/ozet/').json()

        self.assertEqual(g['critical_count'], 1)
        self.assertEqual(g['high_count'], 1)
        self.assertEqual(g['kev_count'], 1)
        self.assertIn(kev.cve_id, [k['cve_id'] for k in g['priority']])

    def test_kev_sayisi_created_at_pencerisinden_bagimsiz(self):
        _cve(6.5, saat_once=30 * 24, kev_gun_once=2)
        _cve(6.5, saat_once=2, kev_gun_once=9)

        g = self.client.get('/api/ozet/').json()

        self.assertEqual(g['kev_count'], 1)
        self.assertEqual(g['priority'], [])    # eski kayit created_at penceresinin disinda

    def test_priority_sirasi_ve_limit(self):
        for i, skor in enumerate([7.0, 9.8, 7.4, 8.1, 9.0, 7.9, 8.8]):
            _cve(skor, saat_once=i + 1)

        skorlar = [k['cvss_score'] for k in self.client.get('/api/ozet/').json()['priority']]

        self.assertEqual(skorlar, [9.8, 9.0, 8.8, 8.1, 7.9])

    def test_priority_esit_skorda_kev_once_sonra_yeni(self):
        eski = _cve(8.0, saat_once=10)
        yeni = _cve(8.0, saat_once=1)
        kev = _cve(8.0, saat_once=50, kev_gun_once=1)

        idler = [k['cve_id'] for k in self.client.get('/api/ozet/').json()['priority']]

        self.assertEqual(idler, [kev.cve_id, yeni.cve_id, eski.cve_id])

    def test_priority_skorsuz_kev_adaydir_ve_sona_kalir(self):
        skorlu = _cve(7.2, saat_once=5)
        skorsuz_kev = _cve(None, saat_once=5, kev_gun_once=0)
        _cve(None, saat_once=5)

        idler = [k['cve_id'] for k in self.client.get('/api/ozet/').json()['priority']]

        self.assertEqual(idler, [skorlu.cve_id, skorsuz_kev.cve_id])

    def test_chart_skorsuzlari_ayirir(self):
        _cve(None)
        _cve(3.1)

        g = self.client.get('/api/ozet/').json()

        self.assertEqual(g['chart'], [])
        self.assertEqual(g['unscored_count'], 2)

    def test_chart_sirasi_alanlari_ve_limit(self):
        for i in range(45):
            _cve(4.0 + i * 0.1)
        _cve(2.0)
        _cve(9.9, saat_once=9 * 24)    # pencere disi: ne grafikte ne sayimda

        g = self.client.get('/api/ozet/').json()

        self.assertEqual(len(g['chart']), 40)
        self.assertEqual(set(g['chart'][0]), {'cve_id', 'cvss_score'})
        skorlar = [p['cvss_score'] for p in g['chart']]
        self.assertEqual(skorlar, sorted(skorlar, reverse=True))
        self.assertEqual(g['unscored_count'], 1)

    def test_since_sayar_ve_gecersizi_yok_sayar(self):
        _cve(5.0, saat_once=3)
        _cve(5.0, saat_once=0.5)
        _cve(5.0, saat_once=0.2)
        since = (timezone.now() - timedelta(hours=1)).isoformat()

        g = self.client.get('/api/ozet/', {'since': since}).json()
        self.assertEqual(g['new_since_count'], 2)

        yanit = self.client.get('/api/ozet/', {'since': 'bozuk'})
        self.assertEqual(yanit.status_code, 200)
        self.assertNotIn('new_since_count', yanit.json())

    def test_since_naif_tarih_utc_sayilir(self):
        _cve(5.0, saat_once=0.5)
        naif = (datetime.now(dt_timezone.utc) - timedelta(hours=1)).replace(tzinfo=None).isoformat()

        self.assertEqual(self.client.get('/api/ozet/', {'since': naif}).json()['new_since_count'], 1)

    def test_since_onbellegi_atlar(self):
        self.client.get('/api/ozet/')
        _cve(5.0, saat_once=0.1)
        since = (timezone.now() - timedelta(hours=1)).isoformat()

        g = self.client.get('/api/ozet/', {'since': since}).json()

        self.assertEqual(g['new_since_count'], 1)     # sayim cache'lenmez
        self.assertEqual(g['unscored_count'], 0)      # govde 60 sn cache'ten gelir
        self.assertEqual(g['chart'], [])

    def test_since_cache_govdesine_sizmaz(self):
        self.client.get('/api/ozet/', {'since': (timezone.now() - timedelta(hours=1)).isoformat()})

        self.assertNotIn('new_since_count', self.client.get('/api/ozet/').json())

    def test_tokensiz_erisim(self):
        self.assertEqual(self.client.get('/api/ozet/').status_code, 200)


class OzetHesaplaTests(V1TestCase):

    def test_sinirlar_verilen_simdiye_gore(self):
        simdi = timezone.now() + timedelta(days=2)    # "simdi" 2 gun ileride
        _cve(8.5, saat_once=1)                        # simdiye gore 49 sa once: kritik penceresi disinda
        _cve(8.5, saat_once=60)

        g = ozet_hesapla(simdi=simdi)

        self.assertEqual(g['generated_at'], simdi.isoformat())
        self.assertEqual((g['critical_count'], g['high_count']), (0, 2))

    def test_sonraki_cekim_zamani_beat_takviminden(self):
        # Beat: dakika 10, saat */6 (Europe/Istanbul). 14:36 Istanbul -> 18:10 Istanbul = 15:10 UTC
        simdi = datetime(2026, 10, 31, 11, 36, tzinfo=dt_timezone.utc)

        g = ozet_hesapla(simdi=simdi)

        self.assertEqual(datetime.fromisoformat(g['fetch']['next_at']),
                         datetime(2026, 10, 31, 15, 10, tzinfo=dt_timezone.utc))

    def test_yeni_kayit_sayisi(self):
        _cve(5.0, saat_once=3)
        _cve(5.0, saat_once=0.5)

        self.assertEqual(yeni_kayit_sayisi(timezone.now() - timedelta(hours=1)), 1)
