"""Var olan CVE'lerin guncellenmesi, yeni kayit secimi, NVD sayfalamasi ve kaynak onceligi (2026-11-07)."""
from datetime import date, datetime, timedelta
from unittest import mock

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from news import cve_guncelleme, tasks
from news.cve_scraper import (CISAKEVScraper, NVDRecentScraper, NVDScraper, aciklama_yer_tutucu_mu,
                              tekillestir)
from news.models import CVEEntry
from news.tests.test_kaynaklar import SahteYanit

KATALOG = CISAKEVScraper.KEV_KATALOG


def _kayit(**ek):
    alanlar = dict(
        cve_id='CVE-2026-1000', source='NVD', original_title='CVE-2026-1000 - Güvenlik Açığı',
        turkish_title='CVE-2026-1000 - Güvenlik Açığı',
        original_description='A remote attacker can execute arbitrary code via crafted packets.',
        turkish_description='Uzaktan bir saldırgan, hazırlanmış paketlerle rastgele kod çalıştırabilir.',
        severity='Yüksek', cvss_score=7.5, published_date=date(2026, 10, 1),
        link='https://nvd.nist.gov/vuln/detail/CVE-2026-1000', cwe_ids=['CWE-787'],
        references=['https://vendor.example/a'], translation_provider='gemini')
    alanlar.update(ek)
    return CVEEntry.objects.create(**alanlar)


def _sozluk(**ek):
    cve = {
        'cve_id': 'CVE-2026-1000', 'source': 'NVD Güncel', 'original_title': 'CVE-2026-1000 - Güvenlik Açığı',
        'original_description': 'A remote attacker can execute arbitrary code via crafted packets.',
        'severity': 'Yüksek', 'cvss_score': 7.5, 'published_date': date(2026, 10, 1),
        'modified_date': None, 'link': 'https://nvd.nist.gov/vuln/detail/CVE-2026-1000',
        'cwe_ids': ['CWE-787'], 'references': ['https://vendor.example/a'],
    }
    cve.update(ek)
    return cve


