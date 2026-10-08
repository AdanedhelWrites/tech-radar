"""Guvenlik basliklari (GUVENLIK-PLANI, ZAP bulgulari 2026-10-08).

- Content-Security-Policy (django-csp): script-src yalniz 'self' + nonce; inline script yok.
- Permissions-Policy, Cross-Origin-Resource-Policy, Cross-Origin-Embedder-Policy (kendi middleware).
- WhiteNoise statik dosyalarda Access-Control-Allow-Origin: * gondermez (ZAP "Cross-Domain Misconfiguration").
- /api/v1/docs/ Swagger UI'si inline script yerine ayri script URL'si kullanir (SpectacularSwaggerSplitView).
"""
import os
import re
import tempfile

from csp.constants import NONCE
from csp.middleware import CSPMiddleware
from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from .base import V1TestCase

NONCE_DESENI = re.compile(r"'nonce-([A-Za-z0-9+/=_-]{16,})'")


def _csp(yanit):
    return yanit.headers.get('Content-Security-Policy', '')


def _yonerge(csp, ad):
    for parca in csp.split(';'):
        parca = parca.strip()
        if parca.startswith(ad + ' ') or parca == ad:
            return parca[len(ad):].strip()
    return None


class BasliklarTests(SimpleTestCase):
    databases = []

    def test_csp_basligi_ve_yonergeleri(self):
        yanit = self.client.get('/api/v1/health/')
        csp = _csp(yanit)
        self.assertTrue(csp, 'Content-Security-Policy basligi yok')
        self.assertEqual(_yonerge(csp, 'default-src'), "'self'")
        # django-csp 4: nonce yalniz bir sablon request.csp_nonce kullandiginda basliga girer;
        # inline script olmayan yanitta script-src tam olarak 'self' kalir.
        self.assertEqual(_yonerge(csp, 'script-src'), "'self'")
        self.assertNotIn("'unsafe-inline'", _yonerge(csp, 'script-src'))
        self.assertNotIn("'unsafe-eval'", csp)
        self.assertIn(NONCE, settings.CONTENT_SECURITY_POLICY['DIRECTIVES']['script-src'])
        self.assertEqual(_yonerge(csp, 'object-src'), "'none'")
        self.assertEqual(_yonerge(csp, 'frame-ancestors'), "'none'")
        self.assertEqual(_yonerge(csp, 'base-uri'), "'self'")
        self.assertEqual(_yonerge(csp, 'form-action'), "'self'")

    def test_nonce_kullanildiginda_basliga_girer_ve_istek_basina_farkli(self):
        # Bir sablon {{ request.csp_nonce }} kullanirsa ayni deger script-src'ye 'nonce-...' olarak girer.
        kullanilan = []

        def gorunum(request):
            kullanilan.append(str(request.csp_nonce))
            return HttpResponse('<script nonce="%s"></script>' % kullanilan[-1])

        ara = CSPMiddleware(gorunum)
        fabrika = RequestFactory()
        a = ara(fabrika.get('/'))
        b = ara(fabrika.get('/'))
        for yanit, nonce in ((a, kullanilan[0]), (b, kullanilan[1])):
            script = _yonerge(_csp(yanit), 'script-src')
            self.assertIn("'self'", script)
            self.assertIn(f"'nonce-{nonce}'", script)
            self.assertRegex(script, NONCE_DESENI)
        self.assertNotEqual(kullanilan[0], kullanilan[1])

    def test_permissions_ve_cross_origin_basliklari(self):
        yanit = self.client.get('/api/v1/health/')
        pp = yanit.headers.get('Permissions-Policy', '')
        for ozellik in ('camera=()', 'microphone=()', 'geolocation=()', 'payment=()'):
            self.assertIn(ozellik, pp)
        self.assertEqual(yanit.headers.get('Cross-Origin-Resource-Policy'), 'same-origin')
        self.assertEqual(yanit.headers.get('Cross-Origin-Embedder-Policy'), 'require-corp')
        # Django'nun kendi varsayilanlari bozulmadi
        self.assertEqual(yanit.headers.get('X-Content-Type-Options'), 'nosniff')
        self.assertEqual(yanit.headers.get('X-Frame-Options'), 'DENY')
        self.assertEqual(yanit.headers.get('Cross-Origin-Opener-Policy'), 'same-origin')

    def test_basliklar_404_sayfasinda_da_var(self):
        yanit = self.client.get('/boyle-bir-yol-yok/')
        self.assertEqual(yanit.status_code, 404)
        self.assertIn("default-src 'self'", _csp(yanit))
        self.assertIn('camera=()', yanit.headers.get('Permissions-Policy', ''))

    def test_admin_login_sayfasi_csp_ile_acilir(self):
        yanit = self.client.get('/admin/login/')
        self.assertEqual(yanit.status_code, 200)
        govde = yanit.content.decode()
        # Admin sablonlarinda inline script yok; CSP 'self' + nonce ile bozulmaz
        self.assertNotRegex(govde, r'<script(?![^>]*\bsrc=)[^>]*>\s*\S')
        self.assertIn("default-src 'self'", _csp(yanit))

    def test_statik_dosyada_acao_yildiz_yok(self):
        # WhiteNoise varsayilani Access-Control-Allow-Origin: * gonderir (ZAP 10098).
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'deneme.css'), 'w', encoding='utf-8') as f:
                f.write('body{}')
            with override_settings(STATIC_ROOT=d):
                yanit = self.client.get('/static/deneme.css')
        self.assertEqual(yanit.status_code, 200, 'WhiteNoise gecici STATIC_ROOT dosyasini sunmali')
        self.assertNotIn('Access-Control-Allow-Origin', yanit.headers)


class DocsCspTests(V1TestCase):

    def test_docs_inline_script_yok_ayri_script_ucu(self):
        yanit = self.client.get('/api/v1/docs/', **self.token_basligi())
        self.assertEqual(yanit.status_code, 200)
        govde = yanit.content.decode()
        self.assertNotRegex(govde, r'<script(?![^>]*\bsrc=)[^>]*>\s*\S',
                            'docs sayfasinda inline script kalmamali (CSP script-src self+nonce)')
        self.assertIn('/api/v1/docs/?', govde)
        self.assertIn('script=', govde)

    def test_docs_script_ucu_javascript_doner(self):
        yanit = self.client.get('/api/v1/docs/?script=', **self.token_basligi())
        self.assertEqual(yanit.status_code, 200)
        self.assertTrue(yanit['Content-Type'].startswith('application/javascript'))
        self.assertIn('SwaggerUIBundle', yanit.content.decode())

    def test_docs_script_ucu_tokensiz_401(self):
        self.assertEqual(self.client.get('/api/v1/docs/?script=').status_code, 401)
