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
MARKDOWN_ISARETLERI = set('\\`*_{}[]()<>#+!~|')
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
    """Markdown tablo hucresi, guvenilmeyen metin icin: satir sonu bosluga, Markdown/HTML isaretleri
    ters boluyle kacirilir (fork PR'inin dal adi ya da workflow adi `<img ...>` veya `[..](..)` olarak
    islenmesin), @ anmasi etkisizlestirilir."""
    metin = str(deger if deger is not None else '').replace('\r', ' ').replace('\n', ' ')
    metin = ''.join('\\' + harf if harf in MARKDOWN_ISARETLERI else harf for harf in metin)
    return metin.replace('@', '&#64;')


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
    # Haftalik degisim arac bazinda yalniz sayi olarak: repo herkese acik, Security sekmesini yalniz
    # yazma yetkisi olanlar gorur; kural / dosya yolu / uyari numarasi Issue'ya yazilmaz.
    degisim = {}
    for uyari in acik:
        if pencerede(uyari.get('created_at'), simdi):
            degisim.setdefault(arac(uyari), [0, 0, 0])[0] += 1
    for uyari in kapanan:
        if uyari.get('state') == 'fixed' and pencerede(uyari.get('fixed_at'), simdi):
            degisim.setdefault(arac(uyari), [0, 0, 0])[1] += 1
        elif uyari.get('state') == 'dismissed' and pencerede(uyari.get('dismissed_at'), simdi):
            degisim.setdefault(arac(uyari), [0, 0, 0])[2] += 1
    yeni, duzeltilen, dismiss = (sum(s[i] for s in degisim.values()) for i in range(3))

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
        nedenler.append(f'Bu hafta {yeni} yeni code scanning uyarısı')
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
                 f'- Yeni açılan (hâlâ açık): **{yeni}**',
                 f'- Düzeltilen: **{duzeltilen}** · Dismiss edilen: **{dismiss}**']
    if degisim:
        satirlar += ['', '| Araç | Yeni | Düzeltilen | Dismiss |', '|---|---:|---:|---:|']
        for ad in sorted(degisim):
            satirlar.append(f'| {hucre(ad)} | ' + ' | '.join(str(n) for n in degisim[ad]) + ' |')
    satirlar += ['', f'Ayrıntı (kural, konum): [Security → Code scanning](https://github.com/{repo}/security/code-scanning)'
                 ' — repo herkese açık olduğu için uyarı ayrıntısı bu Issue\'ya yazılmaz; sekmeyi yazma yetkisi olanlar görür.']

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