class GuncelleTests(TestCase):

    def test_kev_eklenince_tarih_kaynak_ve_katalog_baglantisi_yazilir_ceviri_korunur(self):
        kayit = _kayit()
        degisti = cve_guncelleme.guncelle(kayit, _sozluk(
            source='CISA KEV', kev_added_date=date(2026, 11, 5),
            original_description='Added to the CISA KEV catalog on 2026-11-05. A remote attacker ...',
            references=[KATALOG, 'https://vendor.example/a']))

        self.assertTrue(degisti)
        kayit.refresh_from_db()
        self.assertEqual(kayit.kev_added_date, date(2026, 11, 5))
        self.assertEqual(kayit.source, 'CISA KEV')
        self.assertEqual(kayit.references[0], KATALOG)
        self.assertFalse(kayit.needs_translation)
        self.assertTrue(kayit.turkish_description.startswith('Uzaktan bir saldırgan'))
        self.assertEqual(kayit.original_description, _sozluk()['original_description'],
                         'Gercek aciklama KEV onekiyle yeniden yazilmaz (rozet kev_added_date ile gelir)')

    def test_cvss_degisince_skor_ve_onem_guncellenir(self):
        kayit = _kayit()
        self.assertTrue(cve_guncelleme.guncelle(kayit, _sozluk(cvss_score=9.8, severity='Kritik',
                                                               modified_date=date(2026, 11, 6))))
        kayit.refresh_from_db()
        self.assertEqual((kayit.cvss_score, kayit.severity, kayit.modified_date),
                         (9.8, 'Kritik', date(2026, 11, 6)))

    def test_degisiklik_yoksa_yazilmaz_updated_at_ilerlemez(self):
        kayit = _kayit()
        once = kayit.updated_at
        self.assertFalse(cve_guncelleme.guncelle(kayit, _sozluk()))
        kayit.refresh_from_db()
        self.assertEqual(kayit.updated_at, once)

    def test_tenable_ve_ghsa_guncelleme_yapmaz(self):
        kayit = _kayit()
        for kaynak in ('Tenable', 'GitHub Advisory'):
            with self.subTest(kaynak=kaynak):
                self.assertFalse(cve_guncelleme.guncelle(kayit, _sozluk(source=kaynak, cvss_score=9.5)))
        kayit.refresh_from_db()
        self.assertEqual(kayit.cvss_score, 7.5)

    def test_yer_tutucu_aciklama_gercegiyle_degisir_ve_ceviri_kuyruguna_doner(self):
        kayit = _kayit(source='Tenable', original_description='No description provided',
                       turkish_description='No description provided', translation_provider='',
                       translation_attempts=3)
        self.assertTrue(cve_guncelleme.guncelle(kayit, _sozluk()))
        kayit.refresh_from_db()
        self.assertEqual(kayit.original_description, _sozluk()['original_description'])
        self.assertEqual(kayit.turkish_description, '')
        self.assertTrue(kayit.needs_translation)
        self.assertEqual((kayit.translation_attempts, kayit.translation_provider), (0, ''))
        self.assertEqual(kayit.source, 'Tenable', 'Kaynak yalniz KEV eklenince degisir')

    def test_gercek_aciklama_baska_metinle_ezilmez(self):
        kayit = _kayit()
        cve_guncelleme.guncelle(kayit, _sozluk(original_description='Reworded upstream description text.'))
        kayit.refresh_from_db()
        self.assertEqual(kayit.original_description, _sozluk()['original_description'])
        self.assertFalse(kayit.needs_translation)

    def test_kev_kaydinin_katalog_baglantisi_nvd_guncellemesinde_kaybolmaz(self):
        kayit = _kayit(source='CISA KEV', kev_added_date=date(2026, 11, 1),
                       references=[KATALOG, 'https://vendor.example/a'])
        cve_guncelleme.guncelle(kayit, _sozluk(references=['https://vendor.example/b']))
        kayit.refresh_from_db()
        self.assertEqual(kayit.references, [KATALOG, 'https://vendor.example/b'])
        self.assertEqual(kayit.kev_added_date, date(2026, 11, 1))


class YeniKayitSecimiTests(SimpleTestCase):

    def test_nvd_guncel_pencere_disi_elenir_digerleri_kalir(self):
        bugun = timezone.localdate()
        cves = [
            {'cve_id': 'A', 'source': 'NVD Güncel', 'published_date': bugun - timedelta(days=30), 'cvss_score': 9.8},
            {'cve_id': 'B', 'source': 'NVD Güncel', 'published_date': bugun - timedelta(days=2), 'cvss_score': 5.0},
            {'cve_id': 'C', 'source': 'Tenable', 'published_date': bugun - timedelta(days=30), 'cvss_score': 6.0},
        ]
        self.assertEqual({c['cve_id'] for c in cve_guncelleme.yeni_kayit_secimi(cves, 7)}, {'B', 'C'})

    def test_sira_kev_sonra_cvss_ve_tavan(self):
        cves = [{'cve_id': f'X{i}', 'source': 'NVD', 'cvss_score': s} for i, s in enumerate([5.0, 9.8, None, 7.1])]
        cves.append({'cve_id': 'KEV', 'source': 'CISA KEV', 'cvss_score': 6.0, 'kev_added_date': date(2026, 11, 1)})
        with mock.patch.object(cve_guncelleme, 'CVE_TUR_TAVANI', 3):
            secilen = cve_guncelleme.yeni_kayit_secimi(cves, 7)
        self.assertEqual([c['cve_id'] for c in secilen], ['KEV', 'X1', 'X3'])


