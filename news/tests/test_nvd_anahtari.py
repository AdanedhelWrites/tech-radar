"""NVD_API_KEY (2026-10-08): yalniz services.nvd.nist.gov isteklerine apiKey basligi."""
import os
from unittest import mock

from django.test import SimpleTestCase

from news.cve_scraper import CISAKEVScraper, NVDRecentScraper, NVDScraper


class _Yanit:
    ok = True
    status_code = 200

    def json(self):
        return {'vulnerabilities': []}

    def raise_for_status(self):
        pass


class NVDAnahtariTests(SimpleTestCase):

    def test_anahtar_yalniz_nvd_hostuna_gider(self):
        s = NVDScraper()
        with mock.patch.dict(os.environ, {'NVD_API_KEY': 'nvd-test'}), \
                mock.patch.object(s.session, 'get', return_value=_Yanit()) as get:
            s._nvd_get('https://services.nvd.nist.gov/rest/json/cves/2.0', params={'x': 1})
            s._nvd_get('https://cve.circl.lu/api/last/50')

        self.assertEqual(get.call_args_list[0].kwargs['headers'], {'apiKey': 'nvd-test'})
        self.assertEqual(get.call_args_list[0].kwargs['params'], {'x': 1})
        self.assertEqual(get.call_args_list[1].kwargs['headers'], {})
        self.assertNotIn('apiKey', s.session.headers)

    def test_anahtar_yoksa_baslik_yok(self):
        s = NVDScraper()
        with mock.patch.dict(os.environ, {'NVD_API_KEY': ''}), \
                mock.patch.object(s.session, 'get', return_value=_Yanit()) as get:
            s._nvd_get('https://services.nvd.nist.gov/rest/json/cves/2.0')
        self.assertEqual(get.call_args.kwargs['headers'], {})

    def test_uc_nvd_scraper_i_da_yardimciyi_kullanir(self):
        for cls in (NVDScraper, NVDRecentScraper, CISAKEVScraper):
            with self.subTest(cls=cls.__name__):
                s = cls()
                with mock.patch.dict(os.environ, {'NVD_API_KEY': 'nvd-test'}), \
                        mock.patch.object(s.session, 'get', return_value=_Yanit()) as get, \
                        mock.patch('news.cve_scraper.time.sleep'):
                    s.fetch_cves(days=3)
                self.assertEqual(get.call_args.kwargs['headers'].get('apiKey'), 'nvd-test')
                self.assertTrue(get.call_args.args[0].startswith('https://services.nvd.nist.gov/'))
