"""Loglama (2026-10-08): print yerine logging; LOG_LEVEL / LOG_FORMAT; JSON bicimi."""
import json
import logging
import re
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from cybernews import loglama

KOK = Path(__file__).resolve().parents[2]


class JsonFormatterTests(SimpleTestCase):

    def _kayit(self, msg, **ekstra):
        kayit = logging.LogRecord('news.devtools_scraper', logging.WARNING, __file__, 1, msg, None, None)
        for ad, deger in ekstra.items():
            setattr(kayit, ad, deger)
        return kayit

    def test_satir_basina_json_ve_ekstra_alanlar(self):
        satir = loglama.JsonFormatter().format(self._kayit('[GitLab] Atom hatasi: %s', kaynak='GitLab'))
        govde = json.loads(satir)

        self.assertEqual(govde['level'], 'WARNING')
        self.assertEqual(govde['logger'], 'news.devtools_scraper')
        self.assertEqual(govde['msg'], '[GitLab] Atom hatasi: %s')
        self.assertEqual(govde['kaynak'], 'GitLab')
        self.assertTrue(govde['ts'].endswith('+00:00'))
        self.assertNotIn('\n', satir)

    def test_istisna_exc_alaninda(self):
        try:
            raise ValueError('bozuk')
        except ValueError:
            import sys
            kayit = self._kayit('hata')
            kayit.exc_info = sys.exc_info()
        govde = json.loads(loglama.JsonFormatter().format(kayit))
        self.assertIn('ValueError: bozuk', govde['exc'])

    def test_turkce_karakter_kacirilmaz(self):
        govde = loglama.JsonFormatter().format(self._kayit('çeviri bekliyor'))
        self.assertIn('çeviri bekliyor', govde)


class LoglamaAyariTests(SimpleTestCase):

    def test_varsayilan_text_info(self):
        ayar = loglama.loglama_ayari({})
        self.assertEqual(ayar['handlers']['console']['formatter'], 'text')
        self.assertEqual(ayar['root']['level'], 'INFO')
        self.assertEqual(ayar['loggers']['django']['level'], 'WARNING')

    def test_ortamdan_json_ve_debug(self):
        ayar = loglama.loglama_ayari({'LOG_FORMAT': 'json', 'LOG_LEVEL': 'debug'})
        self.assertEqual(ayar['handlers']['console']['formatter'], 'json')
        self.assertEqual(ayar['root']['level'], 'DEBUG')
        self.assertEqual(ayar['loggers']['news']['level'], 'DEBUG')

    def test_settings_logging_ve_celery_hijack_kapali(self):
        self.assertIn('console', settings.LOGGING['handlers'])
        self.assertFalse(settings.CELERY_WORKER_HIJACK_ROOT_LOGGER)


class PrintKalmadiTests(SimpleTestCase):
    """Scraper ve ceviri katmaninda print() kalmamali; logging kullanilmali."""

    DOSYALAR = [
        'scraper_multi.py', 'news/base_scraper.py', 'news/ai_scraper.py', 'news/cve_scraper.py',
        'news/k8s_scraper.py', 'news/sre_scraper.py', 'news/devtools_scraper.py',
        'news/tasks.py', 'news/retranslate.py', 'news/fetch_runs.py', 'news/gemini.py',
        'news/translation_utils.py', 'news/translation_providers.py', 'news/api_v1/job_signals.py',
    ]

    def test_print_cagrisi_yok(self):
        desen = re.compile(r'^\s*print\(', re.MULTILINE)
        for yol in self.DOSYALAR:
            with self.subTest(dosya=yol):
                metin = (KOK / yol).read_text(encoding='utf-8')
                # __main__ blogundaki ornek ciktilar sayilmaz
                govde = metin.split('if __name__ == "__main__":')[0]
                self.assertIsNone(desen.search(govde), f'{yol} icinde print() kaldi')
                self.assertIn('getLogger(__name__)', metin, f'{yol} logger tanimlamiyor')
