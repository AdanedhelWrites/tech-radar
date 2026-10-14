"""Kaynak sagligi (2026-10-08): FetchRun.by_source, news/kaynaklar.py ve status ucu.

Neden: 8 kaynak aylarca sessizce olmustu; bolum toplamlari "success" gosteriyordu.
"""
from datetime import date, timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from news import fetch_runs, kaynaklar
from news.models import DevToolsEntry, FetchRun, NewsArticle
from news.tests.base import V1TestCase


class BolumKaynaklariTests(SimpleTestCase):

    def test_kayit_defterleri_toplam_47_kaynak(self):
        # 2026-10-14: KDnuggets (403), MinIO (ust kaynak olu), CIRCL (/api/last artik CVE donmuyor) cikti;
        # Ars Technica AI ve Import AI girdi.
        beklenen = {'news': 12, 'cve': 5, 'kubernetes': 3, 'sre': 5, 'devtools': 13, 'ai': 9}
        for bolum, adet in beklenen.items():
            with self.subTest(bolum=bolum):
                self.assertEqual(len(kaynaklar.bolum_kaynaklari(bolum)), adet)
        self.assertIn('CISA KEV', kaynaklar.bolum_kaynaklari('cve'))
        self.assertIn('Bleeping Computer', kaynaklar.bolum_kaynaklari('news'))
        self.assertIn('Ars Technica AI', kaynaklar.bolum_kaynaklari('ai'))
        self.assertIn('Import AI', kaynaklar.bolum_kaynaklari('ai'))
        for bolum, ad in (('ai', 'KDnuggets'), ('devtools', 'MinIO'), ('cve', 'CIRCL')):
            self.assertNotIn(ad, kaynaklar.bolum_kaynaklari(bolum))

    def test_bilinmeyen_bolum_keyerror(self):
        with self.assertRaises(KeyError):
            kaynaklar.bolum_kaynaklari('yok')


class KaynakSayaclariTests(SimpleTestCase):

    def test_secili_kaynaklar_sifirla_acilir_gelenler_sayilir(self):
        entries = [{'source': 'The Hacker News'}, {'source': 'The Hacker News'}, {'source': 'Krebs on Security'}]
        sayac = kaynaklar.kaynak_sayaclari('news', None, entries)

        self.assertEqual(len(sayac), 12)
        self.assertEqual(sayac['The Hacker News'], {'fetched': 2, 'saved': 0})
        self.assertEqual(sayac['Bleeping Computer'], {'fetched': 0, 'saved': 0})

    def test_secim_buyuk_kucuk_harf_duyarsiz_ve_secilmeyen_yok(self):
        sayac = kaynaklar.kaynak_sayaclari('devtools', ['keycloak', 'GitLab'], [{'source': 'Keycloak'}])

        self.assertEqual(set(sayac), {'Keycloak', 'GitLab'})
        self.assertEqual(sayac['Keycloak']['fetched'], 1)
        self.assertEqual(sayac['GitLab']['fetched'], 0)

    def test_kaynak_yazildi_bilinmeyen_adi_da_sayar(self):
        sayac = kaynaklar.kaynak_sayaclari('sre', ['SRE Weekly'], [])
        kaynaklar.kaynak_yazildi(sayac, 'SRE Weekly')
        kaynaklar.kaynak_yazildi(sayac, 'Eski Kaynak')

        self.assertEqual(sayac['SRE Weekly']['saved'], 1)
        self.assertEqual(sayac['Eski Kaynak'], {'fetched': 0, 'saved': 1})


