"""scripts/guvenlik_ozeti.py: haftalik guvenlik ozeti Issue govdesi (GUVENLIK-PLANI P5-b).

Veritabani gerekmez. Betik Django'ya bagli degildir; importlib ile dosya yolundan yuklenir.
"""
import contextlib
import importlib.util
import io
import json
import os
import tempfile
from datetime import datetime, timezone

from django.test import SimpleTestCase

BETIK = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'guvenlik_ozeti.py')
SIMDI = datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc)


def _yukle():
    spec = importlib.util.spec_from_file_location('guvenlik_ozeti', BETIK)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _uyari(no, arac='CodeQL', sev=None, guv=None, olusma='2026-10-01T00:00:00Z',
           durum='open', kural='py/x', yol='a.py', **ek):
    uyari = {
        'number': no, 'state': durum, 'created_at': olusma,
        'html_url': f'https://github.com/o/r/security/code-scanning/{no}',
        'tool': {'name': arac},
        'rule': {'id': kural, 'severity': sev, 'security_severity_level': guv},
        'most_recent_instance': {'location': {'path': yol}},
    }
    uyari.update(ek)
    return uyari


class GuvenlikOzetiTests(SimpleTestCase):
    def setUp(self):
        self.m = _yukle()

    def _ozet(self, acik=(), kapanan=(), dependabot=(), kosular=()):
        return self.m.ozet(list(acik), list(kapanan),
                           dependabot if isinstance(dependabot, dict) else list(dependabot),
                           list(kosular), 'o/r', SIMDI)

    def test_bos_veri_temiz(self):
        govde = self._ozet()
        self.assertIn('**Durum: ✅ Temiz**', govde)
        self.assertIn('Kırmızı koşu yok.', govde)
        self.assertIn('| **Toplam** | 0 | 0 | 0 | 0 | 0 | 0 | 0 | **0** |', govde)
        self.assertIn('Yeni açılan (hâlâ açık): **0**', govde)
        self.assertIn('| 0 | 0 | 0 | 0 | 0 |', govde)

    def test_arac_severity_tablosu(self):
        govde = self._ozet(acik=[
            _uyari(1, 'OWASP ZAP', guv='medium'),
            _uyari(2, 'OWASP ZAP', guv='low'),
            _uyari(3, 'OWASP ZAP', guv='low'),
            _uyari(4, 'CodeQL', sev='error', guv='high'),   # security_severity_level oncelikli
            _uyari(5, 'CodeQL', sev='warning'),
            _uyari(6, 'Trivy', sev=None),                   # bos -> note
        ])
        self.assertIn('| CodeQL | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 2 |', govde)
        self.assertIn('| OWASP ZAP | 0 | 0 | 1 | 2 | 0 | 0 | 0 | 3 |', govde)
        self.assertIn('| Trivy | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 1 |', govde)
        self.assertIn('| **Toplam** | 0 | 1 | 1 | 2 | 0 | 1 | 1 | **6** |', govde)
        self.assertLess(govde.index('| CodeQL |'), govde.index('| OWASP ZAP |'))
        self.assertIn('**Durum: ⚠️ Dikkat**', govde)
        self.assertIn('1 açık critical/high code scanning uyarısı', govde)

    def test_yedi_gun_siniri(self):
        govde = self._ozet(acik=[
            _uyari(1, olusma='2026-10-09T06:00:00Z'),   # tam 7 gun: dahil
            _uyari(2, olusma='2026-10-09T05:59:59Z'),   # 7 gun + 1 sn: haric
        ])
        self.assertIn('Yeni açılan (hâlâ açık): **1**', govde)
        self.assertIn('| CodeQL | 1 | 0 | 0 |', govde)
        self.assertIn('Bu hafta 1 yeni code scanning uyarısı', govde)

    def test_kapananlar(self):
        govde = self._ozet(kapanan=[
            _uyari(1, durum='fixed', fixed_at='2026-10-12T00:00:00Z'),
            _uyari(2, durum='fixed', fixed_at='2026-09-01T00:00:00Z'),
            _uyari(3, durum='dismissed', dismissed_at='2026-10-15T00:00:00Z'),
            _uyari(4, durum='dismissed', dismissed_at='2026-10-10T00:00:00Z'),
            _uyari(5, durum='dismissed', dismissed_at='2026-08-01T00:00:00Z'),
        ])
        self.assertIn('Düzeltilen: **1** · Dismiss edilen: **2**', govde)
        self.assertIn('| CodeQL | 0 | 1 | 2 |', govde)
        self.assertIn('**Durum: ✅ Temiz**', govde)

    def test_uyari_ayrintisi_yayinlanmaz(self):
        """Repo herkese acik: Security sekmesini yalniz yazma yetkisi olanlar gorur. Issue
        duzeltilmemis bir uyarinin kuralini, dosya yolunu ya da numarasini yayinlamamali."""
        govde = self._ozet(acik=[_uyari(7, olusma='2026-10-15T00:00:00Z', guv='high',
                                        kural='py/sql-injection', yol='news/gizli_yol.py')])
        self.assertNotIn('sql-injection', govde)
        self.assertNotIn('gizli', govde)
        self.assertNotIn('/security/code-scanning/7', govde)
        self.assertIn('https://github.com/o/r/security/code-scanning', govde)

    def test_dependabot_okunamadi_durumu_degistirmez(self):
        govde = self._ozet(dependabot={'okunamadi': True})
        self.assertIn('Okunamadı (token izni)', govde)
        self.assertIn('**Durum: ✅ Temiz**', govde)

    def test_dependabot_critical_dikkat(self):
        govde = self._ozet(dependabot=[
            {'security_advisory': {'severity': 'critical'}},
            {'security_advisory': {'severity': 'low'}},
        ])
        self.assertIn('| 1 | 0 | 0 | 1 | 2 |', govde)
        self.assertIn('**Durum: ⚠️ Dikkat**', govde)
        self.assertIn('1 açık critical/high Dependabot uyarısı', govde)

    def test_kirmizi_kosu(self):
        govde = self._ozet(kosular=[
            {'name': 'CI', 'event': 'push', 'head_branch': 'main', 'created_at': '2026-10-15T10:00:00Z',
             'run_number': 42, 'html_url': 'https://github.com/o/r/actions/runs/1'},
            {'name': 'trivy', 'event': 'schedule', 'head_branch': 'main', 'created_at': '2026-10-01T10:00:00Z',
             'run_number': 7, 'html_url': 'https://github.com/o/r/actions/runs/2'},
        ])
        self.assertIn('| CI | push | main | 2026-10-15 10:00 | [#42](https://github.com/o/r/actions/runs/1) |', govde)
        self.assertNotIn('actions/runs/2', govde)
        self.assertIn('Son 7 günde 1 kırmızı koşu', govde)
        self.assertIn('**Durum: ⚠️ Dikkat**', govde)

    def test_hucre_kacisi(self):
        self.assertEqual(self.m.hucre('a|b\nc @ali'), 'a\\|b c &#64;ali')
        self.assertEqual(self.m.hucre('[x](y) <img> `k` *_~#!\\'),
                         '\\[x\\]\\(y\\) \\<img\\> \\`k\\` \\*\\_\\~\\#\\!\\\\')
        # Fork PR'inin dal adi saldirgan secimidir: Issue'da HTML/baglanti olarak islenmemeli
        govde = self._ozet(kosular=[{'name': 'CI', 'event': 'pull_request', 'head_branch': '<img src=x>',
                                     'created_at': '2026-10-15T10:00:00Z', 'run_number': 1,
                                     'html_url': 'https://github.com/o/r/actions/runs/1'}])
        self.assertNotRegex(govde, r'(?<!\\)<img')   # kacirilmamis etiket yok
        self.assertIn('\\<img src=x\\>', govde)

    def test_baslik(self):
        self.assertEqual(self.m.baslik(SIMDI), 'Haftalık güvenlik özeti — 2026-W42 (2026-10-16)')
        self.assertEqual(self.m.baslik(datetime(2027, 1, 1, 6, tzinfo=timezone.utc)),
                         'Haftalık güvenlik özeti — 2026-W53 (2027-01-01)')

    def test_duzlestir(self):
        self.assertEqual(self.m.duzlestir([[{'n': 1}], [{'n': 2}]]), [{'n': 1}, {'n': 2}])
        self.assertEqual(self.m.duzlestir([{'workflow_runs': [{'id': 1}]}, {'workflow_runs': [{'id': 2}]}],
                                          'workflow_runs'), [{'id': 1}, {'id': 2}])
        self.assertEqual(self.m.duzlestir([{'id': 1}], 'workflow_runs'), [{'id': 1}])
        self.assertEqual(self.m.duzlestir([{'n': 1}]), [{'n': 1}])
        self.assertEqual(self.m.duzlestir(None), [])

    def test_main_dosya_yazar_basligi_basar(self):
        with tempfile.TemporaryDirectory() as dizin:
            def yaz(ad, veri):
                yol = os.path.join(dizin, ad)
                with open(yol, 'w', encoding='utf-8') as dosya:
                    json.dump(veri, dosya)
                return yol

            cikti = os.path.join(dizin, 'ozet.md')
            argv = [
                '--acik', yaz('acik.json', [[_uyari(1, 'OWASP ZAP', guv='low')]]),
                '--kapanan', yaz('kapanan.json', [[], []]),
                '--dependabot', yaz('dependabot.json', {'okunamadi': True}),
                '--kosular', yaz('kosular.json', [{'total_count': 0, 'workflow_runs': []}]),
                '--repo', 'o/r', '--cikti', cikti, '--simdi', '2026-10-16T06:00:00Z',
            ]
            tampon = io.StringIO()
            with contextlib.redirect_stdout(tampon):
                kod = self.m.main(argv)
            self.assertEqual(kod, 0)
            self.assertEqual(tampon.getvalue(), 'Haftalık güvenlik özeti — 2026-W42 (2026-10-16)\n')
            with open(cikti, encoding='utf-8') as dosya:
                govde = dosya.read()
            self.assertIn('| OWASP ZAP | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 1 |', govde)
            self.assertIn('Okunamadı (token izni)', govde)
