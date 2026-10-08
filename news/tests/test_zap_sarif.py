"""scripts/zap_sarif.py: ZAP baseline JSON raporu -> SARIF 2.1.0 (GUVENLIK-PLANI P5).

Veritabani gerekmez. Betik Django'ya bagli degildir; importlib ile dosya yolundan yuklenir.
"""
import importlib.util
import json
import os
import tempfile

from django.test import SimpleTestCase

BETIK = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'zap_sarif.py')


def _yukle():
    spec = importlib.util.spec_from_file_location('zap_sarif', BETIK)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


ORNEK_RAPOR = {
    "@version": "2.16.1",
    "@generated": "Wed, 8 Oct 2026 03:20:00",
    "site": [
        {
            "@name": "http://localhost:8000",
            "@host": "localhost",
            "@port": "8000",
            "@ssl": "false",
            "alerts": [
                {
                    "pluginid": "10038",
                    "alertRef": "10038-1",
                    "alert": "Content Security Policy (CSP) Header Not Set",
                    "name": "Content Security Policy (CSP) Header Not Set",
                    "riskcode": "2",
                    "confidence": "3",
                    "riskdesc": "Medium (High)",
                    "desc": "<p>CSP basligi yok.</p>",
                    "instances": [
                        {"uri": "http://localhost:8000/admin/login/", "method": "GET", "param": "", "attack": "", "evidence": "", "otherinfo": ""},
                        {"uri": "http://localhost:8000/admin/", "method": "GET", "param": "", "attack": "", "evidence": "", "otherinfo": ""},
                    ],
                    "count": "2",
                    "solution": "<p>CSP basligi ekleyin.</p>",
                    "otherinfo": "",
                    "reference": "<p>https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP</p>",
                    "cweid": "693",
                    "wascid": "15",
                    "sourceid": "1",
                },
                {
                    "pluginid": "10021",
                    "alertRef": "10021",
                    "alert": "X-Content-Type-Options Header Missing",
                    "name": "X-Content-Type-Options Header Missing",
                    "riskcode": "1",
                    "confidence": "2",
                    "riskdesc": "Low (Medium)",
                    "desc": "<p>nosniff yok.</p>",
                    "instances": [
                        {"uri": "http://localhost:8000/static/admin/css/base.css", "method": "GET", "param": "x-content-type-options", "attack": "", "evidence": "", "otherinfo": ""},
                    ],
                    "count": "1",
                    "solution": "<p>nosniff ekleyin.</p>",
                    "otherinfo": "",
                    "reference": "",
                    "cweid": "693",
                    "wascid": "15",
                    "sourceid": "3",
                },
                {
                    "pluginid": "10015",
                    "alertRef": "10015",
                    "alert": "Re-examine Cache-control Directives",
                    "name": "Re-examine Cache-control Directives",
                    "riskcode": "0",
                    "confidence": "1",
                    "riskdesc": "Informational (Low)",
                    "desc": "<p>Bilgi.</p>",
                    "instances": [
                        {"uri": "http://localhost:8000/admin/login/", "method": "GET", "param": "cache-control", "attack": "", "evidence": "max-age=0", "otherinfo": ""},
                    ],
                    "count": "1",
                    "solution": "",
                    "otherinfo": "",
                    "reference": "",
                    "cweid": "525",
                    "wascid": "13",
                    "sourceid": "3",
                },
            ],
        }
    ],
}


