#!/usr/bin/env python3
"""ZAP baseline JSON raporunu SARIF 2.1.0'a cevirir (GUVENLIK-PLANI P5).

    scripts/zap_sarif.py report_json.json zap-baseline.sarif [--kurallar .zap/rules.tsv]

Yalniz standart kutuphane. Her ZAP alert tipi (alertRef; yoksa pluginid) bir SARIF kurali,
her instance bir sonuc olur. `--kurallar`: ZAP'in rules.tsv'sindeki IGNORE eklentileri SARIF'e
alinmaz. ZAP'in kendi IGNORE'u yalniz konsol ozetini ve cikis kodunu etkiler, JSON rapor
onlari yine tasir; Security sekmesine dusmemeleri icin filtre burada. DAST'ta dosya yoktur ve GitHub Code Scanning "http" semali artifactLocation
kabul etmez (checkout semasi "file" ile eslesmeli); bu yuzden konum sanal goreli yoldur
(`dast/<url-yolu>`), tam URL mesajda ve logicalLocations'ta tasinir. GitHub Security sekmesi
`security-severity` ile siddeti, `partialFingerprints` ile ayni bulgunun kosular arasinda
takibini yapar. Rapor bos olsa da gecerli (sonucsuz) SARIF uretilir: hat yesil kalir ama
Security sekmesinde "ZAP calisti, bulgu yok" gorunur.
"""
import hashlib
import html
import json
import re
import sys
from urllib.parse import urlsplit

SARIF_SEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/sarif-2.1/schema/sarif-schema-2.1.0.json"
ZAP_BILGI = "https://www.zaproxy.org/"

# ZAP riskcode -> (SARIF level, GitHub security-severity).
# GitHub esikleri: >=9.0 critical, 7.0-8.9 high, 4.0-6.9 medium, <4.0 low.
RISK = {
    "3": ("error", "8.0"),
    "2": ("warning", "5.0"),
    "1": ("note", "3.0"),
    "0": ("note", "1.0"),
}

_ETIKET = re.compile(r"<[^>]+>")
_BOSLUK = re.compile(r"\s+")


def _duz_metin(s):
    """ZAP alanlari HTML tasir (<p>...</p>); Security sekmesi duz metin bekler."""
    if not s:
        return ""
    s = _ETIKET.sub(" ", str(s))
    return _BOSLUK.sub(" ", html.unescape(s)).strip()


def _kural_id(alert):
    """Kural anahtari alertRef'tir (or. 90005-2): bir eklenti birden fazla alt kural uretebilir
    (Sec-Fetch-Dest/Mode/Site/User) ve her birinin adi farklidir. alertRef yoksa pluginid."""
    ref = str(alert.get("alertRef") or "").strip()
    pluginid = str(alert.get("pluginid", "")).strip() or "bilinmeyen"
    return f"zap/{ref or pluginid}"


def _kural(alert):
    pluginid = str(alert.get("pluginid", "")).strip() or "bilinmeyen"
    ad = _duz_metin(alert.get("name") or alert.get("alert") or f"ZAP {pluginid}")
    seviye, siddet = RISK.get(str(alert.get("riskcode", "0")), RISK["0"])
    aciklama = _duz_metin(alert.get("desc")) or ad
    cozum = _duz_metin(alert.get("solution"))
    kaynak = _duz_metin(alert.get("reference"))
    diger = _duz_metin(alert.get("otherinfo"))
    yardim = " ".join(p for p in (
        f"Cozum: {cozum}" if cozum else "",
        f"Kaynak: {kaynak}" if kaynak else "",
        f"Ek bilgi: {diger}" if diger else "",
    ) if p) or aciklama

    etiketler = ["security", "dast", "zap", f"risk-{alert.get('riskdesc', '').split(' ')[0].lower() or 'bilinmiyor'}"]
    cwe = str(alert.get("cweid", "")).strip()
    if cwe and cwe not in ("-1", "0"):
        etiketler.append(f"CWE-{cwe}")
    wasc = str(alert.get("wascid", "")).strip()
    if wasc and wasc not in ("-1", "0"):
        etiketler.append(f"WASC-{wasc}")

    return {
        "id": _kural_id(alert),
        "name": ad,
        "shortDescription": {"text": ad},
        "fullDescription": {"text": aciklama},
        "help": {"text": yardim},
        "helpUri": f"https://www.zaproxy.org/docs/alerts/{pluginid}/",
        "defaultConfiguration": {"level": seviye},
        "properties": {
            "security-severity": siddet,
            "tags": etiketler,
            "zap-riskcode": str(alert.get("riskcode", "")),
            "zap-confidence": str(alert.get("confidence", "")),
        },
    }


def _konum_yolu(uri):
    """URL -> Code Scanning'in kabul ettigi goreli sanal yol: dast/<yol> (sorgu ve host yok)."""
    yol = urlsplit(uri).path.lstrip("/")
    return f"dast/{yol}"


