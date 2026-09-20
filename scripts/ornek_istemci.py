#!/usr/bin/env python3
"""CyberNews /api/v1/ delta senkron ornegi (ADR-0003, adim A5).

Alti bolumu imlecli delta ile bastan sona ceker ve yerel bir depoya UPSERT eder.
Yalnizca standart kutuphane kullanir; tuketicinin pip ile bir sey kurmasi
gerekmez.

Kullanim:

    export CYBERNEWS_TOKEN=<Django admin'den uretilen token>
    export CYBERNEWS_URL=http://localhost:8000      # varsayilan
    python scripts/ornek_istemci.py

Imlecler bu dosyanin yanindaki ornek_istemci_durum.json icinde saklanir; script
ikinci kez calistirildiginda kaldigi yerden devam eder ve yalnizca degisenleri
ceker.

Bu ornek kayitlari bellekte tutar. Gercek bir tuketici ayni upsert anahtarini
kendi veritabaninda benzersiz indeks olarak tanimlar.
"""
import json
import os
import pathlib
import urllib.error
import urllib.request

TABAN = os.environ.get('CYBERNEWS_URL', 'http://localhost:8000').rstrip('/')
TOKEN = os.environ.get('CYBERNEWS_TOKEN', '')
DURUM_DOSYASI = pathlib.Path(__file__).with_name('ornek_istemci_durum.json')

# UPSERT ANAHTARI bolume gore degisir ve `id` ASLA kullanilmaz: `id` kalici
# degildir (ADR-0005), saklama penceresi disina dusen bir kayit silinip yeni bir
# id ile geri gelebilir. CVE'de cve_id, diger bes bolumde link kararlidir --
# yazma yolu da (news/tasks.py) ayni anahtarla update_or_create yapar.
UPSERT_ANAHTARLARI = {
    'cve': 'cve_id',
    'news': 'link',
    'kubernetes': 'link',
    'sre': 'link',
    'devtools': 'link',
    'ai': 'link',
}


def cagir(yol):
    """Token ile GET yapar. Hata sozlesmesi: {"error": {"code", "message"}}."""
    istek = urllib.request.Request(f'{TABAN}{yol}',
                                   headers={'Authorization': f'Token {TOKEN}'})
    try:
        with urllib.request.urlopen(istek, timeout=60) as yanit:
            return json.load(yanit)
    except urllib.error.HTTPError as hata:
        # Tanimli uc noktalar {"error": {"code", "message"}} dondurur. Hic rotasi
        # olmayan bir yol (ornegin /api/v1/k8s/ -- v1'de bolum adi 'kubernetes')
        # DRF'e ulasmadan Django'nun duz HTML 404'unu dondurur; o yuzden govde
        # JSON varsayilmaz.
        ham = hata.read()
        try:
            govde = json.loads(ham).get('error', {})
            ayrinti = f'{govde.get("code", "?")}: {govde.get("message", "")}'
        except (ValueError, AttributeError):
            ayrinti = f'JSON olmayan yanit ({hata.headers.get("Content-Type", "?")})'
        raise SystemExit(f'{yol} -> HTTP {hata.code} {ayrinti}')


def baslik(kayit):
    """Ceviri henuz hazir degilse Ingilizceye duser (ADR-0003 bolum 7)."""
    return kayit['title']['tr'] or kayit['title']['original']


def senkronize_et(bolum, imlec, depo):
    """Bir bolumu imlecten sonuna kadar ceker ve yeni imleci dondurur."""
    anahtar = UPSERT_ANAHTARLARI[bolum]
    while True:
        sorgu = '?limit=200' + (f'&since_cursor={imlec}' if imlec else '')
        sayfa = cagir(f'/api/v1/{bolum}/{sorgu}')
        for kayit in sayfa['results']:
            # UPSERT: ayni anahtar yeniden gelirse ustune yazilir, yeni satir
            # acilmaz. Salt insert cift kayit uretir -- `updated_at` icerik
            # degismese de ilerledigi icin ayni kayit tekrar akisa duser.
            depo[(bolum, kayit[anahtar])] = kayit
        # Imlec opaktir: icini acma, sakla ve oldugu gibi geri gonder.
        imlec = sayfa['next_cursor']
        if not sayfa['has_more']:
            return imlec


def main():
    if not TOKEN:
        raise SystemExit('CYBERNEWS_TOKEN tanimli degil.')

    durum = json.loads(DURUM_DOSYASI.read_text('utf-8')) if DURUM_DOSYASI.exists() else {}
    depo = {}

    for bolum in UPSERT_ANAHTARLARI:
        durum[bolum] = senkronize_et(bolum, durum.get(bolum), depo)
        kayitlar = [k for (b, _), k in depo.items() if b == bolum]
        ornek = (baslik(kayitlar[-1]) or '-')[:60] if kayitlar else '-'
        print(f'{bolum:12} degisen={len(kayitlar):4}  son: {ornek}')

    # Imlecler yalnizca tum bolumler basariyla bittiginde yazilir: yarida kesilen
    # bir calisma eski imleci korur ve bir sonraki turda tekrar dener.
    DURUM_DOSYASI.write_text(json.dumps(durum, indent=2), 'utf-8')
    print(f'\n{len(depo)} kayit upsert edildi; imlecler {DURUM_DOSYASI.name} icinde.')


if __name__ == '__main__':
    main()
