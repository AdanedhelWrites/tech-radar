"""CVE baslik ozeti (uctan uca test bulgusu 7, 2026-10-16).

Scraper'lar cogu kayda "CVE-x - Güvenlik Açığı" sablon basligi yazar (10-22: 8076/8812). CWE kayitlarin
%9'unda var, etkilenen urun hicbirinde yok; baslik bu yuzden aciklamanin ilk cumlesinden turetilir.
API katmaninda uygulanir: saklanan veri degismez, ceviri (LibreTranslate -> Gemini) iyilestikce baslik da
iyilesir, ek ceviri butcesi harcanmaz.
"""
import re

BASLIK_MAX_KARAKTER = 110

_SABLON = re.compile(r'^(?P<id>CVE-\d{4}-\d+) - (?:Güvenlik Açığı|Aktif Sömürülen Zafiyet)$')

# Linux CNA kalibi: "In the Linux kernel, the following vulnerability has been resolved: <alt sistem>: ..."
# Ceviride bircok bicim alir (cekirdeginde/çekirdeğinde, asagidaki/şu, zaafiyet/kırılganlık, cozuldu/giderildi).
_LINUX = re.compile(
    r'^\s*(?:Linux [çc]ekirde[ğg]inde,?\s+(?:a[şs]a[ğg][ıi]daki|[şs]u)\s+[^:\n]{1,40}'
    r'|In the Linux kernel, the following vulnerability has been resolved)\s*:\s*', re.I)

# Tanim cumlesi: "Electron is a framework for ..." -> urun adi; asil bilgi ikinci cumlede
_TANIM = re.compile(r'^(?P<urun>[^.,:;\n]{2,50}?),? (?:is|are) (?:an?|the) ')

# Cumle siniri: noktalama + bosluk + buyuk harf/rakam/tirnak (surum noktalari "0.11.6" bolunmez); bos satir
# (paragraf) da sinirdir. Tek satir sonu sinir degildir: NVD/GHSA metinleri cumle ortasinda satir kirar.
_CUMLE_SONU = re.compile(r'(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ0-9"\'(])|\n\s*\n')


def _cumleler(metin: str):
    return [c.strip() for c in _CUMLE_SONU.split(metin or '') if c.strip()]


def _kisalt(metin: str) -> str:
    metin = ' '.join(metin.split()).rstrip(' .;:,')
    if len(metin) <= BASLIK_MAX_KARAKTER:
        return metin
    kesim = metin.rfind(' ', 0, BASLIK_MAX_KARAKTER - 1)
    return metin[:kesim if kesim > 0 else BASLIK_MAX_KARAKTER - 1].rstrip(' .;:,') + '…'


# 2026-11-04'e kadar GitHub Advisory scraper'i ozeti 80 karakterde kesiyordu ("... via Dual-Header Inco",
# 877 kayit). Tam ozet saklanmadigi icin geri getirilemez; kesik kelime atilip ucuna "…" konur. Ozeti tam
# 80 karakter olup tam kelimeyle biten nadir bir baslik da "…" alabilir; bu bedel kabul edildi.
ESKI_GHSA_KESIM = 80


def _eski_kesik_baslik(cve_id: str, baslik: str) -> str:
    onek = f'{cve_id} - '
    ozet = (baslik or '')[len(onek):] if (baslik or '').startswith(onek) else ''
    if len(ozet) != ESKI_GHSA_KESIM or ozet[-1] in '.!?)':
        return baslik
    kesim = ozet.rfind(' ')
    return f"{onek}{ozet[:kesim].rstrip(' .;:,-') if kesim > 0 else ozet}…"


def baslik_ozeti(cve_id: str, baslik: str) -> str:
    """Cevrilecek baslik ozeti: GitHub Advisory ozeti ya da CISA KEV zafiyet adi ("CVE-x - <ozet>").
    Sablon ("Güvenlik Açığı" / "Aktif Sömürülen Zafiyet") ya da onek tasimayan baslikta ''."""
    baslik = (baslik or '').strip()
    onek = f'{cve_id} - '
    if not baslik.startswith(onek) or _SABLON.match(baslik):
        return ''
    return baslik[len(onek):].strip()


_ONEK = re.compile(r'^\s*CVE-\d{4}-\d+\s*[-–—:]?\s*', re.I)


def onekli_baslik(cve_id: str, ceviri: str) -> str:
    """Cevrilmis ozete "CVE-x - " onekini koyar. Ceviri onekle geldiyse (model onegi tekrarlayabilir, ayiraci
    '–' ya da ':' yapabilir; LibreTranslate yolu orijinal basligi aynen verir) once o atilir. Bos ceviride ''."""
    ozet = (ceviri or '').strip()
    if ozet.upper().startswith(cve_id.upper()):
        ozet = _ONEK.sub('', ozet, count=1).strip()
    return f'{cve_id} - {ozet}' if ozet else ''



def cve_basligi(cve_id: str, baslik: str, tr_aciklama: str, orijinal_aciklama: str) -> str:
    """Sablon baslik ise aciklamadan ozet baslik dondurur; eski kesik GHSA basligini kelime sinirinda
    bitirir; degilse basligi aynen dondurur."""
    eslesme = _SABLON.match((baslik or '').strip())
    aciklama = (tr_aciklama or '').strip() or (orijinal_aciklama or '').strip()
    if not eslesme:
        return _eski_kesik_baslik(cve_id, baslik)
    if not aciklama:
        return baslik

    linux = _LINUX.match(aciklama)
    if linux:
        cumleler = _cumleler(aciklama[linux.end():])
        ozet = f'Linux çekirdeği: {cumleler[0]}' if cumleler else ''
    else:
        cumleler = _cumleler(aciklama)
        tanim = _TANIM.match(_cumleler(orijinal_aciklama)[0]) if (orijinal_aciklama or '').strip() else None
        if tanim and len(cumleler) >= 2:
            ozet = f"{tanim.group('urun').strip()}: {cumleler[1]}"
        else:
            ozet = cumleler[0] if cumleler else ''

    ozet = _kisalt(ozet)
    return f"{eslesme.group('id')} - {ozet}" if ozet else baslik
