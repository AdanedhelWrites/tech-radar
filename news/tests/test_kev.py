"""KEV eklenme tarihi: onek ayirici, migration geri doldurma, NVD yeniden yazimi, scraper alani."""
from datetime import date, datetime, timedelta
from unittest import mock

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase, TransactionTestCase

from news import tasks
from news.cve_scraper import CISAKEVScraper
from news.kev import kev_oneki_ayir
from news.models import CVEEntry
from news.tests.test_kaynaklar import SahteYanit, _nvd_cve


class KevOnekiAyirTests(SimpleTestCase):

    def test_onek_ayrilir(self):
        t, son, govde = kev_oneki_ayir(
            'Added to the CISA KEV catalog on 2026-10-20; required action due 2026-11-10. Bir hata.')
        self.assertEqual((t, son, govde), (date(2026, 10, 20), date(2026, 11, 10), 'Bir hata.'))

    def test_son_tarihsiz_onek(self):
        self.assertEqual(kev_oneki_ayir('Added to the CISA KEV catalog on 2026-10-20. X'),
                         (date(2026, 10, 20), None, 'X'))

    def test_onek_yoksa_dokunmaz(self):
        self.assertEqual(kev_oneki_ayir('Plain text.'), (None, None, 'Plain text.'))
        self.assertEqual(kev_oneki_ayir(''), (None, None, ''))

    def test_onek_yalniz_metnin_basindaysa_taninir(self):
        metin = 'Giris. Added to the CISA KEV catalog on 2026-10-20. X'
        self.assertEqual(kev_oneki_ayir(metin), (None, None, metin))

    def test_gecersiz_tarih_onegi_tanimaz(self):
        metin = 'Added to the CISA KEV catalog on 2026-13-45. X'
        self.assertEqual(kev_oneki_ayir(metin), (None, None, metin))


class KevGeriDoldurmaMigrationTests(TransactionTestCase):
    """0015'e donup onekli kayit yazar, 0016'ya ilerler (Desen: test_migrations_0009)."""

    onceki = [('news', '0015_translation_attempts')]
    sonraki = [('news', '0016_cveentry_kev_added_date')]

    def tearDown(self):
        # Sonraki testler icin sema guncel kalmali
        yurutucu = MigrationExecutor(connection)
        yurutucu.migrate(yurutucu.loader.graph.leaf_nodes())

    def test_migration_geri_doldurur(self):
        yurutucu = MigrationExecutor(connection)
        yurutucu.migrate(self.onceki)
        Eski = yurutucu.loader.project_state(self.onceki).apps.get_model('news', 'CVEEntry')
        Eski.objects.create(
            cve_id='CVE-2026-0001', original_title='A', link='https://ornek.test/kev/1',
            original_description='Added to the CISA KEV catalog on 2026-10-20; required action due 2026-11-10. Bir hata.',
            source='CISA KEV', published_date=date(2026, 10, 1))
        Eski.objects.create(
            cve_id='CVE-2026-0002', original_title='B', link='https://ornek.test/kev/2',
            original_description='Plain text.', source='NVD', published_date=date(2026, 10, 1))

        yurutucu = MigrationExecutor(connection)
        yurutucu.migrate(self.sonraki)
        Yeni = yurutucu.loader.project_state(self.sonraki).apps.get_model('news', 'CVEEntry')

        kev = Yeni.objects.get(cve_id='CVE-2026-0001')
        self.assertEqual(kev.kev_added_date, date(2026, 10, 20))
        self.assertTrue(kev.original_description.startswith('Added to the CISA KEV catalog on '),
                        'original_description degismemeli')
        self.assertIsNone(Yeni.objects.get(cve_id='CVE-2026-0002').kev_added_date)


class NvdYenidenYazimiTests(TestCase):

    def setUp(self):
        yama = mock.patch('news.tasks.MultiCVEScraper')
        self.scraper = yama.start()
        self.addCleanup(yama.stop)

    def _calistir(self, kayit):
        ornek = self.scraper.return_value
        ornek.fetch_all_cves.return_value = [kayit]
        ornek.process_cves.side_effect = lambda cves: iter(cves)
        tasks.fetch_cve_task(days=7, skip_existing=False)

    def _kayit(self, **ek):
        kayit = {
            'cve_id': 'CVE-2026-0100', 'source': 'NVD Güncel', 'original_title': 'CVE-2026-0100 - X',
            'original_description': 'Aciklama.', 'published_date': date(2026, 10, 1),
            'link': 'https://ornek.test/cve/100',
        }
        kayit.update(ek)
        return kayit

    def test_nvd_yeniden_yazimi_kev_tarihini_ezmez(self):
        self._calistir(self._kayit(source='CISA KEV', kev_added_date=date(2026, 10, 20)))
        self.assertEqual(CVEEntry.objects.get(cve_id='CVE-2026-0100').kev_added_date, date(2026, 10, 20))

        self._calistir(self._kayit())  # NVD sozlugu: kev_added_date anahtari yok

        kayit = CVEEntry.objects.get(cve_id='CVE-2026-0100')
        self.assertEqual(kayit.source, 'NVD Güncel')
        self.assertEqual(kayit.kev_added_date, date(2026, 10, 20))

    def test_kev_tarihi_yoksa_bos_kalir(self):
        self._calistir(self._kayit())
        self.assertIsNone(CVEEntry.objects.get(cve_id='CVE-2026-0100').kev_added_date)


class KevScraperAlaniTests(SimpleTestCase):

    def test_scraper_kev_added_date_yazar(self):
        s = CISAKEVScraper()
        veri = {'vulnerabilities': [_nvd_cve('CVE-2024-0001', 3)]}
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(json_data=veri)):
            kayit = s.fetch_cves(days=30)[0]
        self.assertEqual(kayit['kev_added_date'], (datetime.now() - timedelta(days=3)).date())
        self.assertIn(f"on {kayit['kev_added_date'].isoformat()}", kayit['original_description'])
