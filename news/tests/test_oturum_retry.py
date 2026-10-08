"""Yeniden denemeli HTTP oturumu (2026-10-08): news/base_scraper.oturum_kur ve scraper tabanlari."""
import io
from unittest import mock

import requests
from django.test import SimpleTestCase
from urllib3.response import HTTPResponse

import scraper_multi as sm
from news.base_scraper import BaseRSSScraper, oturum_kur
from news.cve_scraper import CVEScraper
from news.devtools_scraper import DevToolsScraper
from news.k8s_scraper import K8sScraper
from news.sre_scraper import SREScraper


class OturumKurTests(SimpleTestCase):

    def test_adaptor_ayarlari(self):
        s = oturum_kur({'User-Agent': 'test'})
        for sema in ('https://ornek.test/', 'http://ornek.test/'):
            yeniden = s.get_adapter(sema).max_retries
            self.assertEqual(yeniden.total, 2)
            self.assertEqual(yeniden.backoff_factor, 1)
            self.assertIn(503, yeniden.status_forcelist)
            self.assertIn(429, yeniden.status_forcelist)
            self.assertFalse(yeniden.raise_on_status)
            self.assertEqual(set(yeniden.allowed_methods), {'GET', 'HEAD'})
        self.assertEqual(s.headers['User-Agent'], 'test')

    def test_gecici_503_sonra_200_tek_cagriyla_basarir(self):
        s = oturum_kur()
        yanitlar = [
            HTTPResponse(body=io.BytesIO(b''), status=503, preload_content=False, headers={'Retry-After': '0'}),
            HTTPResponse(body=io.BytesIO(b'tamam'), status=200, preload_content=False),
        ]
        with mock.patch('urllib3.connectionpool.HTTPConnectionPool._make_request', side_effect=yanitlar), \
                mock.patch('urllib3.util.retry.time.sleep'):
            yanit = s.get('http://ornek.test/akis')
        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.content, b'tamam')

    def test_denemeler_bitince_son_yanit_doner_istisna_degil(self):
        s = oturum_kur()
        yanitlar = [HTTPResponse(body=io.BytesIO(b''), status=503, preload_content=False) for _ in range(3)]
        with mock.patch('urllib3.connectionpool.HTTPConnectionPool._make_request', side_effect=yanitlar), \
                mock.patch('urllib3.util.retry.time.sleep'):
            yanit = s.get('http://ornek.test/akis')
        self.assertEqual(yanit.status_code, 503)
        with self.assertRaises(requests.HTTPError):
            yanit.raise_for_status()


class ScraperTabanlariTests(SimpleTestCase):

    def test_butun_tabanlar_yeniden_denemeli_oturum_kullanir(self):
        class HaberKaynagi(sm.NewsSource):
            def get_name(self): return 'x'
            def fetch_news(self, days=7): return []
            def get_base_url(self): return 'https://ornek.test'

        for taban in (BaseRSSScraper(), HaberKaynagi(), CVEScraper(), K8sScraper(), SREScraper(), DevToolsScraper()):
            with self.subTest(taban=type(taban).__name__):
                self.assertEqual(taban.session.get_adapter('https://x.test/').max_retries.total, 2)
                self.assertIn('User-Agent', taban.session.headers)