class ZapSarifTests(SimpleTestCase):

    def setUp(self):
        self.m = _yukle()

    def test_sarif_iskeleti_ve_surum(self):
        sarif = self.m.donustur(ORNEK_RAPOR)
        self.assertEqual(sarif['version'], '2.1.0')
        self.assertIn('$schema', sarif)
        run = sarif['runs'][0]
        self.assertEqual(run['tool']['driver']['name'], 'OWASP ZAP')
        self.assertEqual(run['tool']['driver']['version'], '2.16.1')

    def test_kurallar_alert_basina_tek_ve_siddet_tasir(self):
        run = self.m.donustur(ORNEK_RAPOR)['runs'][0]
        kurallar = {k['id']: k for k in run['tool']['driver']['rules']}
        self.assertEqual(set(kurallar), {'zap/10038', 'zap/10021', 'zap/10015'})
        csp = kurallar['zap/10038']
        self.assertEqual(csp['name'], 'Content Security Policy (CSP) Header Not Set')
        # GitHub security-severity: 4.0-6.9 medium
        self.assertEqual(csp['properties']['security-severity'], '5.0')
        self.assertIn('CWE-693', csp['properties']['tags'])
        # HTML etiketleri temizlenir; cozum ve kaynak help'e girer
        self.assertNotIn('<p>', csp['fullDescription']['text'])
        self.assertIn('CSP basligi ekleyin.', csp['help']['text'])
        self.assertIn('developer.mozilla.org', csp['help']['text'])

    def test_sonuclar_instance_basina_ve_seviye_eslemesi(self):
        run = self.m.donustur(ORNEK_RAPOR)['runs'][0]
        sonuclar = run['results']
        self.assertEqual(len(sonuclar), 4)
        # GitHub Code Scanning "http" semali artifactLocation kabul etmez (checkout semasi "file"):
        # konum sanal goreli yol, tam URL mesajda ve logicalLocations'ta
        seviye = {(s['ruleId'], s['locations'][0]['physicalLocation']['artifactLocation']['uri']): s['level'] for s in sonuclar}
        self.assertEqual(seviye[('zap/10038', 'dast/admin/login/')], 'warning')
        self.assertEqual(seviye[('zap/10021', 'dast/static/admin/css/base.css')], 'note')
        self.assertEqual(seviye[('zap/10015', 'dast/admin/login/')], 'note')
        for s in sonuclar:
            uri = s['locations'][0]['physicalLocation']['artifactLocation']['uri']
            self.assertFalse(uri.startswith(('http://', 'https://', '/')), uri)
            self.assertNotIn(':', uri.split('/')[0])
            self.assertTrue(s['locations'][0]['logicalLocations'][0]['name'].startswith('http://localhost:8000/'))
            self.assertIn('http://localhost:8000/', s['message']['text'])
        # ruleIndex kurallar listesindeki sirayla tutarli
        kural_idler = [k['id'] for k in run['tool']['driver']['rules']]
        for s in sonuclar:
            self.assertEqual(kural_idler[s['ruleIndex']], s['ruleId'])

    def test_yuksek_risk_error_ve_parametre_mesajda(self):
        rapor = json.loads(json.dumps(ORNEK_RAPOR))
        rapor['site'][0]['alerts'][0]['riskcode'] = '3'
        run = self.m.donustur(rapor)['runs'][0]
        csp = [s for s in run['results'] if s['ruleId'] == 'zap/10038']
        self.assertTrue(all(s['level'] == 'error' for s in csp))
        kural = [k for k in run['tool']['driver']['rules'] if k['id'] == 'zap/10038'][0]
        self.assertEqual(kural['properties']['security-severity'], '8.0')
        xcto = [s for s in run['results'] if s['ruleId'] == 'zap/10021'][0]
        self.assertIn('x-content-type-options', xcto['message']['text'])
        self.assertEqual(xcto['properties']['method'], 'GET')

    def test_parmak_izi_ayni_bulgu_icin_kararli(self):
        a = self.m.donustur(ORNEK_RAPOR)['runs'][0]['results']
        b = self.m.donustur(ORNEK_RAPOR)['runs'][0]['results']
        self.assertEqual([s['partialFingerprints'] for s in a], [s['partialFingerprints'] for s in b])
        self.assertEqual(len({s['partialFingerprints']['zap/instance'] for s in a}), 4)

    def test_konum_yolu_sorgu_ve_kok_icin(self):
        rapor = json.loads(json.dumps(ORNEK_RAPOR))
        rapor['site'][0]['alerts'][1]['instances'][0]['uri'] = 'http://localhost:8000/api/v1/cve/?limit=5&x=1'
        rapor['site'][0]['alerts'][2]['instances'][0]['uri'] = 'http://localhost:8000'
        run = self.m.donustur(rapor)['runs'][0]
        uriler = {s['ruleId']: s['locations'][0]['physicalLocation']['artifactLocation']['uri'] for s in run['results']}
        # sorgu dizesi konuma girmez (ayni uc nokta tek konum), kok "/" icin bos olmayan yol
        self.assertEqual(uriler['zap/10021'], 'dast/api/v1/cve/')
        self.assertEqual(uriler['zap/10015'], 'dast/')

    def test_bos_rapor_gecerli_sarif(self):
        sarif = self.m.donustur({"@version": "2.16.1", "site": []})
        self.assertEqual(sarif['runs'][0]['results'], [])
        self.assertEqual(sarif['runs'][0]['tool']['driver']['rules'], [])

    def test_komut_satiri_dosya_yazar(self):
        with tempfile.TemporaryDirectory() as d:
            girdi = os.path.join(d, 'report_json.json')
            cikti = os.path.join(d, 'zap.sarif')
            with open(girdi, 'w', encoding='utf-8') as f:
                json.dump(ORNEK_RAPOR, f)
            kod = self.m.main([girdi, cikti])
            self.assertEqual(kod, 0)
            with open(cikti, encoding='utf-8') as f:
                sarif = json.load(f)
            self.assertEqual(len(sarif['runs'][0]['results']), 4)

    def test_komut_satiri_eksik_dosyada_hata(self):
        with tempfile.TemporaryDirectory() as d:
            kod = self.m.main([os.path.join(d, 'yok.json'), os.path.join(d, 'out.sarif')])
            self.assertNotEqual(kod, 0)