def _sonuc(alert, instance, kural_id, kural_index):
    seviye, _ = RISK.get(str(alert.get("riskcode", "0")), RISK["0"])
    uri = str(instance.get("uri") or "").strip() or "http://localhost/"
    yontem = str(instance.get("method") or "").strip()
    param = _duz_metin(instance.get("param"))
    kanit = _duz_metin(instance.get("evidence"))
    ad = _duz_metin(alert.get("name") or alert.get("alert") or kural_id)

    parcalar = [ad, f"{yontem} {uri}".strip()]
    if param:
        parcalar.append(f"parametre: {param}")
    if kanit:
        parcalar.append(f"kanit: {kanit[:200]}")
    mesaj = " | ".join(parcalar)

    # Ayni kural + URL + parametre = ayni bulgu; kanit degisse de GitHub ayni alert'i gunceller.
    iz = hashlib.sha256(f"{kural_id}\n{yontem}\n{uri}\n{param}".encode("utf-8")).hexdigest()[:32]

    ozellikler = {"method": yontem} if yontem else {}
    diger = _duz_metin(instance.get("otherinfo"))
    if diger:
        ozellikler["otherinfo"] = diger[:500]

    return {
        "ruleId": kural_id,
        "ruleIndex": kural_index,
        "level": seviye,
        "message": {"text": mesaj},
        "locations": [{
            "physicalLocation": {
                "artifactLocation": {"uri": _konum_yolu(uri), "uriBaseId": "%SRCROOT%"},
            },
            "logicalLocations": [{"name": uri, "kind": "resource"}],
        }],
        "partialFingerprints": {"zap/instance": iz},
        "properties": ozellikler,
    }


def ignore_eklentileri(yol):
    """ZAP rules.tsv -> IGNORE satirlarindaki pluginid kumesi. Bicim: <pluginid>\\t<IGNORE|WARN|FAIL>\\t(...)."""
    eklentiler = set()
    with open(yol, encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if not satir or satir.startswith("#"):
                continue
            alanlar = satir.split("\t")
            if len(alanlar) >= 2 and alanlar[1].strip().upper() == "IGNORE":
                eklentiler.add(alanlar[0].strip())
    return eklentiler


def donustur(rapor, yok_say=frozenset()):
    """ZAP JSON raporu (dict) -> SARIF 2.1.0 (dict). yok_say: atlanacak pluginid'ler."""
    kurallar = []
    indeks = {}
    sonuclar = []
    atlanan = 0

    for site in rapor.get("site") or []:
        for alert in site.get("alerts") or []:
            if str(alert.get("pluginid", "")).strip() in yok_say:
                atlanan += 1
                continue
            kural = _kural(alert)
            kid = kural["id"]
            if kid not in indeks:
                indeks[kid] = len(kurallar)
                kurallar.append(kural)
            else:
                # Ayni alertRef birden fazla site'ta gelebilir; en yuksek riski koru
                mevcut = kurallar[indeks[kid]]
                if float(kural["properties"]["security-severity"]) > float(mevcut["properties"]["security-severity"]):
                    kurallar[indeks[kid]] = kural
            instances = alert.get("instances") or [{}]
            for instance in instances:
                sonuclar.append(_sonuc(alert, instance, kid, indeks[kid]))

    return {
        "$schema": SARIF_SEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "OWASP ZAP",
                    "version": str(rapor.get("@version") or "bilinmiyor"),
                    "informationUri": ZAP_BILGI,
                    "rules": kurallar,
                }
            },
            "results": sonuclar,
            "properties": {
                "generated": str(rapor.get("@generated") or ""),
                "sites": [str(s.get("@name") or "") for s in (rapor.get("site") or [])],
                "ignoredPlugins": sorted(yok_say),
                "ignoredAlertTypes": atlanan,
            },
        }],
    }


def main(argv):
    argv = list(argv)
    kurallar_yolu = None
    if "--kurallar" in argv:
        i = argv.index("--kurallar")
        if i + 1 >= len(argv):
            print("--kurallar bir dosya yolu ister", file=sys.stderr)
            return 2
        kurallar_yolu = argv[i + 1]
        del argv[i:i + 2]
    if len(argv) != 2:
        print("kullanim: zap_sarif.py <report_json.json> <cikti.sarif> [--kurallar rules.tsv]", file=sys.stderr)
        return 2
    girdi, cikti = argv
    try:
        with open(girdi, encoding="utf-8") as f:
            rapor = json.load(f)
    except (OSError, ValueError) as hata:
        print(f"ZAP raporu okunamadi: {girdi}: {hata}", file=sys.stderr)
        return 1
    yok_say = frozenset()
    if kurallar_yolu:
        try:
            yok_say = frozenset(ignore_eklentileri(kurallar_yolu))
        except OSError as hata:
            print(f"kural dosyasi okunamadi: {kurallar_yolu}: {hata}", file=sys.stderr)
            return 1
    sarif = donustur(rapor, yok_say=yok_say)
    with open(cikti, "w", encoding="utf-8") as f:
        json.dump(sarif, f, ensure_ascii=False, indent=2)
    run = sarif["runs"][0]
    print(f"SARIF yazildi: {cikti} ({len(run['results'])} sonuc, {len(run['tool']['driver']['rules'])} kural; "
          f"IGNORE ile atlanan alert tipi: {run['properties']['ignoredAlertTypes']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