class FetchRunBySourceTests(TestCase):

    def _sender(self, ad):
        class SahteSender:
            name = ad
            request = {}
        return SahteSender()

    def test_postrun_by_source_yazar(self):
        sender = self._sender('news.tasks.fetch_news_task')
        fetch_runs.tur_basladi(sender=sender, task_id='k1')
        fetch_runs.tur_bitti(sender=sender, task_id='k1',
                             retval={'success': True, 'count': 1, 'fetched_count': 3,
                                     'by_source': {'The Hacker News': {'fetched': 3, 'saved': 1},
                                                   'Bleeping Computer': {'fetched': 0, 'saved': 0}}})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.by_source['Bleeping Computer'], {'fetched': 0, 'saved': 0})
        self.assertEqual(kayit.by_source['The Hacker News']['saved'], 1)

    def test_by_source_yoksa_bos_sozluk(self):
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='k2')
        fetch_runs.tur_bitti(sender=sender, task_id='k2', retval={'success': True, 'count': 0, 'fetched_count': 0})

        self.assertEqual(FetchRun.objects.get().by_source, {})


def _tur(bolum, by_source, gun_once, status='success'):
    kayit = FetchRun.objects.create(section=bolum, trigger='beat', status=status, by_source=by_source,
                                    finished_at=timezone.now())
    zaman = timezone.now() - timedelta(hours=6 * gun_once)
    FetchRun.objects.filter(pk=kayit.pk).update(started_at=zaman, finished_at=zaman)
    return kayit


class KaynakDurumlariTests(TestCase):

    def test_dort_ardisik_sifir_tur_sessiz(self):
        for i in range(4):
            _tur('news', {'Bleeping Computer': {'fetched': 0, 'saved': 0},
                          'The Hacker News': {'fetched': 5, 'saved': 1}}, i)

        durum = kaynaklar.kaynak_durumlari('news', NewsArticle)

        self.assertTrue(durum['Bleeping Computer']['silent'])
        self.assertEqual(durum['Bleeping Computer']['zero_runs'], 4)
        self.assertEqual(durum['Bleeping Computer']['last_fetched_count'], 0)
        self.assertFalse(durum['The Hacker News']['silent'])
        self.assertEqual(durum['The Hacker News']['zero_runs'], 0)

    def test_uc_sifir_tur_henuz_sessiz_degil_ve_ilk_pozitifte_durur(self):
        _tur('news', {'Krebs on Security': {'fetched': 2, 'saved': 0}}, 3)
        for i in range(3):
            _tur('news', {'Krebs on Security': {'fetched': 0, 'saved': 0}}, i)

        durum = kaynaklar.kaynak_durumlari('news', NewsArticle)

        self.assertEqual(durum['Krebs on Security']['zero_runs'], 3)
        self.assertFalse(durum['Krebs on Security']['silent'])

    def test_kaynagin_secilmedigi_ve_by_source_siz_turlar_atlanir(self):
        # by_source bos (ozellikten onceki tur) ve yalniz THN secili turlar sayima girmez
        _tur('news', {}, 5)
        _tur('news', {'The Hacker News': {'fetched': 4, 'saved': 0}}, 4)
        for i in range(4):
            _tur('news', {'Dark Reading': {'fetched': 0, 'saved': 0}}, i)

        durum = kaynaklar.kaynak_durumlari('news', NewsArticle)

        self.assertTrue(durum['Dark Reading']['silent'])
        self.assertEqual(durum['The Hacker News']['last_fetched_count'], 4)
        self.assertIsNone(durum['SecurityWeek']['last_fetched_count'])
        self.assertFalse(durum['SecurityWeek']['silent'])

    def test_calisan_tur_sayilmaz(self):
        for i in range(4):
            _tur('news', {'SANS ISC': {'fetched': 0, 'saved': 0}}, i, status='running')

        self.assertFalse(kaynaklar.kaynak_durumlari('news', NewsArticle)['SANS ISC']['silent'])

    def test_son_kayit_zamani_modelden(self):
        NewsArticle.objects.create(source='The Register', original_title='t', turkish_title='t',
                                   link='https://ornek.test/r1', date=timezone.now().date(),
                                   original_date='')

        durum = kaynaklar.kaynak_durumlari('news', NewsArticle)

        self.assertIsNotNone(durum['The Register']['last_record_at'])
        self.assertIsNone(durum['CyberScoop']['last_record_at'])

    def test_esik_ortamdan(self):
        for i in range(2):
            _tur('news', {'SANS ISC': {'fetched': 0, 'saved': 0}}, i)
        with mock.patch.object(kaynaklar, 'SESSIZ_TUR_ESIGI', 2):
            self.assertTrue(kaynaklar.kaynak_durumlari('news', NewsArticle)['SANS ISC']['silent'])

    def _devtools_kaydi(self, gun_once):
        kayit = DevToolsEntry.objects.create(source='RabbitMQ', original_title='RabbitMQ v4.3.6',
                                             original_description='D', link='https://ornek.test/r',
                                             published_date=date(2026, 9, 14))
        DevToolsEntry.objects.filter(pk=kayit.pk).update(created_at=timezone.now() - timedelta(days=gun_once))

    def test_seyrek_kaynak_pencere_disinda_sessiz_degil(self):
        # RabbitMQ 30 gunluk pencerede 0 doner ama son surum 29 gun once; beklenen aralik 60 gun
        self._devtools_kaydi(29)
        for i in range(4):
            _tur('devtools', {'RabbitMQ': {'fetched': 0, 'saved': 0}}, i)

        durum = kaynaklar.kaynak_durumlari('devtools', DevToolsEntry)['RabbitMQ']

        self.assertEqual(durum['zero_runs'], 4)
        self.assertEqual(durum['expected_gap_days'], 60)
        self.assertEqual(durum['days_since_record'], 29)
        self.assertFalse(durum['silent'])

    def test_seyrek_kaynak_beklenen_araligi_asinca_sessiz(self):
        self._devtools_kaydi(61)
        for i in range(4):
            _tur('devtools', {'RabbitMQ': {'fetched': 0, 'saved': 0}}, i)

        self.assertTrue(kaynaklar.kaynak_durumlari('devtools', DevToolsEntry)['RabbitMQ']['silent'])

    def test_akis_kaynagi_bolum_penceresini_kullanir(self):
        # Haber penceresi 7 gun: 10 gun once kayit + 4 sifir tur = sessiz
        kayit = NewsArticle.objects.create(source='Dark Reading', original_title='T', turkish_title='T',
                                           link='https://ornek.test/d', date=date(2026, 10, 1),
                                           original_date='2026-10-01')
        NewsArticle.objects.filter(pk=kayit.pk).update(created_at=timezone.now() - timedelta(days=10))
        for i in range(4):
            _tur('news', {'Dark Reading': {'fetched': 0, 'saved': 0}}, i)

        durum = kaynaklar.kaynak_durumlari('news', NewsArticle)['Dark Reading']

        self.assertEqual(durum['expected_gap_days'], 7)
        self.assertEqual(durum['days_since_record'], 10)
        self.assertTrue(durum['silent'])


