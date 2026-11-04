"""GitHub Advisory basligi (2026-11-04): ozet 80 karakterde kelime ortasindan kesilmez. Ag erisimi yok."""
from unittest import mock

from django.test import SimpleTestCase

from news.cve_scraper import GitHubAdvisoryScraper

UZUN_OZET = 'zip: Critical Parser Differential & Security Control Bypass via Dual-Header Inconsistency'


def _yanit(ozet):
    yanit = mock.Mock()
    yanit.raise_for_status.return_value = None
    yanit.json.return_value = [{
        'cve_id': 'CVE-2026-115905', 'summary': ozet, 'description': 'Long description.',
        'published_at': '2026-11-01T00:00:00Z', 'html_url': 'https://github.com/advisories/GHSA-x',
        'cvss_severities': {}, 'severity': 'critical', 'cwes': [], 'vulnerabilities': [], 'references': [],
    }]
    return yanit


class GhsaBaslikTests(SimpleTestCase):

    def _cek(self, ozet):
        tarayici = GitHubAdvisoryScraper()
        with mock.patch.object(tarayici.session, 'get', return_value=_yanit(ozet)):
            return tarayici.fetch_cves(days=7)

    def test_uzun_ozet_tamami_basliga_yazilir(self):
        kayitlar = self._cek(UZUN_OZET)
        self.assertEqual(kayitlar[0]['original_title'], f'CVE-2026-115905 - {UZUN_OZET}')

    def test_ozet_yoksa_sablon_baslik(self):
        kayitlar = self._cek('')
        self.assertEqual(kayitlar[0]['original_title'], 'CVE-2026-115905 - Güvenlik Açığı')