class FetchCveTaskGuncellemeTests(TestCase):

    def setUp(self):
        yama = mock.patch('news.tasks.MultiCVEScraper')
        self.scraper = yama.start()
        self.addCleanup(yama.stop)

    def test_var_olan_cevrilmis_kayit_guncellenir_yalniz_yeni_kayit_islenir(self):
        _kayit()
        yeni = _sozluk(cve_id='CVE-2026-2000', source='NVD', published_date=timezone.localdate(),
                       link='https://nvd.nist.gov/vuln/detail/CVE-2026-2000')
        ornek = self.scraper.return_value
        ornek.fetch_all_cves.return_value = [
            _sozluk(source='CISA KEV', kev_added_date=date(2026, 11, 5), references=[KATALOG]), yeni]
        islenen = []

        def _isle(cves):
            islenen.extend(c['cve_id'] for c in cves)
            for c in cves:
                yield dict(c, turkish_title=c['original_title'], turkish_description='Türkçe açıklama.')
        ornek.process_cves.side_effect = _isle

        sonuc = tasks.fetch_cve_task(days=7, skip_existing=True)

        self.assertEqual(islenen, ['CVE-2026-2000'])
        self.assertEqual(CVEEntry.objects.get(cve_id='CVE-2026-1000').kev_added_date, date(2026, 11, 5))
        self.assertEqual(sonuc['count'], 1)
        self.assertEqual(sonuc['by_source']['CISA KEV']['updated'], 1)

    def test_yeni_kayit_yokken_guncelleme_yine_yapilir(self):
        _kayit()
        ornek = self.scraper.return_value
        ornek.fetch_all_cves.return_value = [_sozluk(cvss_score=9.1, severity='Kritik')]
        ornek.process_cves.side_effect = AssertionError('ceviri cagrilmamali')

        sonuc = tasks.fetch_cve_task(days=7, skip_existing=True)

        self.assertEqual(sonuc['count'], 0)
        self.assertEqual(CVEEntry.objects.get(cve_id='CVE-2026-1000').cvss_score, 9.1)


def _nvd_oge(cve_id, aciklama='A remote attacker can execute arbitrary code via crafted packets.', skor=9.8):
    return {'cve': {
        'id': cve_id, 'vulnStatus': 'Analyzed', 'published': '2026-11-01T10:00:00.000',
        'lastModified': '2026-11-02T10:00:00.000',
        'descriptions': [{'lang': 'en', 'value': aciklama}],
        'metrics': {'cvssMetricV31': [{'cvssData': {'baseScore': skor, 'baseSeverity': 'CRITICAL'}}]},
        'references': [], 'weaknesses': [],
    }}


class NvdSayfalamaTests(SimpleTestCase):

    def test_totalresults_kadar_sayfa_ister(self):
        s = NVDScraper()
        sayfalar = [
            SahteYanit(json_data={'totalResults': 3, 'vulnerabilities': [_nvd_oge('CVE-1'), _nvd_oge('CVE-2')]}),
            SahteYanit(json_data={'totalResults': 3, 'vulnerabilities': [_nvd_oge('CVE-3')]}),
        ]
        with mock.patch.object(s.session, 'get', side_effect=sayfalar) as get:
            cves = s.fetch_cves(days=7)
        self.assertEqual([c['cve_id'] for c in cves], ['CVE-1', 'CVE-2', 'CVE-3'])
        self.assertEqual([c.kwargs['params']['startIndex'] for c in get.call_args_list], [0, 2])

    def test_totalresults_yoksa_tek_sayfa(self):
        s = NVDScraper()
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(
                json_data={'vulnerabilities': [_nvd_oge('CVE-1')]})) as get:
            self.assertEqual(len(s.fetch_cves(days=7)), 1)
        self.assertEqual(get.call_count, 1)

    def test_tavanda_durur(self):
        s = NVDScraper()
        yanit = SahteYanit(json_data={'totalResults': 10, 'vulnerabilities': [_nvd_oge('CVE-1'), _nvd_oge('CVE-2')]})
        with mock.patch('news.cve_scraper.NVD_YAYIN_TAVANI', 2), \
                mock.patch.object(s.session, 'get', return_value=yanit) as get:
            s.fetch_cves(days=7)
        self.assertEqual(get.call_count, 1)
        self.assertEqual(get.call_args.kwargs['params']['resultsPerPage'], 2)

    def test_ara_sayfa_hatasinda_okunanlar_doner(self):
        s = NVDScraper()
        sayfalar = [SahteYanit(json_data={'totalResults': 4, 'vulnerabilities': [_nvd_oge('CVE-1'), _nvd_oge('CVE-2')]}),
                    SahteYanit(status=503)]
        with mock.patch.object(s.session, 'get', side_effect=sayfalar):
            self.assertEqual([c['cve_id'] for c in s.fetch_cves(days=7)], ['CVE-1', 'CVE-2'])

    def test_guncel_penceresi_en_fazla_iki_gun_ve_kaynak_adi(self):
        s = NVDRecentScraper()
        with mock.patch.object(s.session, 'get', return_value=SahteYanit(
                json_data={'vulnerabilities': [_nvd_oge('CVE-1')]})) as get:
            cves = s.fetch_cves(days=7)
        params = get.call_args.kwargs['params']
        bas = datetime.fromisoformat(params['lastModStartDate'][:19])
        son = datetime.fromisoformat(params['lastModEndDate'][:19])
        self.assertAlmostEqual((son - bas).total_seconds(), 2 * 86400, delta=5)
        self.assertEqual(params['startIndex'], 0)
        self.assertEqual(cves[0]['source'], 'NVD Güncel')