class StatusKaynakAlanlariTests(V1TestCase):

    def test_status_sessiz_kaynaklari_listeler(self):
        for i in range(4):
            _tur('news', {'Bleeping Computer': {'fetched': 0, 'saved': 0},
                          'The Hacker News': {'fetched': 5, 'saved': 1}}, i)

        govde = self.client.get('/api/v1/status/', **self.token_basligi()).json()

        haber = govde['sections']['news']
        self.assertEqual(haber['silent_sources'], ['Bleeping Computer'])
        self.assertTrue(haber['sources']['Bleeping Computer']['silent'])
        self.assertEqual(haber['sources']['The Hacker News']['zero_runs'], 0)
        self.assertEqual(len(haber['sources']), 12)
        self.assertEqual(govde['sections']['cve']['silent_sources'], [])

    def test_sema_kaynak_alanlarini_tasir(self):
        from news.tests.test_schema import sema_uret

        sema = sema_uret()
        alanlar = sema['components']['schemas']['BolumDurumuV1']['properties']
        self.assertIn('sources', alanlar)
        self.assertIn('silent_sources', alanlar)
        self.assertIn('KaynakDurumuV1', sema['components']['schemas'])
        kaynak = sema['components']['schemas']['KaynakDurumuV1']['properties']
        self.assertIn('expected_gap_days', kaynak)
        self.assertIn('days_since_record', kaynak)
