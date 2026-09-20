"""GET /api/v1/status/ (spec 2026-09-20-a4, bolum 3.5)."""
from datetime import date, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from news.models import CVEEntry, FetchRun
from news.tests.base import V1TestCase


class StatusViewTests(V1TestCase):

    def test_tokensiz_401(self):
        yanit = self.client.get('/api/v1/status/')

        self.assertEqual(yanit.status_code, 401)
        self.assertEqual(yanit.json()['error']['code'], 'unauthorized')

    def test_hic_fetchrun_yokken_200_ve_null(self):
        yanit = self.client.get('/api/v1/status/', **self.token_basligi())

        self.assertEqual(yanit.status_code, 200)
        cve = yanit.json()['sections']['cve']
        self.assertIsNone(cve['last_success_at'])
        self.assertIsNone(cve['last_status'])
        self.assertEqual(cve['total'], 0)

    def test_son_basarili_cekimi_ve_sayilari_dondurur(self):
        CVEEntry.objects.create(cve_id='CVE-2026-1', source='NVD', original_title='T',
                                original_description='D', published_date=date(2026, 9, 12),
                                link='https://ornek.test/1', needs_translation=True)
        FetchRun.objects.create(section='cve', trigger='beat', status='success',
                                fetched_count=268, saved_count=37,
                                finished_at=timezone.now())

        yanit = self.client.get('/api/v1/status/', **self.token_basligi())

        cve = yanit.json()['sections']['cve']
        self.assertEqual(cve['last_status'], 'success')
        self.assertEqual(cve['last_fetched_count'], 268)
        self.assertEqual(cve['last_saved_count'], 37)
        self.assertEqual(cve['pending_translation'], 1)
        self.assertEqual(cve['total'], 1)
        self.assertIsNotNone(cve['last_success_at'])

    def test_basarisiz_tur_last_success_at_i_ilerletmez(self):
        """Eski basarili, yeni basarili, en yeni basarısız: yeni success zamanı doner."""
        simdi = timezone.now()
        iki_gun_once = simdi - timedelta(days=2)
        bir_gun_once = simdi - timedelta(days=1)

        # Eski basarili cekim (2 gun once)
        eski_success = FetchRun.objects.create(
            section='cve', trigger='beat', status='success',
            fetched_count=10, saved_count=5,
            finished_at=iki_gun_once
        )
        FetchRun.objects.filter(pk=eski_success.pk).update(
            started_at=iki_gun_once, finished_at=iki_gun_once
        )

        # Yeni basarili cekim (1 gun once)
        yeni_success = FetchRun.objects.create(
            section='cve', trigger='beat', status='success',
            fetched_count=15, saved_count=8,
            finished_at=bir_gun_once
        )
        FetchRun.objects.filter(pk=yeni_success.pk).update(
            started_at=bir_gun_once, finished_at=bir_gun_once
        )

        # En yeni basarisiz cekim (hemen simdi)
        FetchRun.objects.create(
            section='cve', trigger='beat', status='failure',
            error='disk I/O error', finished_at=simdi
        )

        cve = self.client.get('/api/v1/status/', **self.token_basligi()).json()['sections']['cve']

        # Son BASARILI cekim zaman degeri yeni success'ten geliyor
        son_basarili_zaman = parse_datetime(cve['last_success_at'])
        self.assertEqual(son_basarili_zaman, yeni_success.finished_at,
                        'son BASARILI cekim en yeni success\'in zamani olmali')
        # En yeni cekim basarisiz
        self.assertEqual(cve['last_status'], 'failure')

    def test_retranslate_bolumu_yanitta_yer_almaz(self):
        FetchRun.objects.create(section='retranslate', trigger='beat', status='success',
                                finished_at=timezone.now())

        bolumler = self.client.get('/api/v1/status/', **self.token_basligi()).json()['sections']

        self.assertNotIn('retranslate', bolumler)
        self.assertEqual(set(bolumler), {'cve', 'news', 'kubernetes', 'sre', 'devtools', 'ai'})

    def test_operator_alanlari_yanitta_yok(self):
        """Dar sozlesme: Gemini butcesi, by_provider, stopped_reason, trigger, error girmez."""
        FetchRun.objects.create(section='cve', trigger='admin', status='failure',
                                error='gizli', stopped_reason='gemini_budget',
                                by_provider={'gemini': 5}, finished_at=timezone.now())

        govde = self.client.get('/api/v1/status/', **self.token_basligi()).json()

        ham = str(govde)
        for yasak in ('by_provider', 'stopped_reason', 'trigger', 'error', 'gizli', 'gemini', 'circuit_open'):
            self.assertNotIn(yasak, ham, f'{yasak} dar sozlesmeye girmemeli')