class KaynakOnceligiTests(SimpleTestCase):

    def test_nvd_ailesi_tenable_ve_ghsa_nin_onune_gecer_sira_korunur(self):
        cves = [
            {'cve_id': 'A', 'source': 'Tenable', 'cvss_score': 9.5},
            {'cve_id': 'B', 'source': 'GitHub Advisory'},
            {'cve_id': 'A', 'source': 'NVD Güncel', 'cvss_score': 8.1},
            {'cve_id': 'B', 'source': 'Tenable'},
            {'cve_id': 'C', 'source': 'CISA KEV'},
            {'cve_id': 'C', 'source': 'NVD'},
        ]
        sonuc = tekillestir(cves)
        self.assertEqual([(c['cve_id'], c['source']) for c in sonuc],
                         [('A', 'NVD Güncel'), ('B', 'GitHub Advisory'), ('C', 'CISA KEV')])


class YerTutucuTests(SimpleTestCase):

    def test_yer_tutucular(self):
        for metin in ('No description provided', 'No description provided.', '', None, 'n/a', 'kisa'):
            with self.subTest(metin=metin):
                self.assertTrue(aciklama_yer_tutucu_mu(metin))
        self.assertFalse(aciklama_yer_tutucu_mu('A remote attacker can execute arbitrary code.'))


class AciklamaTamamlaKomutuTests(TestCase):

    def test_rapor_modu_yazmaz_uygula_nvd_aciklamasini_yazar(self):
        from io import StringIO

        from django.core.management import call_command
        _kayit(cve_id='CVE-2026-3000', source='Tenable', original_description='No description provided',
               turkish_description='No description provided', link='https://www.tenable.com/cve/CVE-2026-3000')
        _kayit(cve_id='CVE-2026-3001', link='https://nvd.nist.gov/vuln/detail/CVE-2026-3001')

        cikti = StringIO()
        call_command('cve_aciklama_tamamla', stdout=cikti)
        self.assertIn('Yer tutucu aciklamali CVE: 1', cikti.getvalue())
        self.assertEqual(CVEEntry.objects.get(cve_id='CVE-2026-3000').original_description, 'No description provided')

        yanit = SahteYanit(json_data={'vulnerabilities': [_nvd_oge('CVE-2026-3000', aciklama='Auth bypass lets a remote attacker run commands.')]})
        with mock.patch('requests.Session.get', return_value=yanit) as get:
            call_command('cve_aciklama_tamamla', '--uygula', stdout=StringIO())

        self.assertEqual(get.call_args.kwargs['params'], {'cveId': 'CVE-2026-3000'})
        kayit = CVEEntry.objects.get(cve_id='CVE-2026-3000')
        self.assertEqual(kayit.original_description, 'Auth bypass lets a remote attacker run commands.')
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(kayit.cvss_score, 9.8)
