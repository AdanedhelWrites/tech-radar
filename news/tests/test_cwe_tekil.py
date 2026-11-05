"""CWE kimliklerinin tekillestirilmesi: NVD ayristiricisi ve 0018 veri gocu."""
import importlib
from datetime import date

from django.apps import apps
from django.test import SimpleTestCase, TestCase

from news.cve_scraper import nvd_cwe_listesi, tekil_cwe
from news.models import CVEEntry

goc = importlib.import_module('news.migrations.0018_cve_cwe_tekillestir')


class TekilCweTests(SimpleTestCase):

    def test_nvd_primary_ve_secondary_ayni_cwe_tek_kalir(self):
        weaknesses = [
            {'source': 'nvd@nist.gov', 'type': 'Primary',
             'description': [{'lang': 'en', 'value': 'CWE-787'}]},
            {'source': 'cna@example.com', 'type': 'Secondary',
             'description': [{'lang': 'en', 'value': 'CWE-787'},
                             {'lang': 'en', 'value': 'CWE-20'}]},
        ]
        self.assertEqual(nvd_cwe_listesi(weaknesses), ['CWE-787', 'CWE-20'])

    def test_cwe_olmayan_degerler_atilir(self):
        weaknesses = [{'description': [{'value': 'NVD-CWE-noinfo'},
                                       {'value': 'NVD-CWE-Other'},
                                       {'value': 'CWE-79'}]}]
        self.assertEqual(nvd_cwe_listesi(weaknesses), ['CWE-79'])

    def test_bos_ve_eksik_girdi(self):
        self.assertEqual(nvd_cwe_listesi(None), [])
        self.assertEqual(nvd_cwe_listesi([{}]), [])
        self.assertEqual(tekil_cwe(None), [])

    def test_sira_korunur_bos_deger_atilir(self):
        self.assertEqual(tekil_cwe(['CWE-79', '', 'CWE-89', 'CWE-79']),
                         ['CWE-79', 'CWE-89'])


class CweGocuTests(TestCase):

    def _cve(self, cve_id, cwe_ids):
        return CVEEntry.objects.create(
            cve_id=cve_id, source='NVD Güncel', original_title=f'{cve_id} - ornek',
            original_description='ornek', published_date=date(2026, 11, 5),
            link=f'https://nvd.example/{cve_id}', cwe_ids=cwe_ids)

    def test_yinelenen_cwe_temizlenir_digerleri_dokunulmaz(self):
        yinelenen = self._cve('CVE-2026-0001', ['CWE-862', 'CWE-639', 'CWE-862'])
        temiz = self._cve('CVE-2026-0002', ['CWE-79'])
        bos = self._cve('CVE-2026-0003', [])
        temiz_once = CVEEntry.objects.get(pk=temiz.pk).updated_at

        goc.cwe_tekillestir(apps, None)

        self.assertEqual(CVEEntry.objects.get(pk=yinelenen.pk).cwe_ids,
                         ['CWE-862', 'CWE-639'])
        self.assertEqual(CVEEntry.objects.get(pk=temiz.pk).cwe_ids, ['CWE-79'])
        self.assertEqual(CVEEntry.objects.get(pk=temiz.pk).updated_at, temiz_once)
        self.assertEqual(CVEEntry.objects.get(pk=bos.pk).cwe_ids, [])
