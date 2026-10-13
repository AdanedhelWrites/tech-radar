# P5-b Haftalık Güvenlik Özeti Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Her Cuma Security + Actions verisinden araç × severity tablolu bir GitHub Issue açan, bir öncekini kapatan workflow.

**Architecture:** Workflow (`.github/workflows/guvenlik-ozeti.yml`) yalnız `gh api --paginate --slurp` ile JSON çeker ve Issue açar/kapatır. Biçimleme saf bir betikte (`scripts/guvenlik_ozeti.py`, stdlib, ağ yok); Django test koşucusu altında `SimpleTestCase` ile birim testlidir (`test_zap_sarif.py` kalıbı).

**Tech Stack:** Python 3.11+ stdlib, GitHub Actions, `gh` CLI, `jq`.

**Spec:** `docs/superpowers/specs/2026-10-13-p5b-haftalik-guvenlik-ozeti-design.md`

## Global Constraints

- Zamanlama: `cron: "0 6 * * 5"` + `workflow_dispatch`.
- İzinler: üst düzey `permissions: {}`; iş düzeyinde `contents: read`, `issues: write`, `security-events: read`, `actions: read`.
- Action SHA'ları: `step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 # v2.21.1`, `actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1`; `persist-credentials: false`.
- `${{ }}` ifadeleri `run` içine gömülmez; `env` üzerinden geçer.
- Etiket: `guvenlik-ozeti`. Başlık: `Haftalık güvenlik özeti — YYYY-Www (YYYY-MM-DD)`.
- Pencere: `simdi - 7 gün <= zaman <= simdi`. Yeni uyarı listesi tavanı 20.
- Severity sütunları sabit: `critical, high, medium, low, error, warning, note`; boş/`none`/bilinmeyen → `note`.
- `main` korumalı: dal + PR + 5 zorunlu check; doğrudan push yok.

## Review Focus

