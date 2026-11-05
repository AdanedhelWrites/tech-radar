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
  satici blogunun her yazisi kendi adini tasir. Bilerek guvenli taraf: kaynak adi
  urun adiysa (DevTools'ta "Redis", "PostgreSQL") o urunun adi hicbir baslikta ad bagi
  kuramaz; ornegin bir Redis acigi haberi Redis surum notuyla ad uzerinden birlesmez.
- Uydurma ad: harf-rakam-harf bicimli, en az UYDURMA_HARF_EN_AZ harfli kok
  (^[a-z]+[0-9]+[a-z]+$: php2shell, plex2shell, node2shell) ya da ayni CVE kimligi
  (cve-YYYY-NNNN...). Bunlar bir olaya ozgu konmus adlardir ve TEK BASINA baglar.
  Genel harf+rakam adlari (GPT-6.1, ISC2), CamelCase ya da buyuk harfli adlar tek
  basina baglamaz; inceleme taramasinda bunlar yanlis bag uretiyordu.
- Ad obegi: baslikta bitisik ozel adlar tek ad obegidir ("Palo Alto", "West Virginia",
  "GPT-6 Astra"). Kural 2'deki "ikinci ortak ad" obek olarak sayilir: iki sozcuklu tek
  bir ortak ad yine ek sozcuk ister. Neden: The Record "Court strikes down West Virginia
  law..." ile TechCrunch "Nvidia weighs ... AI data center in West Virginia" ve OpenAI
  Blog "Basis completes a tax workbook 2x faster with GPT-6 Astra" ile GPT-6.1 Sol
  olayi yalniz boyle bir obek uzerinden birlesiyordu. Bedeli (tum-olay taramasi): yalniz
  rakamsiz iki sozcuklu adi paylasan dogru ciftler de ayri kalir ("SiteGuard WAF",
  "Quest Diagnostics"); supheli durumda ayri tutma kurali geregi. Ayni kaynak kurali (0)
  token sayar; orada Jaccard >= YUKSEK_ESIK zaten siki.
- Surumlu urun adi obegi (_surum_obegi): basligin ILK rakamli ad obegi ("GPT-6.1 Sol",
  "Gemini 4 Argon" -> {4, argon}, "Kubernetes 1.35"). Iki baslikta AYNI ise tek basina
  baglar (kural 1): buyuk model/surum cikislari Gundem'in asil konusudur ve "Introducing
  GPT-6.1 Terra" gibi basliklarda baska ortak sozcuk yoktur. Yalniz ilk obek alindigi
  icin TechCrunch "OpenAI launches GPT-6.1 Sol, says it nearly matches GPT-6 Astra"
  basligi GPT-6.1 Sol'dur; Basis "...with GPT-6 Astra" ona baglanmaz. "Windows 11",
  "Microsoft 365" gibi yalniz genel ad + tamsayi obekleri gecersizdir.
- Listeler (DURAK, GENEL, GENEL_AD) kok bicimleriyle de genisletilir: "windows",
  "kubernetes", "macos" kokte "window", "kubernete", "maco" olur; yoksa eslesmiyordu.
- Yil sozcukleri (^(19|20)\\d{2}$) atilir: "2027" iki ilgisiz basligi ek sozcuk olarak
  bagliyordu. Binlik ayiracli sayilar tek sozcuktur ("238,000"; yoksa "000" baglardi).
- DURAK genel karsilastirma ve sifatlari da icerir (faster, biggest, top, major...):
  MarkTechPost "...Flow Map Drafter for 6.14x Faster LLM Decoding" ile Google Cloud SRE
  "How to troubleshoot GKE workloads faster with VPC Flow Logs" "flow" + "faster" ile
  birlesiyordu. DURAK kok bicimiyle karsilastirilir ("launches" -> "launche").

Iki kayit su durumda ayni olaydir (union-find ile gecisli birlesir):

0. Ayni kaynaktan iki kayit YALNIZ su durumda dogrudan baglanir: Jaccard >= YUKSEK_ESIK
   VE (en az 2 ortak ozel ad YA DA en az YUKSEK_ORTAK_EN_AZ ortak sozcuk). Asagidaki
   kurallar ayni kaynak icin uygulanmaz. Neden: AWS ML Blog'un "Amazon Bedrock AgentCore"
   paylasan ilgisiz iki yazisi 10-01'de GPT-6.1 olayina zincirleniyordu. Ayni kaynagin
   takip haberleri diger kaynaklar uzerinden yine ayni olaya baglanir.
1. Ortak uydurma ad, ayni CVE kimligi ya da ayni surumlu urun adi obegi; ya da
2. Ortak bir ozel ad VE Jaccard >= ORTA_ESIK VE (ikinci bir ortak ad OBEGI YA DA
   GENEL_AD olmayan bir ortak icerik sozcugu daha); ya da
3. Jaccard >= YUKSEK_ESIK ve en az YUKSEK_ORTAK_EN_AZ ortak icerik sozcugu (ad sartsiz).

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

Secim aninda birlestirme: secilen ve ZATEN COK KAYNAKLI olan iki satirin olaylarinda
BUTUN basliklarin oznesi ayni ise iki olay birlesir, puan ve temsilci yeniden hesaplanir
ve secim bastan yapilir; kararli olana kadar. Iki olayin zaman araliklari kesismeli ya da
aralarinda en fazla BIRLESME_ZAMAN_SAAT (24 sa) olmali: ayni sirketin gunler arayla
yasadigi ayri olaylar (ornegin iki ayri Ivanti acigi) birlesmez. Dolgu (tek kaynakli) satirlar asla katilmaz:
tek basliklik bir olay "butun basliklar ayni ozneli" sartini kendiliginden saglar ve
ozne gurultuludur (The Record "Judge denies WhatsApp's bid..." ile Ars "Judge rejects
Trump's..." sahte iki kaynakli satir olurdu; Google Cloud SRE'nin iki "Accelerating..."
yazisi ayni kaynak kuralini asardi).
Ozne: basliktaki ilk ozel ad ya da pencerede hic kucuk harfle gecmeyen ilk buyuk harfli
icerik sozcugu; GENEL_AD ve kaynak adlari atlanir. Ikinci kosul yalniz Title Case
basliklarda gecen adlari yakalar: "Siemens Software Center Vulnerability Exploited in
ClickFix Malware Attacks" icin ozne "siemens"tir; "Google Chrome Adds ClickFix Warnings"
icin "clickfix". Boylece Siemens ClickFix ile Chrome ClickFix olaylari birlesmez.
Neden: 10-30 12:15-18:00 arasi Binance iki olayda kaliyordu (capraz ciftler yalniz
"binance" paylasiyordu, ikisi ~3.16, ikisi de 2 kaynakli) ve iki satirda gorunuyordu
(spec s4). Fikstur taramasinda (10-21..10-23 ve 10-30..11-03, 15 dk aralik, 768 an) kural
yalniz Binance icin tetiklendi; tum olaylar satir sayildiginda da (adet sinirsiz) yanlis
birlesme yok (bkz. task-1-report.md, duzeltme turu 2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, NamedTuple, Optional, Tuple
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
UYDURMA_HARF_EN_AZ = 4  # "a1b" gibi kisa kodlar uydurma ad sayilmaz
BIRLESME_ZAMAN_SAAT = 24  # secim aninda birlesme: iki olayin zaman araligi en fazla bu kadar uzak

# Islev sozcukleri, manset dolgu sozcukleri ve genel karsilastirma/sifatlar (faster, biggest,
# top...; ek sozcuk olarak bag kurmasinlar diye). Kok bicimiyle; alfabetik, tekrarsiz. Yillar
# burada degil, _YIL kalibiyla atilir.
DURAK = frozenset('''
a about across after against ahead all also amid an and announce announces announcing another any are as at
back be been before behind being best better big bigger biggest by can cheaper cheapest could day did do does
down earlier early easier easiest fast faster fastest first for from full get got great greater greatest had
has have her here here's high higher highest his how in inside into introduce introduces introducing is it
it's its just large larger largest last latest launch launche launched launches less like low lower lowest
made major make may meet might more most new newer newest next no not now of off old older oldest on one only
or other our out over per release released releases report reveal revealed reveals said say says show shows
small smaller smallest smart smarter some still strong stronger than that the their then there these this
those three through time to today top two u.s uk under unveil unveiled unveils up us use used using via vs was
way we week were what what's when where which while who whom why will with within without worse worst would
year yet you your
'''.split())

# Alan genelinde cok sik gecen, olay ayirt etmeyen sozcukler (kok bicimiyle).
GENEL = frozenset('''
security cyber cybersecurity flaw bug vulnerability vulnerabilitie vuln hacker attacker attack threat malware
critical patch patche patched update fix fixe fixed exploit exploitation exploited exploiting data user ai model
agent agentic tool open source company team warn warning researcher research find found risk system service
app platform software code cloud network build building guide help issue issues million billion customer
government official orgs organization online device devices browser server servers account campaign actor
group gang target targeted targeting store zero-day 0-day part chapter section
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

# Surum obegini bitiren, urun adi olmayan sozcukler: "CVSS 9.8", "Part 1", "Chapter 11",
# "Section 230", "Fortune 500", "SEC 8-K" tek basina baglanmasin (_surum_obegi).
OBEK_DISI = frozenset('cvss part chapter section fortune sec'.split())
_DOSYA_FORMU = re.compile(r'^\d+-[kq]$')  # SEC dosyalari: 8-K, 10-K, 10-Q

# Etki sozcukleri (spec G3 ornekleri, kok bicimiyle eslesir).
ETKI_SOZCUKLERI = frozenset('''
hack hacked heist breach breached breaches stolen theft ransomware zero-day 0-day exploited emergency critical
outage billion record
'''.split())

CEVIRI_SIRASI = {'gemini': 0, 'openrouter': 1, 'deepl': 1, 'google': 2, 'libretranslate': 3}
CEVIRISIZ_SIRA = 4
BOS_CEVIRI_SIRA = 5

_KISA_ISLEV = frozenset('a an the and or of to in on for with by at from as vs via is are be its'.split())
_UYDURMA = re.compile(r'^[a-z]+[0-9]+[a-z]+$')
_CVE = re.compile(r'^cve-\d{4}-\d{4,}$')
_YIL = re.compile(r'^(19|20)\d{2}$')
# Binlik ayiracli sayilar tek sozcuktur ("238,000"); yoksa "000" iki ilgisiz basligi
# ek sozcuk olarak baglayabiliyordu (Denver Health ile DHS sizintisi).
_SOZCUK = re.compile(r"[A-Za-z0-9$]+(?:(?:[.\-']|,(?=\d{3}\b))[A-Za-z0-9]+)*")


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


def _surum_obegi(baslik: str) -> Optional[frozenset]:
    """Basliktaki ilk gecerli surumlu urun adi obegi ("GPT-6.1 Sol", "Gemini 4 Argon",
    "Kubernetes 1.35"); yoksa None.

    Obek: aralarinda yalniz bosluk olan, buyuk harf (macOS dahil) ya da rakam iceren ardisik
    sozcukler (DURAK, GENEL ve yil sozcukleri ile her noktalama obegi bitirir). Basindaki
    genel adlar (OpenAI's, Gemini) kalan en az iki sozcukse atilir. Gecerli sayilmasi icin
    en az iki sozcuk, en az bir rakamli sozcuk ve ya genel ad olmayan harfli bir sozcuk
    ("Argon", "Sol") ya da noktali bir surum ("1.35") gerekir; "Windows 11", "Microsoft
    365" gecersizdir. Yalniz ILK gecerli obek alinir: TechCrunch "OpenAI launches GPT-6.1
    Sol, says it nearly matches GPT-6 Astra" basligin oznesi GPT-6.1 Sol'dur."""
    metin = (baslik or '').replace('’', "'").replace('‘', "'")
    obekler: List[List[Tuple[str, str]]] = []
    obek: Optional[List[Tuple[str, str]]] = None
    onceki_son = 0
    for m in _SOZCUK.finditer(metin):
        bitisik = metin[onceki_son:m.start()].strip() == ''
        onceki_son = m.end()
        ham = m.group().lstrip('$')
        k = _kok(ham) if ham else ''
        uye = (bool(k) and k not in DURAK and k not in GENEL and not _YIL.match(k)
               and k not in OBEK_DISI and not _DOSYA_FORMU.match(k)
               and (any(c.isupper() for c in ham) or any(c.isdigit() for c in ham)))
        if not uye:
            obek = None
            continue
        if obek is None or not bitisik:
            obek = []
            obekler.append(obek)
        obek.append((ham, k))
    for obek in obekler:
        if not any(any(c.isdigit() for c in ham) for ham, _ in obek):
            continue
        kokler = [k for _, k in obek]
        while len(kokler) > 2 and kokler[0] in GENEL_AD:
            kokler.pop(0)
        if len(kokler) < 2:
            continue
        harfli_ad = any(k not in GENEL_AD and not any(c.isdigit() for c in k) and any(c.isalpha() for c in k)
                        for k in kokler)
        noktali = any('.' in k and any(c.isdigit() for c in k) for k in kokler)
        if harfli_ad or noktali:
            return frozenset(kokler)
    return None


def _kok(sozcuk: str) -> str:
    k = sozcuk.lower()
    if k.endswith("'s"):
        k = k[:-2]
    k = k.strip("'")
    if len(k) > 3 and k.endswith('s') and not k.endswith(('ss', 'us', 'is')):
        k = k[:-1]
    return k


# Listeler kok bicimiyle karsilastirilir; cogul yazilan girdiler kok bicimleriyle de eklenir.
# Yoksa "windows", "kubernetes", "macos", "ddos" hic eslesmiyordu (kok: window, kubernete...)
# ve "Windows" ozel ad sayiliyordu.
# 3 harfli govde (does -> doe) baska bir sozcuge (DOE: Enerji Bakanligi) carpmasin diye atlanir.
DURAK = DURAK | frozenset(_kok(w) for w in DURAK if len(_kok(w)) >= 4)
GENEL = GENEL | frozenset(_kok(w) for w in GENEL)
GENEL_AD = GENEL_AD | frozenset(_kok(w) for w in GENEL_AD)


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


class _Ozellik(NamedTuple):
    kaynak: str
    icerik: frozenset
    adlar: frozenset
    uydurma: frozenset  # tek basina baglayan uydurma adlar ve CVE kimlikleri
    ozne: Optional[str]  # basligin oznesi (bkz. _baslik_ozellikleri; genel adlar haric)
    obekler: Tuple[frozenset, ...] = ()  # bitisik ozel adlarin olusturdugu ad obekleri
    surum: Optional[frozenset] = None  # ilk surumlu urun adi obegi (bkz. _surum_obegi)


def _uydurma_mi(kok: str) -> bool:
    if _CVE.match(kok):
        return True
    return bool(_UYDURMA.match(kok)) and sum(c.isalpha() for c in kok) >= UYDURMA_HARF_EN_AZ


def _baslik_ozellikleri(ogeler: List[Ogeler]) -> List[_Ozellik]:
    """Her oge icin kaynak, icerik kumesi, ozel ad kumesi, uydurma adlar ve ozne."""
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
        uydurma = set()
        ozne = None
        obekler = []
        obek = None
        for s in _sozcukler(o.baslik):
            k = _kok(s)
            ad = False
            if k and k not in DURAK and k not in GENEL and not _YIL.match(k):
                icerik.add(k)
                if k not in GENEL_AD and k not in kaynak_sozcukleri and len(k) >= 2:
                    if _uydurma_mi(k):
                        uydurma.add(k)
                    if any(c.isalpha() for c in s):
                        ad = (any(c.isdigit() for c in s)
                              or any(c.isupper() for c in s[1:])
                              or (s[0].isupper() and k not in kucuk_gorulen and k in cumle_duzeninde_buyuk))
                        # Ozne: ilk ozel ad ya da pencerede hic kucuk harfle gecmeyen ilk buyuk
                        # harfli icerik sozcugu. Ikincisi yalniz Title Case basliklarda gecen adlari
                        # yakalar ("Siemens Software Center ..." -> siemens; yoksa "clickfix" olurdu).
                        if ozne is None and (ad or (s[0].isupper() and k not in kucuk_gorulen)):
                            ozne = k
            # Bitisik ozel adlar tek ad obegidir ("Palo Alto", "West Virginia", "GPT-6 Astra");
            # ad olmayan her sozcuk obegi bitirir.
            if ad:
                adlar.add(k)
                if obek is None:
                    obek = set()
                    obekler.append(obek)
                obek.add(k)
            else:
                obek = None
        sonuc.append(_Ozellik(_kaynak(o), frozenset(icerik), frozenset(adlar), frozenset(uydurma), ozne,
                              tuple(frozenset(ob) for ob in obekler), _surum_obegi(o.baslik)))
    return sonuc


def _ortak_obek_sayisi(a: _Ozellik, b: _Ozellik, ortak_adlar: frozenset) -> int:
    """Ortak ozel adlarin kac ayri ad obegine dagildigi (iki baslikta da; kucuk olani).
    "Palo Alto" tek obektir: iki ortak sozcuk ama tek ortak ad."""
    sayi_a = sum(1 for ob in a.obekler if ob & ortak_adlar)
    sayi_b = sum(1 for ob in b.obekler if ob & ortak_adlar)
    return min(sayi_a, sayi_b)


def _ayni_olay(a: _Ozellik, b: _Ozellik) -> bool:
    ortak = a.icerik & b.icerik
    if not ortak:
        return False
    jaccard = len(ortak) / len(a.icerik | b.icerik)
    ortak_adlar = a.adlar & b.adlar
    if a.kaynak == b.kaynak:
        # Ayni kaynagin iki yazisi ancak cok benzerse dogrudan baglanir; satici
        # bloglarinin urun adini paylasan ilgisiz yazilari zincir kurmasin.
        return jaccard >= YUKSEK_ESIK and (len(ortak_adlar) >= 2 or len(ortak) >= YUKSEK_ORTAK_EN_AZ)
    if a.uydurma & b.uydurma:
        return True
    if a.surum is not None and a.surum == b.surum:
        # Ayni surumlu urun adi (GPT-6.1 Sol, Gemini 4 Argon) uydurma ad gibi tek basina baglar.
        return True
    if ortak_adlar and jaccard >= ORTA_ESIK:
        # Ad tek basina yetmez: ikinci bir ortak ad OBEGI ya da genel ad olmayan bir ortak
        # icerik sozcugu daha gerekir ("Amazon Bedrock" gibi satici urun adi + satici adi,
        # "West Virginia" gibi iki sozcuklu tek ad baglamaz).
        ek = [k for k in ortak - ortak_adlar if k not in GENEL_AD]
        if _ortak_obek_sayisi(a, b, ortak_adlar) >= 2 or ek:
            return True
    return len(ortak) >= YUKSEK_ORTAK_EN_AZ and jaccard >= YUKSEK_ESIK


def _olay_sirasi(olay: List[Ogeler]) -> List[Ogeler]:
    return sorted(olay, key=lambda o: (o.created_at, o.bolum, o.id))


def _grupla(sirali: List[Ogeler], ozellik: List[_Ozellik]) -> List[List[Ogeler]]:
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
    olaylar = [_olay_sirasi(g) for g in gruplar.values()]
    olaylar.sort(key=lambda g: (g[0].created_at, g[0].bolum, g[0].id))
    return olaylar


def olaylari_grupla(ogeler: List[Ogeler]) -> List[List[Ogeler]]:
    """Ogeleri olaylara boler. Cikti: her olay (created_at, bolum, id) sirali; olaylar ilk
    ogelerine gore sirali. Girdi sirasindan bagimsizdir."""
    sirali = sorted(ogeler, key=_anahtar)
    return _grupla(sirali, _baslik_ozellikleri(sirali))


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


Satir = Tuple[List[Ogeler], Ogeler, bool]


def _satirlar(olaylar: List[List[Ogeler]], simdi: datetime, adet: int) -> List[Satir]:
    """(olay, gosterilecek kayit, dolgu_mu) satirlari: secim aninda birlestirme oncesi."""
    cok, tek = [], []
    for olay in olaylar:
        (cok if len({_kaynak(o) for o in olay}) >= COK_KAYNAK_EN_AZ else tek).append(olay)

    puanli = [(olay_puani(o, simdi), max(x.created_at for x in o), temsilci(o), o) for o in cok]
    puanli.sort(key=lambda p: (-p[0], -p[1].timestamp(), _anahtar(p[2])))
    satirlar = [(o, t, False) for _, _, t, o in puanli[:adet]]

    if len(satirlar) < adet:
        dolgu = [(max(olay, key=lambda o: (o.created_at, -o.id, o.bolum)), olay) for olay in tek]
        dolgu.sort(key=lambda p: (-p[0].created_at.timestamp(), p[0].id, p[0].bolum))
        satirlar.extend((olay, kayit, True) for kayit, olay in dolgu[:adet - len(satirlar)])
    return satirlar


def _olay_oznesi(olay: List[Ogeler], ozellik: Dict[Tuple[str, int], _Ozellik]) -> Optional[str]:
    """Olaydaki her basligin ilk ozel adi (oznesi) ayniysa o ad, degilse None."""
    ozneler = {ozellik[_anahtar(o)].ozne for o in olay}
    if len(ozneler) == 1:
        return ozneler.pop()
    return None


def _zamanca_yakin(a: List[Ogeler], b: List[Ogeler]) -> bool:
    """Iki olayin zaman araliklari kesisiyor ya da aralarinda en fazla BIRLESME_ZAMAN_SAAT var."""
    a_ilk, a_son = min(o.created_at for o in a), max(o.created_at for o in a)
    b_ilk, b_son = min(o.created_at for o in b), max(o.created_at for o in b)
    return max(a_ilk, b_ilk) - min(a_son, b_son) <= timedelta(hours=BIRLESME_ZAMAN_SAAT)


def _secip_birlestir(
    olaylar: List[List[Ogeler]], simdi: datetime, adet: int, ozellik: Dict[Tuple[str, int], _Ozellik],
) -> Tuple[List[Satir], List[Tuple[List[Ogeler], List[Ogeler]]]]:
    """Secim aninda birlestirme (bkz. modul belgesi). Doner: (satirlar, birlesen olay ciftleri)."""
    birlesmeler = []
    while True:
        satirlar = _satirlar(olaylar, simdi, adet)
        # Yalniz zaten cok kaynakli olan satirlar katilir: tek basliklik bir olay "butun
        # basliklar ayni ozneli" sartini kendiliginden saglar; dolgu satirlari asla birlesmez.
        adaylar = [olay for olay, _, dolgu in satirlar
                   if not dolgu and len({_kaynak(o) for o in olay}) >= COK_KAYNAK_EN_AZ]
        cift = None
        for i in range(len(adaylar)):
            ozne = _olay_oznesi(adaylar[i], ozellik)
            if ozne is None:
                continue
            for j in range(i + 1, len(adaylar)):
                if _olay_oznesi(adaylar[j], ozellik) == ozne and _zamanca_yakin(adaylar[i], adaylar[j]):
                    cift = (adaylar[i], adaylar[j])
                    break
            if cift:
                break
        if cift is None:
            return satirlar, birlesmeler
        a, b = cift
        birlesmeler.append(cift)
        olaylar = [o for o in olaylar if o is not a and o is not b] + [_olay_sirasi(a + b)]


def olaylari_sec(ogeler: List[Ogeler], simdi: datetime, adet: int = 6) -> List[dict]:
    """Penceredeki ogelerden Gundem ogelerini secer (bkz. modul belgesi, Secim)."""
    sirali = sorted(penceredeki(ogeler, simdi), key=_anahtar)
    ozellik_listesi = _baslik_ozellikleri(sirali)
    ozellik = {_anahtar(o): oz for o, oz in zip(sirali, ozellik_listesi)}
    satirlar, _ = _secip_birlestir(_grupla(sirali, ozellik_listesi), simdi, adet, ozellik)
    return [
        _olay_ozeti([kayit], simdi, kayit) if dolgu else _olay_ozeti(olay, simdi, kayit)
        for olay, kayit, dolgu in satirlar
    ]
