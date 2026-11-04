"""Gundem: bes bolumun son kayitlarini olaylara gruplar, cok kaynakli olaylari puanlar.

Saf fonksiyonlar; veritabani, Django ayari, LLM ve dis istek yok. Ayni girdi ve ayni
`simdi` her zaman ayni sonucu verir: girdi once (bolum, id) ile siralanir, kume ve sozluk
sirasina bagli hicbir karar yoktur.

Tasarim: docs/superpowers/specs/2026-11-05-gundem-puani-design.md (G2-G4, s4, s5, s7).
Esikler gercek veri fiksturune (news/tests/fixtures/gundem_basliklari.json) gore
ayarlandi; test_gundem.py s5 orneklerini bu fikstur uzerinde dogrular.

Pencere
-------
`created_at` son 72 saatte (ve `simdi`'den sonra degil) VE yayin tarihi `simdi`'nin
Istanbul tarihinden en fazla 4 takvim gunu once. Yayin tarihi bossa yalniz `created_at`.
Yeni eklenen bir kaynagin eski yazilari boylece "yeni buyuk olay" gibi gorunmez.

Gruplama
--------
Yalniz Ingilizce ORIJINAL baslik kullanilir (ceviriler saglayicidan saglayiciya degisir).

- Sozcukler kucuk harfe indirilir, iyelik "'s" ve cogul "s" atilir (kok).
- Icerik kumesi: DURAK (islev ve manset dolgu sozcukleri) ile GENEL (guvenlik/YZ
  haberlerinin hepsinde gecen alan sozcukleri: flaw, hackers, critical, model...)
  disindaki sozcukler. Benzerlik bu kumelerin Jaccard oranidir.
- Ozel ad: harf iceren, DURAK/GENEL/GENEL_AD disinda kalan ve
  (a) rakam iceren (PHP2Shell, GPT-6.1), ya da (b) ilk harften sonra buyuk harf
  tasiyan (PHP, TraderTraitor, eMudhra), ya da (c) buyuk harfle yazilip penceredeki
  hicbir baslikta kucuk harfle gecmeyen VE en az bir "cumle duzeni" baslikta buyuk
  harfle gecen (Binance, Argon, Fragnesia) sozcuk. (c) kurali "Title Case" manset
  yazan kaynaklarin (THN, SecurityWeek, MarkTechPost) siradan sozcuklerini eler:
  "Remote", "Execution" yalniz Title Case basliklarda buyuk harflidir; bunlar ad
  sayilsaydi 10-21'de FortiSIEM ile PHP basliklari "Remote Code Execution" uzerinden
  birlesiyordu.
- GENEL_AD: Microsoft, Google, OpenAI, CISA, FBI; ulke/uyruk adlari (Japan: GMO ile
  Japan Airlines ayri olaylar); MFA, SSH gibi genel kisaltmalar ozel ad sayilmaz
  (icerik kumesinde kalir, benzerlige katkisi olur ama bag kurmaz). Kaynak adlarindaki
  sozcukler de (Google DeepMind, Hugging Face, AWS ML Blog) ayni nedenle genel sayilir:
  satici blogunun her yazisi kendi adini tasir.

Iki kayit su durumda ayni olaydir (union-find ile gecisli birlesir):

1. Ortak bir ozel ad VE Jaccard >= ORTA_ESIK VE (ikinci bir ortak ozel ad YA DA
   GENEL_AD olmayan bir ortak icerik sozcugu daha); ya da
2. Jaccard >= YUKSEK_ESIK ve en az YUKSEK_ORTAK_EN_AZ ortak icerik sozcugu (ad sartsiz).

Ozel ad icin salt belge sikligi esigi KULLANILMAZ: 10-21 penceresinde "PHP" 13 baslikta,
10-30 penceresinde "Microsoft" 8 baslikta gecer; siklik ikisini ayiramaz. Ayiran sey ad
ile birlikte orta benzerlik sartidir: "PHP releases emergency fixes for 2 critical
vulnerabilities" PHP2Shell basliklariyla "php" + "emergency" + "fixes" paylasir; buna
karsilik "Microsoft urges Entra ID admins to migrate users to passkeys" ile "Researcher
Reveals How Logic Bugs Alone Cracked Microsoft Edge in $175,000 Pwn2Own Win" yalniz
"microsoft"u paylasir ve ayri kalir (test_genel_ad_tek_basina_birlestirmez).
Supheli durumda ayri tutmak, yanlis birlestirmekten iyidir (spec s4).

Esikler (fiksturle ayarlandi):

- ORTA_ESIK = 0.12: en zayif gercek bag THN'nin "Binance Suffers Security Breach
  Affecting $6.3 Billion in Assets, Nearly $3 Billion Frozen" basligi; diger Binance
  basliklariyla yalniz "binance" + "6.3" paylasir (2/15 ~ 0.13). 0.15 bu kaynagi
  disarida birakip 10-30'da Binance'i 4 kaynaga dusuruyordu.
- Ek sozcugun GENEL_AD olmamasi sarti: AWS blogunun "Amazon Bedrock" gecen ilgisiz
  yazilari yalniz "bedrock" + "amazon" paylasir ve zincir kuruyordu.
- YUKSEK_ESIK = 0.4, YUKSEK_ORTAK_EN_AZ = 3: ozel ad yakalanamasa da cok benzer
  mansetler birlesir. Ornek: "Claude Code" iki genel addan olusur; THN "Official Claude
  Code VS Code Extension Compromised to Install Persistent SSH Backdoor" ile BC
  "Malicious Claude Code extension on Cursor planted SSH backdoors" (4/10) ve HNS
  "...poisoned with persistent SSH backdoor" ayni olaydir. Fiksturde 0.4-0.5 araligindaki
  3+ ortak sozcuklu ciftlerin hepsi ayni olaydi; 0.33-0.4 araliginda ise ilgisiz ciftler
  (OpenAI'nin Oracle ve ServiceNow ortaklik yazilari) basliyor, bu yuzden 0.4.

Puan (spec G3'un genellemesi)
-----------------------------
    puan = sum_kaynak 0.5 ** (yas(kaynagin en yeni makalesi) / 24)
         + 0.5 * sum_tekrar 0.5 ** (yas(tekrar makale) / 24)
         + 1.5 * 0.5 ** (yas(etki sozcuklu en yeni makale) / 24)   [etki sozcugu yoksa 0]

Butun makaleler ayni yastaysa spec G3 formulunun aynisidir:
(farkli_kaynak + 0.5 * (makale - farkli_kaynak) + etki) * 0.5 ** (yas / 24)
(test_puan_formulu: 3 kaynak 4 makale yas 0 -> 3.5; yas 24 -> 1.75; etki +1.5).

Neden genellestirildi: G3'te tek yas carpani olayin EN YENI makalesinden olculur. Gercek
veride 2026-10-30 20:00'de PHP2Shell'in uc gune yayilmis takip haberleri (6 kaynak, 8
makale; en yenisi 18:05) ayni dakikada son makalesi olan taze Binance haberini (5 kaynak,
6 makale, hepsi o gun) geciyordu: 8.03 > 6.62. Bu gruplamayla PHP2Shell 5 kaynak / 6
makalede kaliyor ve G3 formulu iki olayi 7.0 x ayni carpanda esitliyor; sirayi saniye farki
belirliyordu. Her kaynak kendi en yeni makalesinin yasiyla azalinca taze kapsam acikca one
gecer (Binance 6.03, PHP2Shell 3.56; sekiz PHP2Shell basligi tek olay olsa bile ~4.9) ve
suren haber yine olayi canli tutar: yeni makale taze agirlik getirir
(test_taze_kapsam_esit_buyuklukte_eskiyi_gecer).

Secim
-----
Once en az 2 farkli kaynakli olaylar puan azalan (esitlikte `son` azalan, sonra temsilci
(bolum, id)). Kalan yerler tek kaynakli olaylarin en yeni kaydiyla dolar (`created_at`
azalan, sonra (bolum, id)); her tek kaynakli olaydan yalniz bir kayit alinir ki ayni olay
iki satirda gorunmesin. Dolgu ogeleri kaynak_sayisi 1 ve makale_sayisi 1 tasir.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

# settings.TIME_ZONE ile ayni; saf modul Django ayarina bagli kalmasin diye sabit.
YEREL_SAAT = ZoneInfo('Europe/Istanbul')
PENCERE_SAAT = 72
YAYIN_GUN = 4
YARILANMA_SAAT = 24.0
TEKRAR_AGIRLIK = 0.5
ETKI_PUANI = 1.5
COK_KAYNAK_EN_AZ = 2

ORTA_ESIK = 0.12
YUKSEK_ESIK = 0.4
YUKSEK_ORTAK_EN_AZ = 3

# Islev sozcukleri ve manset dolgu sozcukleri (kok bicimiyle).
DURAK = frozenset('''
a an the and or of to in on for with by at from as is are was were be been being its it it's this that these
those new how why what who whom which when where after before over into via vs not no your you we our their
his her than more most up out say says said report amid about can could will would may might just now get
got one two three has have had do does did all any some still yet also only then there here other another
next way under against across through within without while ahead behind back down off per like make made
use using used today week day year time inside meet introducing announcing introduce introduces announce
announces unveil unveils unveiled launch launches launched release releases released show shows reveal
reveals revealed new latest what's here's now off over amid u.s us uk 2025 2026 vs.
'''.split())

# Alan genelinde cok sik gecen, olay ayirt etmeyen sozcukler (kok bicimiyle).
GENEL = frozenset('''
security cyber cybersecurity flaw bug vulnerability vulnerabilitie vuln hacker attacker attack threat malware
critical patch patche patched update fix fixe fixed exploit exploitation exploited exploiting data user ai model
agent agentic tool open source company team warn warning researcher research find found risk system service
app platform software code cloud network build building guide help issue issues million billion customer
government official orgs organization online device devices browser server servers account campaign actor
group gang target targeted targeting store
'''.split())

# Sik gecen genel adlar: ozel ad sayilmaz (spec G2 ayrim olcutu). Buyuk saticilar, kurumlar,
# ulke ve uyruk adlari, yaygin platformlar ve genel kisaltmalar. WordPress burada, PHP
# degil: WordPress eklenti aciklari her hafta ayri olaylardir; PHP'nin dil duzeyindeki
# acigi (PHP2Shell) ise nadirdir ve "PHP" gecen basliklar ancak benzerlikle birlesir.
GENEL_AD = frozenset('''
microsoft google apple amazon aws meta openai anthropic nvidia cisco oracle ibm intel amd samsung adobe
cisa fbi nsa doj dhs us uk eu nato
china chinese russia russian iran iranian north south korea korean israel israeli ukraine ukrainian
japan japanese india indian taiwan taiwanese germany german france french britain british australia
australian canada canadian europe european asia asian africa african america american
linux windows android ios macos chrome firefox github gitlab kubernetes k8s python java javascript wordpress
ai llm api ceo cto ciso it rce cve cvss sql vpn dos ddos os mcp saas gpu tpu sdk mfa 2fa sso ssh tls ssl
dns http xss poc iot ics edr siem soc apt
deepmind azure gemini claude chatgpt gpt copilot week review
'''.split())

# Etki sozcukleri (spec G3 ornekleri, kok bicimiyle eslesir).
ETKI_SOZCUKLERI = frozenset('''
hack hacked heist breach breached breaches stolen theft ransomware zero-day 0-day exploited emergency critical
outage billion record
'''.split())

CEVIRI_SIRASI = {'gemini': 0, 'openrouter': 1, 'deepl': 1, 'google': 2, 'libretranslate': 3}
CEVIRISIZ_SIRA = 4
BOS_CEVIRI_SIRA = 5

_KISA_ISLEV = frozenset('a an the and or of to in on for with by at from as vs via is are be its'.split())
_SOZCUK = re.compile(r"[A-Za-z0-9$]+(?:[.\-'][A-Za-z0-9]+)*")


@dataclass(frozen=True)
class Ogeler:
    bolum: str
    id: int
    source: str
    baslik: str
    created_at: datetime
    yayin: Optional[date]
    ceviri: str
    tr_baslik: str


def _anahtar(oge: Ogeler) -> Tuple[str, int]:
    return (oge.bolum, oge.id)


def _kaynak(oge: Ogeler) -> str:
    return (oge.source or '').strip().casefold()


def _sozcukler(baslik: str) -> List[str]:
    metin = (baslik or '').replace('’', "'").replace('‘', "'")
    return [s.lstrip('$') for s in _SOZCUK.findall(metin) if s.lstrip('$')]


def _kok(sozcuk: str) -> str:
    k = sozcuk.lower()
    if k.endswith("'s"):
        k = k[:-2]
    k = k.strip("'")
    if len(k) > 3 and k.endswith('s') and not k.endswith(('ss', 'us', 'is')):
        k = k[:-1]
    return k


def _yas_carpani(simdi: datetime, an: datetime) -> float:
    saat = max(0.0, (simdi - an).total_seconds() / 3600.0)
    return 0.5 ** (saat / YARILANMA_SAAT)


def penceredeki(ogeler: List[Ogeler], simdi: datetime) -> List[Ogeler]:
    """72 saat + 4 takvim gunu kurali (bkz. modul belgesi)."""
    alt = simdi - timedelta(hours=PENCERE_SAAT)
    en_eski_yayin = simdi.astimezone(YEREL_SAAT).date() - timedelta(days=YAYIN_GUN)
    return [
        o for o in ogeler
        if alt <= o.created_at <= simdi and (o.yayin is None or o.yayin >= en_eski_yayin)
    ]


def _title_case_mi(sozcukler: List[str]) -> bool:
    """Basligin "Title Case" yazilip yazilmadigi: ilk sozcuk ve kisa islev sozcukleri
    disindaki harfle baslayan sozcuklerin cogu buyuk harfle basliyorsa."""
    adaylar = [s for s in sozcukler[1:] if s[0].isalpha() and s.lower() not in _KISA_ISLEV]
    if len(adaylar) < 2:
        return True  # karar verilemiyor; ad kaniti sayilmaz
    buyuk = sum(1 for s in adaylar if s[0].isupper())
    return buyuk >= 0.6 * len(adaylar)


def _baslik_ozellikleri(ogeler: List[Ogeler]) -> List[Tuple[frozenset, frozenset]]:
    """Her oge icin (icerik kumesi, ozel ad kumesi)."""
    kucuk_gorulen = set()
    cumle_duzeninde_buyuk = set()
    kaynak_sozcukleri = set()
    for o in ogeler:
        sozcukler = _sozcukler(o.baslik)
        title_case = _title_case_mi(sozcukler)
        for s in sozcukler:
            if s[0].islower():
                kucuk_gorulen.add(_kok(s))
            elif s[0].isupper() and not title_case:
                cumle_duzeninde_buyuk.add(_kok(s))
        for s in _sozcukler(o.source):
            kaynak_sozcukleri.add(_kok(s))

    sonuc = []
    for o in ogeler:
        icerik = set()
        adlar = set()
        for s in _sozcukler(o.baslik):
            k = _kok(s)
            if not k or k in DURAK or k in GENEL:
                continue
            icerik.add(k)
            if k in GENEL_AD or k in kaynak_sozcukleri or len(k) < 2:
                continue
            if not any(c.isalpha() for c in s):
                continue
            if (any(c.isdigit() for c in s)
                    or any(c.isupper() for c in s[1:])
                    or (s[0].isupper() and k not in kucuk_gorulen and k in cumle_duzeninde_buyuk)):
                adlar.add(k)
        sonuc.append((frozenset(icerik), frozenset(adlar)))
    return sonuc


def _ayni_olay(a: Tuple[frozenset, frozenset], b: Tuple[frozenset, frozenset]) -> bool:
    icerik_a, adlar_a = a
    icerik_b, adlar_b = b
    ortak = icerik_a & icerik_b
    if not ortak:
        return False
    jaccard = len(ortak) / len(icerik_a | icerik_b)
    ortak_adlar = adlar_a & adlar_b
    if ortak_adlar and jaccard >= ORTA_ESIK:
        # Ad tek basina yetmez: ikinci bir ortak ad ya da genel ad olmayan bir ortak
        # icerik sozcugu daha gerekir ("Amazon Bedrock" gibi satici urun adi + satici
        # adi baglamaz).
        ek = [k for k in ortak - ortak_adlar if k not in GENEL_AD]
        if len(ortak_adlar) >= 2 or ek:
            return True
    return len(ortak) >= YUKSEK_ORTAK_EN_AZ and jaccard >= YUKSEK_ESIK


def olaylari_grupla(ogeler: List[Ogeler]) -> List[List[Ogeler]]:
    """Ogeleri olaylara boler. Cikti: her olay (created_at, bolum, id) sirali; olaylar ilk
    ogelerine gore sirali. Girdi sirasindan bagimsizdir."""
    sirali = sorted(ogeler, key=_anahtar)
    ozellik = _baslik_ozellikleri(sirali)
    ebeveyn = list(range(len(sirali)))

    def kok_bul(i: int) -> int:
        while ebeveyn[i] != i:
            ebeveyn[i] = ebeveyn[ebeveyn[i]]
            i = ebeveyn[i]
        return i

    for i in range(len(sirali)):
        for j in range(i + 1, len(sirali)):
            if _ayni_olay(ozellik[i], ozellik[j]):
                a, b = kok_bul(i), kok_bul(j)
                if a != b:
                    ebeveyn[max(a, b)] = min(a, b)

    gruplar: Dict[int, List[Ogeler]] = {}
    for i, oge in enumerate(sirali):
        gruplar.setdefault(kok_bul(i), []).append(oge)
    olaylar = [sorted(g, key=lambda o: (o.created_at, o.bolum, o.id)) for g in gruplar.values()]
    olaylar.sort(key=lambda g: (g[0].created_at, g[0].bolum, g[0].id))
    return olaylar


def _etkili(oge: Ogeler) -> bool:
    return any(_kok(s) in ETKI_SOZCUKLERI or s.lower() in ETKI_SOZCUKLERI for s in _sozcukler(oge.baslik))


def olay_puani(olay: List[Ogeler], simdi: datetime) -> float:
    """Kaynak basina yas carpanli puan (bkz. modul belgesi; spec G3'un genellemesi)."""
    en_yeni: Dict[str, Ogeler] = {}
    for o in sorted(olay, key=lambda o: (o.created_at, o.bolum, o.id)):
        en_yeni[_kaynak(o)] = o  # sirali gezildigi icin sonuncusu en yenisi
    kaynak_toplam = sum(_yas_carpani(simdi, o.created_at) for o in en_yeni.values())
    secilenler = {_anahtar(o) for o in en_yeni.values()}
    tekrar_toplam = sum(_yas_carpani(simdi, o.created_at) for o in olay if _anahtar(o) not in secilenler)
    etkililer = [o.created_at for o in olay if _etkili(o)]
    etki = ETKI_PUANI * _yas_carpani(simdi, max(etkililer)) if etkililer else 0.0
    return kaynak_toplam + TEKRAR_AGIRLIK * tekrar_toplam + etki


def _ceviri_sirasi(oge: Ogeler) -> int:
    if not (oge.tr_baslik or '').strip():
        return BOS_CEVIRI_SIRA
    return CEVIRI_SIRASI.get((oge.ceviri or '').strip().lower(), CEVIRISIZ_SIRA)


def temsilci(olay: List[Ogeler]) -> Ogeler:
    """En iyi cevrilmis kayit; esitlikte en erken giren, sonra en kucuk id."""
    return min(olay, key=lambda o: (_ceviri_sirasi(o), o.created_at, o.id, o.bolum))


def _kaynak_adlari(olay: List[Ogeler]) -> List[str]:
    adlar: Dict[str, str] = {}
    for o in olay:
        anahtar = _kaynak(o)
        ad = (o.source or '').strip()
        if anahtar not in adlar or ad < adlar[anahtar]:
            adlar[anahtar] = ad
    return sorted(adlar.values(), key=lambda a: (a.casefold(), a))


def _olay_ozeti(olay: List[Ogeler], simdi: datetime, kayit: Ogeler) -> dict:
    return {
        'temsilci': kayit,
        'kaynak_sayisi': len({_kaynak(o) for o in olay}),
        'kaynaklar': _kaynak_adlari(olay),
        'makale_sayisi': len(olay),
        'bolumler': sorted({o.bolum for o in olay}),
        'puan': round(olay_puani(olay, simdi), 2),
        'ilk': min(o.created_at for o in olay),
        'son': max(o.created_at for o in olay),
    }


def olaylari_sec(ogeler: List[Ogeler], simdi: datetime, adet: int = 6) -> List[dict]:
    """Penceredeki ogelerden Gundem ogelerini secer (bkz. modul belgesi, Secim)."""
    olaylar = olaylari_grupla(penceredeki(ogeler, simdi))
    cok, tek = [], []
    for olay in olaylar:
        (cok if len({_kaynak(o) for o in olay}) >= COK_KAYNAK_EN_AZ else tek).append(olay)

    puanli = [(olay_puani(o, simdi), max(x.created_at for x in o), temsilci(o), o) for o in cok]
    puanli.sort(key=lambda p: (-p[0], -p[1].timestamp(), _anahtar(p[2])))
    secim = [_olay_ozeti(o, simdi, t) for _, _, t, o in puanli[:adet]]

    if len(secim) < adet:
        dolgu = [max(olay, key=lambda o: (o.created_at, -o.id, o.bolum)) for olay in tek]
        dolgu.sort(key=lambda o: (-o.created_at.timestamp(), o.id, o.bolum))
        for kayit in dolgu[:adet - len(secim)]:
            secim.append(_olay_ozeti([kayit], simdi, kayit))
    return secim