1. Runner'daki `gh` `--slurp` desteklemezse veri adımı düşer → ilk `workflow_dispatch` koşusu doğrular (Task 3).
2. `GITHUB_TOKEN` Dependabot uyarılarını okuyamazsa hat yeşil kalmalı, Issue'da not olmalı → Task 1 testi (`okunamadi`) + Task 3 gözlemi.
3. Düz liste (slurp'süz) girdi de doğru sayılmalı → Task 1 `test_duzlestir`.
4. Uyarı yolunda `|` / `@` tabloyu bozmamalı, kimseyi anmamalı → Task 1 `test_hucre_kacisi`.
5. Yıl sınırında ISO hafta (`2027-01-01` → `2026-W53`) → Task 1 `test_baslik`.

---

### Task 1: Biçimleme betiği ve testleri

**Files:**
- Create: `news/tests/test_guvenlik_ozeti.py`
- Create: `scripts/guvenlik_ozeti.py`

**Interfaces:**
- Produces: `ozet(acik, kapanan, dependabot, kosular, repo, simdi) -> str`, `baslik(simdi) -> str`, `duzlestir(veri, anahtar=None) -> list`, `hucre(deger) -> str`, `main(argv=None) -> int` (CLI: `--acik --kapanan --dependabot --kosular --repo --cikti [--simdi]`; gövdeyi `--cikti`'ya yazar, başlığı stdout'a basar).

- [ ] **Step 1: Testleri yaz** — `news/tests/test_guvenlik_ozeti.py`:

```python
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
        self.assertIn('[#1](', govde)
        self.assertNotIn('[#2](', govde)
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
        self.assertIn('**Durum: ✅ Temiz**', govde)

    def test_yeni_liste_tavani(self):
        govde = self._ozet(acik=[_uyari(n, olusma='2026-10-15T00:00:00Z') for n in range(1, 26)])
        self.assertEqual(govde.count('/security/code-scanning/'), 20)
        self.assertIn('… ve 5 uyarı daha', govde)

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
        govde = self._ozet(acik=[_uyari(1, olusma='2026-10-15T00:00:00Z', yol='x|y.py')])
        self.assertIn('| x\\|y.py |', govde)

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
```

- [ ] **Step 2: Kırmızıyı gör**

Run (repo kökünden, Git Bash):
`MSYS_NO_PATHCONV=1 docker run --rm -e DEBUG=True -e SECRET_KEY=test-only -v "$(pwd -W):/app" -w /app --entrypoint python teknoloji-haberleri-api:latest manage.py test news.tests.test_guvenlik_ozeti --noinput`
Expected: 12 test ERROR, `FileNotFoundError` (betik yok).

- [ ] **Step 3: Betiği yaz** — `scripts/guvenlik_ozeti.py`:

```python
#!/usr/bin/env python3
"""Haftalik guvenlik ozeti: GitHub API JSON'larindan Issue govdesi uretir (GUVENLIK-PLANI P5-b).

    scripts/guvenlik_ozeti.py --acik code_acik.json --kapanan code_kapanan.json \\
        --dependabot dependabot.json --kosular kosular.json \\
        --repo OWNER/NAME --cikti ozet.md [--simdi 2026-10-16T06:00:00Z]

Yalniz standart kutuphane, ag yok: veriyi .github/workflows/guvenlik-ozeti.yml `gh api --paginate
--slurp` ile ceker, bu betik yalniz bicimler. Govde --cikti dosyasina yazilir, Issue basligi stdout'a
basilir. Haftalik degisim icin durum saklanmaz: created_at / fixed_at / dismissed_at son 7 gunluk
pencereyle karsilastirilir, onceki Issue govdesi ayristirilmaz. Dependabot GITHUB_TOKEN ile
okunamazsa workflow {"okunamadi": true} yazar; Issue'ya not duser, durum degismez.
Spec: docs/superpowers/specs/2026-10-13-p5b-haftalik-guvenlik-ozeti-design.md
"""
import argparse
import json
import sys
from datetime import datetime, timedelta, timezone

PENCERE = timedelta(days=7)
SUTUNLAR = ('critical', 'high', 'medium', 'low', 'error', 'warning', 'note')
DEPENDABOT_SUTUNLAR = ('critical', 'high', 'medium', 'low')
YENI_TAVAN = 20
PLAN = 'docs/GUVENLIK-PLANI.md'


def zaman(deger):
    """GitHub ISO 8601 zamani (Z sonekli) -> UTC datetime; bos ise None."""
    if not deger:
        return None
    return datetime.fromisoformat(deger.replace('Z', '+00:00')).astimezone(timezone.utc)


def duzlestir(veri, anahtar=None):
    """`gh api --paginate --slurp` ciktisi (sayfa listesi) -> tek oge listesi.

    anahtar verilirse sayfa {anahtar: [...]} nesnesi olabilir (actions/runs: workflow_runs).
    Duz liste de kabul edilir.
    """
    if veri is None:
        return []
    if isinstance(veri, dict):
        veri = [veri]
    ogeler = []
    for sayfa in veri:
        if anahtar and isinstance(sayfa, dict) and anahtar in sayfa:
            ogeler.extend(sayfa[anahtar] or [])
        elif isinstance(sayfa, list):
            ogeler.extend(sayfa)
        else:
            ogeler.append(sayfa)
    return ogeler


def hucre(deger):
    """Markdown tablo hucresi: | kacar, satir sonunu bosluga cevirir, @ anmayi etkisizlestirir."""
    metin = str(deger if deger is not None else '')
    return metin.replace('\r', ' ').replace('\n', ' ').replace('|', '\\|').replace('@', '&#64;')


def severity(uyari):
    kural = uyari.get('rule') or {}
    deger = (kural.get('security_severity_level') or kural.get('severity') or '').lower()
    return deger if deger in SUTUNLAR else 'note'


def arac(uyari):
    return (uyari.get('tool') or {}).get('name') or 'bilinmeyen'


def pencerede(deger, simdi):
    an = zaman(deger)
    return an is not None and simdi - PENCERE <= an <= simdi


def baslik(simdi):
    yil, hafta, _ = simdi.isocalendar()
    return f'Haftalık güvenlik özeti — {yil}-W{hafta:02d} ({simdi.date().isoformat()})'


def ozet(acik, kapanan, dependabot, kosular, repo, simdi):
    """Issue govdesi (Markdown).

    acik/kapanan: code scanning uyarilari; dependabot: uyari listesi ya da {'okunamadi': True};
    kosular: basarisiz workflow kosulari.
    """
    kirmizi = sorted((k for k in kosular if pencerede(k.get('created_at'), simdi)),
                     key=lambda k: k.get('created_at') or '')

    tablo = {}
    for uyari in acik:
        satir = tablo.setdefault(arac(uyari), dict.fromkeys(SUTUNLAR, 0))
        satir[severity(uyari)] += 1
    yeni = sorted((u for u in acik if pencerede(u.get('created_at'), simdi)),
                  key=lambda u: (SUTUNLAR.index(severity(u)), arac(u), u.get('number') or 0))
    duzeltilen = sum(1 for u in kapanan
                     if u.get('state') == 'fixed' and pencerede(u.get('fixed_at'), simdi))
    dismiss = sum(1 for u in kapanan
                  if u.get('state') == 'dismissed' and pencerede(u.get('dismissed_at'), simdi))

    dependabot_okunamadi = isinstance(dependabot, dict) and bool(dependabot.get('okunamadi'))
    dep = dict.fromkeys(DEPENDABOT_SUTUNLAR, 0)
    if not dependabot_okunamadi:
        for uyari in dependabot:
            sev = ((uyari.get('security_advisory') or {}).get('severity') or '').lower()
            if sev in dep:
                dep[sev] += 1

    nedenler = []
    if kirmizi:
        nedenler.append(f'Son 7 günde {len(kirmizi)} kırmızı koşu')
    kritik = sum(s['critical'] + s['high'] for s in tablo.values())
    if kritik:
        nedenler.append(f'{kritik} açık critical/high code scanning uyarısı')
    if yeni:
        nedenler.append(f'Bu hafta {len(yeni)} yeni code scanning uyarısı')
    if dep['critical'] + dep['high']:
        nedenler.append(f"{dep['critical'] + dep['high']} açık critical/high Dependabot uyarısı")

    baslangic = simdi - PENCERE
    satirlar = [f'Dönem: {baslangic:%Y-%m-%d %H:%M} → {simdi:%Y-%m-%d %H:%M} (UTC) · Depo: `{repo}`', '']
    if nedenler:
        satirlar.append('**Durum: ⚠️ Dikkat**')
        satirlar += [f'- {neden}' for neden in nedenler]
    else:
        satirlar.append('**Durum: ✅ Temiz**')

    satirlar += ['', '## Kırmızı koşular (son 7 gün)', '']
    if kirmizi:
        satirlar += ['| Workflow | Olay | Dal | Tarih | Koşu |', '|---|---|---|---|---|']
        for k in kirmizi:
            tarih = (k.get('created_at') or '')[:16].replace('T', ' ')
            satirlar.append(f"| {hucre(k.get('name'))} | {hucre(k.get('event'))} | {hucre(k.get('head_branch'))} "
                            f"| {hucre(tarih)} | [#{k.get('run_number')}]({k.get('html_url')}) |")
    else:
        satirlar.append('Kırmızı koşu yok.')

    satirlar += ['', '## Code scanning — açık uyarılar', '',
                 '| Araç | ' + ' | '.join(SUTUNLAR) + ' | Toplam |',
                 '|---' + '|---:' * (len(SUTUNLAR) + 1) + '|']
    for ad in sorted(tablo):
        s = tablo[ad]
        satirlar.append(f'| {hucre(ad)} | ' + ' | '.join(str(s[c]) for c in SUTUNLAR) + f' | {sum(s.values())} |')
    toplam = {c: sum(s[c] for s in tablo.values()) for c in SUTUNLAR}
    satirlar.append('| **Toplam** | ' + ' | '.join(str(toplam[c]) for c in SUTUNLAR)
                    + f' | **{sum(toplam.values())}** |')

    satirlar += ['', '## Bu hafta', '',
                 f'- Yeni açılan (hâlâ açık): **{len(yeni)}**',
                 f'- Düzeltilen: **{duzeltilen}** · Dismiss edilen: **{dismiss}**']
    if yeni:
        satirlar += ['', '| Araç | Severity | Kural | Konum | Uyarı |', '|---|---|---|---|---|']
        for u in yeni[:YENI_TAVAN]:
            konum = ((u.get('most_recent_instance') or {}).get('location') or {}).get('path')
            satirlar.append(f"| {hucre(arac(u))} | {severity(u)} | {hucre((u.get('rule') or {}).get('id'))} "
                            f"| {hucre(konum)} | [#{u.get('number')}]({u.get('html_url')}) |")
        if len(yeni) > YENI_TAVAN:
            satirlar += ['', f'… ve {len(yeni) - YENI_TAVAN} uyarı daha (Security → Code scanning).']

    satirlar += ['', '## Dependabot — açık uyarılar', '']
    if dependabot_okunamadi:
        satirlar.append('Okunamadı (token izni). Security → Dependabot sekmesine elle bakın.')
    else:
        satirlar += ['| ' + ' | '.join(DEPENDABOT_SUTUNLAR) + ' | Toplam |',
                     '|' + '---:|' * (len(DEPENDABOT_SUTUNLAR) + 1),
                     '| ' + ' | '.join(str(dep[c]) for c in DEPENDABOT_SUTUNLAR) + f' | {sum(dep.values())} |']

    satirlar += ['', '## Ne yapmalı', '',
                 '1. Kırmızı koşu varsa önce onu çöz: rapor hattı bozuksa bulgu listesi eksiktir.',
                 '2. critical/high uyarıları GUVENLIK-PLANI P4 listesine ekle.',
                 '3. Diğer bulguları Security → Code scanning\'de düzelt ya da gerekçeyle dismiss et.',
                 '',
                 f'Rutin: [{PLAN}](https://github.com/{repo}/blob/main/{PLAN}) §2. '
                 'Bu Issue `guvenlik-ozeti.yml` tarafından açıldı; bir sonraki özet açılınca kapanır.']
    return '\n'.join(satirlar) + '\n'


def _oku(yol):
    with open(yol, encoding='utf-8') as dosya:
        return json.load(dosya)


def main(argv=None):
    ayrac = argparse.ArgumentParser(description='Haftalik guvenlik ozeti (GUVENLIK-PLANI P5-b)')
    for ad in ('--acik', '--kapanan', '--dependabot', '--kosular', '--repo', '--cikti'):
        ayrac.add_argument(ad, required=True)
    ayrac.add_argument('--simdi', help='ISO 8601 UTC; verilmezse su an')
    arg = ayrac.parse_args(argv)

    simdi = zaman(arg.simdi) if arg.simdi else datetime.now(timezone.utc)
    dependabot = _oku(arg.dependabot)
    if not (isinstance(dependabot, dict) and dependabot.get('okunamadi')):
        dependabot = duzlestir(dependabot)
    govde = ozet(duzlestir(_oku(arg.acik)), duzlestir(_oku(arg.kapanan)), dependabot,
                 duzlestir(_oku(arg.kosular), 'workflow_runs'), arg.repo, simdi)
    with open(arg.cikti, 'w', encoding='utf-8') as dosya:
        dosya.write(govde)
    print(baslik(simdi))
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Yeşili gör** — Step 2 komutu. Expected: `Ran 12 tests` / `OK`.

- [ ] **Step 5: Commit**

```bash
git add scripts/guvenlik_ozeti.py news/tests/test_guvenlik_ozeti.py
git commit -m "feat(guvenlik): haftalik guvenlik ozeti bicimleyicisi (P5-b)"
```

### Task 2: Workflow ve belge

**Files:**
- Create: `.github/workflows/guvenlik-ozeti.yml`
- Modify: `docs/GUVENLIK-PLANI.md` (başlık notu, §1 tablo, §2 rutin, §4 P5-b, §5 geçmiş)

**Interfaces:**
- Consumes: Task 1 CLI (`python3 scripts/guvenlik_ozeti.py ... > baslik.txt`).

- [ ] **Step 1: Workflow'u yaz** — `.github/workflows/guvenlik-ozeti.yml`:

```yaml
# Haftalik guvenlik ozeti (GUVENLIK-PLANI P5-b): Security + Actions verisinden her Cuma bir GitHub
# Issue acar (etiket guvenlik-ozeti), oncekini "Yerine #N" yorumuyla kapatir.
# Mod: RAPOR. Hat yalniz rapor uretilemezse kirmizidir: code scanning / kosular okunamadi, Issue
# acilamadi ya da onceki kapatilamadi. Dependabot GITHUB_TOKEN ile okunamazsa Issue'ya not duser,
# hat yesil kalir. Bicimleme scripts/guvenlik_ozeti.py'de (yalniz stdlib, birim testli).
# Spec: docs/superpowers/specs/2026-10-13-p5b-haftalik-guvenlik-ozeti-design.md

name: Haftalik guvenlik ozeti

on:
  schedule:
    - cron: "0 6 * * 5"   # Cuma 06:00 UTC: haftalik taramalarin sonuncusu zizmor (Persembe)
  workflow_dispatch:

permissions: {}

concurrency:
  group: ${{ github.workflow }}
  cancel-in-progress: false

jobs:
  ozet:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read          # checkout (betik)
      issues: write           # etiket, Issue ac, oncekini kapat
      security-events: read   # code scanning uyarilari
      actions: read           # basarisiz workflow kosulari
    steps:
      - name: Harden runner
        uses: step-security/harden-runner@e14015d583714f6e62063499dc959a02595150a1 # v2.21.1
        with:
          egress-policy: audit

      - name: Checkout
        uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
        with:
          persist-credentials: false

      - name: Veriyi cek
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          gh api --paginate --slurp "repos/${REPO}/code-scanning/alerts?state=open&per_page=100" > code_acik.json
          gh api --paginate --slurp "repos/${REPO}/code-scanning/alerts?state=fixed&per_page=100" > code_fixed.json
          gh api --paginate --slurp "repos/${REPO}/code-scanning/alerts?state=dismissed&per_page=100" > code_dismissed.json
          jq -s 'add' code_fixed.json code_dismissed.json > code_kapanan.json
          # API gun cozunurlugunde suzer; kesin 7 gunluk pencere betikte
          tarih="$(date -u -d '8 days ago' +%Y-%m-%d)"
          gh api --paginate --slurp "repos/${REPO}/actions/runs?status=failure&created=%3E%3D${tarih}&per_page=100" > kosular.json
          if ! gh api --paginate --slurp "repos/${REPO}/dependabot/alerts?state=open&per_page=100" > dependabot.json 2> dependabot.err; then
            echo "::warning::Dependabot uyarilari okunamadi: $(head -c 300 dependabot.err)"
            echo '{"okunamadi": true}' > dependabot.json
          fi

      - name: Ozeti uret
        env:
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          python3 scripts/guvenlik_ozeti.py --acik code_acik.json --kapanan code_kapanan.json \
            --dependabot dependabot.json --kosular kosular.json --repo "${REPO}" --cikti ozet.md > baslik.txt
          cat baslik.txt

      - name: Issue ac, oncekini kapat
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
        run: |
          set -euo pipefail
          gh label create guvenlik-ozeti --repo "${REPO}" --color 5319E7 \
            --description "Haftalik guvenlik ozeti (guvenlik-ozeti.yml)" --force
          url="$(gh issue create --repo "${REPO}" --title "$(cat baslik.txt)" --body-file ozet.md --label guvenlik-ozeti)"
          yeni="${url##*/}"
          echo "Acildi: ${url}"
          for no in $(gh issue list --repo "${REPO}" --label guvenlik-ozeti --state open --limit 50 --json number --jq '.[].number'); do
            if [ "${no}" != "${yeni}" ]; then
              gh issue close "${no}" --repo "${REPO}" --comment "Yerine #${yeni} açıldı."
            fi
          done
          echo "### Haftalik guvenlik ozeti: ${url}" >> "${GITHUB_STEP_SUMMARY}"
```

- [ ] **Step 2: YAML sözdizimini doğrula**

Run: `MSYS_NO_PATHCONV=1 docker run --rm -v "$(pwd -W):/app" -w /app --entrypoint python teknoloji-haberleri-api:latest -c "import yaml;d=yaml.safe_load(open('.github/workflows/guvenlik-ozeti.yml'));print(sorted(d['jobs']['ozet']['permissions']))"`
Expected: `['actions', 'contents', 'issues', 'security-events']`

- [ ] **Step 3: Workflow adımlarını yerelde sına** — gerçek veriyle, Issue açmadan:

```bash
REPO=AdanedhelWrites/tech-radar; d="$(mktemp -d)"
gh api --paginate --slurp "repos/$REPO/code-scanning/alerts?state=open&per_page=100" > "$d/acik.json"
gh api --paginate --slurp "repos/$REPO/code-scanning/alerts?state=fixed&per_page=100" > "$d/f.json"
gh api --paginate --slurp "repos/$REPO/code-scanning/alerts?state=dismissed&per_page=100" > "$d/x.json"
jq -s 'add' "$d/f.json" "$d/x.json" > "$d/kapanan.json"
gh api --paginate --slurp "repos/$REPO/actions/runs?status=failure&created=%3E%3D$(date -u -d '8 days ago' +%Y-%m-%d)&per_page=100" > "$d/kosular.json"
echo '{"okunamadi": true}' > "$d/dep.json"
python scripts/guvenlik_ozeti.py --acik "$d/acik.json" --kapanan "$d/kapanan.json" --dependabot "$d/dep.json" --kosular "$d/kosular.json" --repo "$REPO" --cikti "$d/ozet.md"
```
Expected: başlık satırı; `ozet.md`'de OWASP ZAP satırı (2026-10-13 itibarıyla 4 medium / 11 low).

- [ ] **Step 4: GUVENLIK-PLANI'yı güncelle**
  - Başlık notu: `> Son güncelleme: 2026-10-13 (P5-b haftalık özet Issue'su; kalan P5-c). ...`
  - §1 tabloya `OpenSSF Scorecard` satırından sonra:
    `| \`Haftalik guvenlik ozeti\` | Cuma 06:00 UTC, elle | Rapor (Issue, etiket \`guvenlik-ozeti\`) | Özet üretilemedi: code scanning / koşular okunamadı, Issue açılamadı ya da önceki kapatılamadı |`
  - §2 "Haftalık kontrol rutini" başlığının altına: `Her Cuma bu rutinin özeti \`guvenlik-ozeti\` etiketli bir Issue olarak açılır (önceki kapanır); önce ona bak, ayrıntı gerekirse aşağıdaki adımlara in.`
  - §4 P5-b: `- [x] Haftalık güvenlik özeti: ... — \`.github/workflows/guvenlik-ozeti.yml\` + \`scripts/guvenlik_ozeti.py\` (12 test), PR #<no> (2026-10-13)`
  - §5: `- **2026-10-13:** P5-b: haftalık güvenlik özeti Issue'su (Cuma 06:00 UTC; araç × severity, kırmızı koşular, haftalık yeni/kapanan, Dependabot).`

- [ ] **Step 5: Tam kapı** — geçici PostgreSQL 16.15 + Redis ile `manage.py check`, `makemigrations --check --dry-run`, `manage.py test --noinput`. Expected: önceki 477 + 12 = **489 test OK**.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/guvenlik-ozeti.yml docs/GUVENLIK-PLANI.md docs/superpowers/plans/2026-10-13-p5b-haftalik-guvenlik-ozeti.md
git commit -m "feat(guvenlik): haftalik guvenlik ozeti workflow'u (P5-b)"
```

### Task 3: PR, birleştirme, ilk koşu

- [ ] **Step 1:** Staged gitleaks (`git diff origin/main... | docker run --rm -i zricethezav/gitleaks:v8.30.1 stdin --no-banner`) → `no leaks found`.
- [ ] **Step 2:** `git push -u origin feat/p5b-guvenlik-ozeti`; `MSYS_NO_PATHCONV=1 gh pr create --repo AdanedhelWrites/tech-radar ...`.
- [ ] **Step 3:** 5 zorunlu check yeşil → merge (`gh pr merge <no> --merge --delete-branch`).
- [ ] **Step 4:** `MSYS_NO_PATHCONV=1 gh workflow run guvenlik-ozeti.yml --repo AdanedhelWrites/tech-radar` → koşu yeşil; açılan Issue'da tablo, Dependabot bölümü (okundu mu / "okunamadı" mı) kontrol edilir; sonuç kullanıcıya bildirilir.
- [ ] **Step 5:** İkinci kez tetikle → ikinci Issue açılır, birincisi "Yerine #N açıldı." yorumuyla kapanır. (Kapatma yolunu bir kez canlı doğrular; test Issue'ları kapalı arşivde kalır.)

## Plan Değişikliği (2026-10-13, uygulama sırasında)

Task 1 commit'inden sonra otomatik güvenlik incelemesi iki geçerli bulgu verdi (repo herkese açık); spec §4a.
Task 1'deki kod blokları bu bölümle **geçersizdir**; bağlayıcı olan repodaki `scripts/guvenlik_ozeti.py` ve testleridir.

- "Bu hafta" bölümündeki uyarı ayrıntı tablosu (kural | konum | bağlantı, 20 satır tavanı, `YENI_TAVAN`) kaldırıldı;
  yerine `Araç | Yeni | Düzeltilen | Dismiss` sayı tablosu ve Security → Code scanning bağlantısı geldi.
- `hucre()` artık ``\ ` * _ { } [ ] ( ) < > # + ! ~ |`` işaretlerini ters bölüyle kaçırır (`MARKDOWN_ISARETLERI`).
- Testler: `test_yeni_liste_tavani` → `test_uyari_ayrintisi_yayinlanmaz`; `test_yedi_gun_siniri` ve
  `test_kapananlar` araç tablosu satırını, `test_hucre_kacisi` genişletilmiş kaçışı ve fork dal adı `<img src=x>`
  durumunu doğrular. Test sayısı değişmedi (12).
