"""Gemini API ile kayit duzeyinde ceviri (spec 2026-09-15-gemini-yukseltme, bolum 3.2).

Yalnizca retranslate kullanir. Kayit basina TEK istek: cevrilecek alanlar JSON
olarak gider, ayni anahtarlarla Turkce doner. Kota korumasi:
  - Redis paylasimli aralik kapisi: istekler arasi en az GEMINI_MIN_INTERVAL sn
  - Gunluk istek butcesi (GEMINI_DAILY_BUDGET): istek ONCESI artar, 4xx'te geri alinir
  - 429 / 5xx / ag hatasi -> GEMINI_COOLDOWN sn devre kesici
  - 401 / 403 / 404 (anahtar, yetki, model) ve gecersiz anahtar / hesap sorunu bildiren 400
    (API_KEY_INVALID, FAILED_PRECONDITION...) -> devre kesici, butce geri alinir
  - Beklenmeyen istisna (kod hatasi) -> devre kesici
Hicbir istisna disari cikmaz; cevrilemeyen kayit icin None doner.
XTRM yer tutucu korumasi ve turkish_post_process uygulanmaz: terimler prompt'la korunur.

paket_cevir (spec 2026-11-02-ceviri-yayma G5): ayni kota kurallariyla TEK istekte birden cok kayit
(kimlik -> alanlar). Butce istek basina sayilir; dogrulama kayit basina yapilir.

Yedek zincir (spec 2026-11-02-ceviri-yayma G6): kota/HTTP kurallari ve paket akisi KayitCevirmeni
tabanindadir; GeminiCevirmen(model, onek) her model icin kendi kapisini, devre kesicisini ve sayacini
(<onek>:budget:<Pasifik gunu>) kullanir. Modul fonksiyonlari (hazir, kaydi_cevir, paket_cevir,
butce_ozeti...) birincil model BIRINCIL'in (onek 'gemini') ince sarmalayicisidir; BIRINCIL durumunu
modul globallerinden (_gate, _butce, GEMINI_*) okur. Diger cevirmenler: kayit_cevirmenleri.
"""
import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional, Set
from zoneinfo import ZoneInfo

import requests
from django.conf import settings

from . import translation_utils as tu
import logging

log = logging.getLogger(__name__)

PASIFIK = ZoneInfo('America/Los_Angeles')  # Google RPD kotasi bu saat diliminde sifirlanir

GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')
GEMINI_TIMEOUT = float(os.environ.get('GEMINI_TIMEOUT', '60'))
GEMINI_MIN_INTERVAL = float(os.environ.get('GEMINI_MIN_INTERVAL', '5'))   # 15 RPM'in altinda kal
# 500 RPD'nin altinda kal (50 guvenlik payi). Tum bolumler tek tavani paylasir: CVE rezervi
# (ADR-0005) 2026-11-02'de kalkti; oncelik retranslate.BOLUMLER sirasiyla verilir.
GEMINI_DAILY_BUDGET = int(os.environ.get('GEMINI_DAILY_BUDGET', '450'))
GEMINI_COOLDOWN = int(os.environ.get('GEMINI_COOLDOWN', '600'))
# Daha buyuk kayit 60 sn'de bitmiyor ve devre kesiciyi aciyor; LibreTranslate yolunda kalir
GEMINI_MAX_CHARS = int(os.environ.get('GEMINI_MAX_CHARS', '12000'))
# Paket sinirlari (G5): toplam karakter GEMINI_MAX_CHARS'in altinda kalir (60 sn zaman asimi)
GEMINI_BATCH_CHARS = int(os.environ.get('GEMINI_BATCH_CHARS', '10000'))
GEMINI_BATCH_MAX = int(os.environ.get('GEMINI_BATCH_MAX', '15'))
# Kayittan bagimsiz 4xx: 401 anahtar gecersiz, 403 yetki/proje, 404 model adi yanlis
SISTEMIK_HTTP = (401, 403, 404)
# 400 de sistemik olabilir: Generative Language API gecersiz/iptal/suresi dolmus anahtari
# 400 INVALID_ARGUMENT + details[].reason=API_KEY_INVALID ile, bazi hesap sorunlarini
# 400 FAILED_PRECONDITION ile doner. Kayit sucu sayilsa birikim bir gunde deneme tavanina ulasirdi.
SISTEMIK_DURUM = frozenset({'FAILED_PRECONDITION', 'PERMISSION_DENIED', 'UNAUTHENTICATED'})
SISTEMIK_SEBEP = frozenset({'API_KEY_INVALID'})
# Gecici sunucu hatalari ("This model is currently experiencing high demand" 503 vb.): devre kesici
# acilmadan once bu beklemelerle (sn) yeniden denenir; hepsi tukenirse devre kesici acilir. Sayac
# mantiksal istek basina bir kez artar (yeniden denemeler ayrica sayilmaz).
GECICI_HTTP = frozenset({500, 502, 503, 504})
GECICI_HATA_BEKLEMELERI = tuple(
    float(s) for s in os.environ.get('GEMINI_GECICI_BEKLEMELER', '5,15').split(',') if s.strip())


def _uyu(saniye: float) -> None:
    time.sleep(saniye)


def _gecici_ag_hatasi(hata: Exception) -> bool:
    """Baglanti kopmasi gecicidir; zaman asimi degildir (60 sn beklemeyi tekrarlamaya degmez)."""
    return isinstance(hata, requests.ConnectionError) and not isinstance(hata, requests.Timeout)
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
MAX_RATIO = 3.0
ECHO_MIN_WORDS = 4
# En az bu kadar kelimelik bir ceviride hic Turkce harf yoksa model ASCII'ye kaymistir (bkz. _alan_sorunu)
TURKCE_HARF_MIN_KELIME = 10
_TURKCE_HARF = re.compile('[çğıöşüÇĞİÖŞÜ]')
# Latin disi alfabeler (Kiril, Yunan, Ermeni, Ibrani, Arap, CJK, Hangul): orijinalde yoksa ceviride
# uydurulmustur (2026-10-21 canli olcum: 'sunarken' -> 'sերerken'). Orijinalde varsa (ozel ad) serbest.
_YABANCI_YAZI = re.compile('[Ͱ-ϿЀ-ӿ԰-֏֐-׿؀-ۿ'
                           '぀-ヿ一-鿿가-힯]')
# Paket capalari (bkz. _capalar): ceviride AYNEN kalmasi gereken belirtecler. Iki parcali ondalik
# (9.8) bilerek yok: Turkce '9,8' yazilabilir.
_CAPA_DESENLERI = (
    re.compile(r'\bCVE-\d{4}-\d{4,}\b', re.IGNORECASE),
    re.compile(r'\bGHSA(?:-[0-9a-z]+)+', re.IGNORECASE),
    re.compile(r'`[^`\n]+`'),                                   # kod parcasi (ters tirnaklariyla)
    re.compile(r'\bv?\d+(?:\.\d+){2,}\b', re.IGNORECASE),        # 2.4.1, v1.31.0
    re.compile(r'\bv\d+\.\d+(?!\.?\d)', re.IGNORECASE),          # v1.31
)
_URL = re.compile(r'https?://\S+', re.IGNORECASE)
_URL_SONU = '.,;:!?)]}>\'"`'

# Proje kurali "kod ASCII Turkce" bu metne UYGULANMAZ: talimat modele gider ve model yazimini taklit
# eder. 2026-10-16'ya kadar diakritiksiz yazilmisti; Gemini cevirilerinin yarisi (CVE'de %53) Turkce
# karaktersiz geldi ('kimligi dogrulanmamis saldirgan'). Ornekler ve kural bu yuzden duzgun Turkcedir.
# Terim sozlugu (2026-11-07 inceleme): ayni terim kayittan kayda farkli cevriliyordu ('zafiyet' / 'güvenlik
# açığı' / 'kırılganlık', 'istismar' / 'sömürü'). Yazilim akisi terimleri Ingilizce kalir; LibreTranslate
# icin translation_utils.TRANSLATION_FIXES'in zorladigiyla ayni (depo -> repository, kabuk -> shell).
_TERIM_SOZLUGU = (
    "- Terimleri her kayıtta aynı karşılıkla çevir: vulnerability -> güvenlik açığı; exploit -> istismar "
    "(fiil: istismar etmek); privilege escalation -> yetki yükseltme; denial of service -> hizmet reddi (DoS); "
    "cross-site scripting -> siteler arası betik çalıştırma (XSS); SQL injection -> SQL enjeksiyonu; "
    "path traversal -> dizin geçişi; arbitrary code execution -> keyfi kod çalıştırma; buffer overflow -> "
    "arabellek taşması; out-of-bounds read/write -> sınır dışı okuma/yazma; authentication bypass -> kimlik "
    "doğrulamayı atlatma; patch -> yama; deprecated -> kullanımdan kaldırılmış.\n"
    "- Şu yazılım terimlerini İngilizce bırak: commit, branch, merge, pull request, pipeline, repository, "
    "shell, stack, gateway, pod, namespace, container, cluster, use-after-free.\n"
)
_TALIMAT_GOVDESI = (
    "Sen teknik haber ve güvenlik bültenleri çeviren bir çevirmensin. Verilen JSON nesnesindeki "
    "her alanın İngilizce metnini doğal ve anlaşılır Türkçeye çevir; aynı anahtarlarla bir JSON nesnesi döndür.\n"
    "Kurallar:\n"
    "- Çeviriyi mutlaka Türkçe karakterlerle yaz (ç, ğ, ı, İ, ö, ş, ü); harfleri ASCII karşılıklarına "
    "(c, g, i, o, s, u) dönüştürme.\n"
    "- Teknik terimleri, ürün/kütüphane/şirket/kişi adlarını, kod parçalarını, dosya yollarını, fonksiyon "
    "adlarını, CVE numaralarını, sürüm ve commit numaralarını AYNEN bırak; Türkçe ek getirmek dışında değiştirme.\n"
    "- Satır sonlarını, madde işaretlerini, numaralandırmayı ve '===SECTION:' gibi yapısal işaretleri "
    "olduğu gibi koru.\n"
    "- Kubernetes changelog'larında '===SECTION: ...===', '---ITEM---' ve '<<<PR#...|...|...>>>' "
    "satırlarını birebir koru; sayılarını ve sırasını değiştirme.\n"
    "- Özetleme, ekleme, yorum yapma; metnin tamamını çevir.\n"
    "- Güvenlik terimlerini teknik anlamıyla çevir (örn. 'unauthenticated attacker' -> "
    "'kimliği doğrulanmamış saldırgan', 'remote code execution' -> 'uzaktan kod çalıştırma').\n"
    + _TERIM_SOZLUGU
)
_TALIMAT_SONU = "- Yalnızca JSON döndür."
SISTEM_TALIMATI = _TALIMAT_GOVDESI + _TALIMAT_SONU
# Paket talimati ayridir: tek kayit yolunun girdisi kimlik anahtarli degil, onun talimati degismez
PAKET_KURALI = (
    "- Girdi, kimlik anahtarlı kayıtlardan oluşan bir JSON nesnesidir; her kaydı ayrı çevir, aynı kimlik "
    "ve alan anahtarlarıyla döndür. Kayıtları birleştirme, sırasını ya da kimliğini değiştirme.\n"
)
PAKET_TALIMATI = _TALIMAT_GOVDESI + PAKET_KURALI + _TALIMAT_SONU

_gate = None
_butce = None


def _anahtar() -> str:
    return (getattr(settings, 'GEMINI_API_KEY', '') or '').strip()


def _redis_client():
    try:
        from django_redis import get_redis_connection
        client = get_redis_connection('default')
        client.ping()
        return client
    except Exception:
        return None


# Redis'e ulasilamayinca kurulan yerel yedek (kapi ve sayac) bu kadar sn sonra Redis'i yeniden dener
# (2026-11-07 inceleme): once yedek kalici kaliyordu; Redis donse de her worker sureci kendi sayaciyla
# gunluk butcenin tamamini harcayabiliyordu. Yalniz yedek olarak kurulan nesneler (yedek=True) yeniden
# denenir; testlerin verdigi yerel nesneler etkilenmez.
REDIS_YENIDEN_DENEME_SN = 60


def _yedek_kur(nesne):
    nesne.yedek = True
    nesne.kurulma = time.monotonic()
    return nesne


def _yedek_suresi_doldu(nesne) -> bool:
    return (getattr(nesne, 'yedek', False)
            and time.monotonic() - nesne.kurulma >= REDIS_YENIDEN_DENEME_SN)


def _kapi_kur(mevcut, prefix: str):
    """Redis varsa paylasilan kapi; yoksa yerel yedek (mevcut yedek varsa korunur, sayaci yeniden baslar)."""
    client = _redis_client()
    if client is not None:
        return tu._RedisGate(client, prefix=prefix)
    return _yedek_kur(mevcut if mevcut is not None else tu._LocalGate())


def _sayac_kur(mevcut, prefix: str, ttl: int):
    """Redis varsa paylasilan sayac; yoksa yerel yedek. Yedekten Redis'e donerken yedegin saydigi istekler
    Redis sayacina eklenir: kesinti suresince harcanan butce kaybolmaz."""
    client = _redis_client()
    if client is None:
        return _yedek_kur(mevcut if mevcut is not None else _LocalButce())
    sayac = _RedisButce(client, prefix=prefix, ttl=ttl)
    for anahtar, miktar in (getattr(mevcut, 'sayaclar', None) or {}).items():
        if miktar:
            sayac.artir(anahtar, miktar)
    return sayac


def _get_gate():
    """Aralik kapisi + devre kesici; Redis varsa tum worker'larda paylasilir."""
    global _gate
    if _gate is None or _yedek_suresi_doldu(_gate):
        _gate = _kapi_kur(_gate, 'gemini')
    return _gate


class _LocalButce:
    """Tek surec icin sayac (Redis yoksa ve testlerde)."""

    def __init__(self):
        self.sayaclar = {}

    def artir(self, anahtar: str, miktar: int = 1) -> int:
        self.sayaclar[anahtar] = self.sayaclar.get(anahtar, 0) + miktar
        return self.sayaclar[anahtar]

    def azalt(self, anahtar: str, miktar: int = 1) -> None:
        self.sayaclar[anahtar] = max(self.sayaclar.get(anahtar, 0) - miktar, 0)

    def oku(self, anahtar: str) -> int:
        return self.sayaclar.get(anahtar, 0)


class _RedisButce:
    """Tum worker sureclerinin paylastigi sayac; anahtar ttl sn (gunluk sayacta 48 saat) sonra
    kendiliginden silinir. miktar: istek basina 1 ya da (DeepL) karakter sayisi."""

    def __init__(self, client, prefix: str = 'gemini', ttl: int = 48 * 3600):
        self.client = client
        self.prefix = prefix
        self.ttl = ttl

    def _tam(self, anahtar: str) -> str:
        return f'{self.prefix}:{anahtar}'

    def artir(self, anahtar: str, miktar: int = 1) -> int:
        tam = self._tam(anahtar)
        deger = int(self.client.incrby(tam, miktar))
        if deger == miktar:
            self.client.expire(tam, self.ttl)
        return deger

    def azalt(self, anahtar: str, miktar: int = 1) -> None:
        self.client.decrby(self._tam(anahtar), miktar)

    def oku(self, anahtar: str) -> int:
        return int(self.client.get(self._tam(anahtar)) or 0)


def _get_butce():
    global _butce
    if _butce is None or _yedek_suresi_doldu(_butce):
        _butce = _sayac_kur(_butce, 'gemini', 48 * 3600)
    return _butce


def butce_anahtari() -> str:
    """Google RPD kotasi Pasifik gece yarisinda sifirlanir; anahtar o gune gore."""
    return f'budget:{datetime.now(PASIFIK):%Y-%m-%d}'


# --- Birincil modelin modul arayuzu (retranslate, views ve testler bunlari kullanir) ---

def butce_kullanimi() -> int:
    return BIRINCIL.butce_kullanimi()


def butce_tavani() -> int:
    """Gunluk istek tavani; sayac tum bolumler ve worker'lar arasinda paylasilir."""
    return GEMINI_DAILY_BUDGET


def butce_var() -> bool:
    return BIRINCIL.butce_var()


def hazir() -> bool:
    """Anahtar dolu, devre kesici kapali ve gunluk butce var mi. Redis erisilemezse False."""
    return BIRINCIL.hazir()


def butce_ozeti() -> dict:
    """Anonim /api/saglik/ icin butce ozeti; ASLA firlatmaz ve anahtar/kimlik bilgisi icermez."""
    return BIRINCIL.butce_ozeti()


def _devre_kesici(sebep: str) -> None:
    BIRINCIL._devre_kesici(sebep)


def _sistemik_hata(yanit) -> Optional[str]:
    """200 disi yanit kayittan bagimsiz mi (anahtar/yetki/hesap/model). Sebep metni ya da None.

    Govde JSON olmayabilir ya da beklenmedik sekilde olabilir; ASLA firlatmaz."""
    if yanit.status_code in SISTEMIK_HTTP:
        return f'HTTP {yanit.status_code}'
    try:
        hata = json.loads(yanit.text).get('error')
        durum = hata.get('status')
        if isinstance(durum, str) and durum in SISTEMIK_DURUM:
            return f'HTTP {yanit.status_code} {durum}'
        for ayrinti in hata.get('details') or ():
            sebep = ayrinti.get('reason') if isinstance(ayrinti, dict) else None
            if isinstance(sebep, str) and sebep in SISTEMIK_SEBEP:
                return f'HTTP {yanit.status_code} {sebep}'
    except Exception:  # JSON degil / dict degil / details liste degil: kayda ozgu sayilir
        return None
    return None


def _kelime_sayisi(metin: str) -> int:
    return len(re.findall(r'[^\W\d_]{2,}', metin))


def _alan_sorunu(orijinal: str, ceviri) -> Optional[str]:
    """Alan cevirisinin guvenilir olup olmadigi; sorun varsa kisa aciklama."""
    if not isinstance(ceviri, str) or not ceviri.strip():
        return 'bos'
    oran = len(ceviri) / max(len(orijinal), 1)
    if oran < tu.MIN_RATIO or oran > MAX_RATIO:
        return f'oran {oran:.2f}'
    if (_kelime_sayisi(orijinal) >= ECHO_MIN_WORDS
            and tu._normalize_for_echo(ceviri) == tu._normalize_for_echo(orijinal)):
        return 'yanki'
    if _kelime_sayisi(ceviri) >= TURKCE_HARF_MIN_KELIME and not _TURKCE_HARF.search(ceviri):
        # Bu uzunlukta duzgun Turkce metin bu harflerden en az birini icerir; hic yoksa model ASCII'ye kaymistir
        return 'turkce harf yok'
    yabanci = set(_YABANCI_YAZI.findall(ceviri)) - set(_YABANCI_YAZI.findall(orijinal))
    if yabanci:
        return 'yabanci alfabe'
    return None


def _alan_semasi(alanlar) -> dict:
    """Alan adlari -> STRING; hepsi zorunlu."""
    return {
        'type': 'OBJECT',
        'properties': {ad: {'type': 'STRING'} for ad in alanlar},
        'required': list(alanlar),
    }


def _paket_semasi(kayitlar: Dict[str, Dict[str, str]]) -> dict:
    """Her kimlik icin ic ice OBJECT (kendi alanlariyla); kimlikler ve alanlar zorunlu."""
    return {
        'type': 'OBJECT',
        'properties': {kimlik: _alan_semasi(alanlar) for kimlik, alanlar in kayitlar.items()},
        'required': list(kayitlar),
    }


def _istek_govdesi(veri: dict, sema: dict, talimat: str) -> dict:
    return {
        'systemInstruction': {'parts': [{'text': talimat}]},
        'contents': [{'role': 'user', 'parts': [{'text': json.dumps(veri, ensure_ascii=False)}]}],
        'generationConfig': {
            'temperature': 0.2,
            'responseMimeType': 'application/json',
            'responseSchema': sema,
        },
    }


def _istek_at(govde: dict, etiket: str = 'genel kaydi', kayit_sayisi: int = 1) -> Optional[requests.Response]:
    """Birincil modelle kota kurallariyla tek istek (bkz. KayitCevirmeni._istek_at)."""
    return BIRINCIL._istek_at(govde, etiket, kayit_sayisi)


def _aday_ciktisi(yanit, log_adi: str = 'Gemini'):
    """(cikti, finishReason). cikti None: yanit tamamlanmadi ya da JSON nesnesi cozulemedi. ASLA firlatmaz.
    log_adi yalniz log icindir (ikinci model kendi adiyla loglar)."""
    sebep = None
    try:
        aday = yanit.json()['candidates'][0]
        sebep = aday.get('finishReason')
        if sebep not in (None, 'STOP'):
            log.warning(f"  [{log_adi}] yanit tamamlanmadi ({sebep}).")
            return None, sebep
        cikti = json.loads(aday['content']['parts'][0]['text'])
    except Exception as hata:  # ValueError/KeyError/IndexError/TypeError/AttributeError vb.
        log.warning(f"  [{log_adi}] yanit cozulemedi ({type(hata).__name__}).")
        return None, sebep
    if not isinstance(cikti, dict):
        log.warning(f"  [{log_adi}] yanit JSON nesnesi degil.")
        return None, sebep
    return cikti, sebep


def _yaniti_coz(yanit) -> Optional[dict]:
    return _aday_ciktisi(yanit)[0]


def _dolu_alanlar(alanlar) -> Dict[str, str]:
    if not isinstance(alanlar, dict):
        return {}
    return {ad: metin for ad, metin in alanlar.items() if isinstance(metin, str) and metin.strip()}


def _kayit_cevirisi(alanlar: Dict[str, str], cikti: dict, onek: str = '',
                    log_adi: str = 'Gemini') -> Optional[Dict[str, str]]:
    """Kaydin tum alanlari dogrulamadan gecerse cevirileri (hepsi ya da hicbiri), yoksa None.
    Istenmeyen alanlar yok sayilir. onek ve log_adi yalniz log icindir (paket kimligi, saglayici)."""
    sonuc = {}
    for ad, orijinal in alanlar.items():
        sorun = _alan_sorunu(orijinal, cikti.get(ad)) or _eksik_capa(orijinal, cikti[ad])
        if sorun:
            log.warning(f"  [{log_adi}] dogrulama basarisiz ({onek}{ad}: {sorun}).")
            return None
        sonuc[ad] = cikti[ad].strip()
    return sonuc


def _eksik_capa(orijinal: str, ceviri: str) -> Optional[str]:
    """Alanin her capasi (CVE/GHSA kimligi, URL, kod parcasi, surum) ceviride aynen var mi; yoksa sebep.
    Tek kayit yolunda capraz denetim yoktu: model bir surumu ya da CVE numarasini degistirse ceviri
    yaziliyordu. Kod parcasinda ters tirnak zorunlu degil (model tirnaksiz yazabilir); icerigi aranir.
    Duz alt dize testi: Turkce ek kesmeden sonra gelir ('2.4.1'den')."""
    metin = ceviri.upper()
    eksik = [capa for capa in _capalar(orijinal) if capa.strip('`') not in metin]
    return f'capa kayip ({len(eksik)})' if eksik else None


def _capalar(metin: str) -> Set[str]:
    """Ceviride aynen kalmasi gereken belirtecler, buyuk harfe normalize: CVE/GHSA kimlikleri, URL'ler
    (sondaki noktalama atilir), ters tirnakli kod parcalari, >=3 parcali ya da v onekli surumler."""
    capalar = {eslesme.upper() for desen in _CAPA_DESENLERI for eslesme in desen.findall(metin)}
    capalar.update(url.rstrip(_URL_SONU).upper() for url in _URL.findall(metin))
    capalar.discard('')
    return capalar


def _gecis_araliklari(metin: str, capalar: Set[str]) -> list:
    """Capalarin metindeki tum gecislerinin [bas, son) araliklari."""
    araliklar = []
    for capa in capalar:
        bas = metin.find(capa)
        while bas != -1:
            araliklar.append((bas, bas + len(capa)))
            bas = metin.find(capa, bas + 1)
    return araliklar


def _acikta_geciyor(metin: str, capa: str, maskeli: list) -> bool:
    """capa metinde, tamami maskeli bir araligin icinde kalmayan bir gecisle var mi."""
    bas = metin.find(capa)
    while bas != -1:
        son = bas + len(capa)
        if not any(m_bas <= bas and son <= m_son for m_bas, m_son in maskeli):
            return True
        bas = metin.find(capa, bas + 1)
    return False


def _capa_sorunu(capalar: Dict[str, Set[str]], kimlik: str, ceviri: str) -> Optional[str]:
    """Paket icinde kimlik karismasi: ceviri baska kaydin capasini tasiyor ya da (>=2 capali kayitta)
    kendi capalarinin hicbirini tasimiyor. Ayni bicimli yer degisimini _alan_sorunu yakalayamaz.
    Duz alt dize testi: Turkce ek kesmeden sonra gelir ('2.4.1'den')."""
    kendi = capalar[kimlik]
    metin = ceviri.upper()
    kendi_araliklari = _gecis_araliklari(metin, kendi)
    for diger, onlarin in capalar.items():
        if diger == kimlik:
            continue
        for capa in onlarin - kendi:
            # Yalniz kendi capasinin icinde kalan gecis (1.2.3.4 icindeki 1.2.3) karisma sayilmaz;
            # kendi capasini asan gecis (kendi 1.2.3, metinde 1.2.3.4) sayilir
            if _acikta_geciyor(metin, capa, kendi_araliklari):
                return f'capa karisti ({diger} kaydinin capasi)'
    if len(kendi) >= 2 and not any(capa in metin for capa in kendi):
        return 'capalar kayip'
    return None


def kaydi_cevir(alanlar: Dict[str, str], bolum: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Kaydin cevrilecek alanlarini tek istekle cevirir. None: cevrilemedi (sebep loglandi).

    bolum yalniz log metni icindir; tavan tum bolumler icin aynidir."""
    return BIRINCIL.kaydi_cevir(alanlar, bolum)


@dataclass
class PaketSonucu:
    """paket_cevir sonucu.

    istek_hatasi: istek gitmedi (hazir degil / butce) ya da istek duzeyinde basarisiz oldu (ag, 429,
      5xx, 200 disi yanit); hicbir kaydin sucu degil.
    kesildi: yanit MAX_TOKENS ile yarim kaldi; paket boyu sorunudur (cagiran bolup yeniden dener).
    yanit_bozuk: yanitin tamami kullanilamaz (SAFETY/RECITATION vb. tamamlanmamis, cozulemeyen ya da
      nesne olmayan JSON); sucun hangi kayitta oldugu bilinmez (cagiran bolup yeniden dener, tek
      kayitta o kaydin icerik hatasidir).
    Bu ucunden biri True ise ceviriler ve reddedilen bostur. Hepsi False ise her girdi kimligi
    ya ceviriler'de ya reddedilen'dedir (icerik hatasi: dogrulama, eksik kimlik, capa karismasi)."""
    ceviriler: Dict[str, Dict[str, str]] = field(default_factory=dict)
    reddedilen: Set[str] = field(default_factory=set)
    istek_hatasi: bool = False
    kesildi: bool = False
    yanit_bozuk: bool = False


def paket_cevir(kayitlar: Dict[str, Dict[str, str]], bolum: Optional[str] = None) -> PaketSonucu:
    """Birden cok kaydi TEK istekte cevirir (spec G5). Anahtarlar kimlik ('k0', 'k1'...), degerler
    alanlar ({'title': ..., 'description': ...}). Butce istek basina bir artar.

    Bos alanlar istege girmez; tum alanlari bos kayit gonderilmez ve reddedilir. Modelin kimligi
    dusurdugu, nesne olmayan deger dondurdugu ya da bir alani dogrulamadan gecemeyen kayit yalniz
    kendisi reddedilir; digerleri cevrilir. Ayni bicimli yer degisimi icin capa capraz denetimi
    (_capa_sorunu): cevirisi baska kaydin CVE/GHSA/URL/kod/surum capasini tasiyan ya da >=2 capali
    olup hicbirini tasimayan kayit reddedilir; capasiz kayitlar etkilenmez.
    finishReason MAX_TOKENS -> kesildi; diger tamamlanmamis
    (SAFETY vb.) ya da cozulemeyen yanit -> yanit_bozuk (tek bir kayit tum paketi yakmasin; cagiran
    boler). Hicbir istisna disari cikmaz."""
    return BIRINCIL.paket_cevir(kayitlar, bolum)


def paketi_ayir(kayitlar: Dict[str, Dict[str, str]]):
    """(gonderilecek, bos): bos alanlari atilmis kayitlar ve hicbir alani dolu olmayan kimlikler."""
    gonderilecek, bos = {}, set()
    for kimlik, alanlar in kayitlar.items():
        dolu = _dolu_alanlar(alanlar)
        if dolu:
            gonderilecek[kimlik] = dolu
        else:
            bos.add(kimlik)
    return gonderilecek, bos


def paket_ciktisini_dogrula(gonderilecek: Dict[str, Dict[str, str]], bos: Set[str], cikti: dict,
                            log_adi: str = 'Gemini') -> PaketSonucu:
    """Cozulmus paket ciktisini (kimlik -> alanlar) kayit basina dogrular; tum saglayicilar icin ortak.

    Kimligi yanitta olmayan, nesne olmayan ya da bir alani _alan_sorunu'ndan gecemeyen kayit yalniz
    kendisi reddedilir. Sonra capa capraz denetimi (_capa_sorunu): kimlik karismasi olan kayit reddedilir."""
    sonuc = PaketSonucu(reddedilen=set(bos))
    for kimlik, alanlar in gonderilecek.items():
        deger = cikti.get(kimlik)
        if not isinstance(deger, dict):
            log.warning(f"  [{log_adi}] dogrulama basarisiz ({kimlik}: "
                        f"{'yanitta yok' if deger is None else 'nesne degil'}).")
            sonuc.reddedilen.add(kimlik)
            continue
        ceviri = _kayit_cevirisi(alanlar, deger, f'{kimlik}/', log_adi)
        if ceviri is None:
            sonuc.reddedilen.add(kimlik)
        else:
            sonuc.ceviriler[kimlik] = ceviri

    # Capa capraz denetimi: tum paketin orijinalleri burada elde; reddedilenlerin capalari da sayilir
    capalar = {kimlik: _capalar('\n'.join(alanlar.values())) for kimlik, alanlar in gonderilecek.items()}
    for kimlik, ceviri in list(sonuc.ceviriler.items()):
        sorun = _capa_sorunu(capalar, kimlik, '\n'.join(ceviri.values()))
        if sorun:
            log.warning(f"  [{log_adi}] dogrulama basarisiz ({kimlik}: {sorun}).")
            del sonuc.ceviriler[kimlik]
            sonuc.reddedilen.add(kimlik)
    return sonuc


class KayitCevirmeni:
    """Kayit duzeyi cevirmen tabani (spec 2026-11-02-ceviri-yayma G6). Arayuz: name (DB degeri),
    hazir(), kaydi_cevir(), paket_cevir(), butce_ozeti(). Hicbir istisna disari cikmaz.

    Ortak kurallar: kendi aralik kapisi + devre kesicisi (<onek>:slot / <onek>:cooldown) ve sayaci
    (<onek>:<_donem_anahtari()>); sayac istek ONCESI miktar kadar artar (_istek_at). Dogrulama
    (_alan_sorunu, capa capraz denetimi) her saglayiciya aynen uygulanir.
    Alt sinif verir: _anahtar, _donem_anahtari, _istek_adresi, _basliklar, _govde, _cikti."""

    name = ''
    log_adi = ''
    donem = 'day'               # butce_ozeti()['period']
    donem_metni = 'gunluk'      # log metni
    sayac_ttl = 48 * 3600
    zaman_asimi = 60.0
    bekleme = 600               # devre kesici suresi (sn)
    kesici_http = frozenset({429})      # + tum 5xx: devre kesici, kota harcanmis sayilir
    sistemik_http = frozenset({401, 403, 404})  # kayittan bagimsiz: kota geri alinir + devre kesici

    def __init__(self, onek: str, tavan: int, aralik: float):
        self.onek = onek
        self._tavan = tavan
        self._aralik = aralik
        self._gate = None
        self._butce = None

    @property
    def _log(self):
        return logging.getLogger(type(self).__module__)

    # --- Durum ve ayarlar (birincil Gemini bunlari modul globallerine yonlendirir) ---

    def _kapi(self):
        if self._gate is None or _yedek_suresi_doldu(self._gate):
            self._gate = _kapi_kur(self._gate, self.onek)
        return self._gate

    def _sayac(self):
        if self._butce is None or _yedek_suresi_doldu(self._butce):
            self._butce = _sayac_kur(self._butce, self.onek, self.sayac_ttl)
        return self._butce

    def tavan(self) -> int:
        return self._tavan

    def aralik(self) -> float:
        return self._aralik

    def _anahtar(self) -> str:
        raise NotImplementedError

    def _donem_anahtari(self) -> str:
        raise NotImplementedError

    def _kullanilabilir(self) -> bool:
        """Ayar duzeyi on kosul (model adi vb.); anahtar dolu iken sorulur."""
        return True

    def _hazir_mi(self) -> bool:
        """kaydi_cevir / paket_cevir / butce_ozeti'nin sordugu hazirlik."""
        return self.hazir()

    # --- Istek bicimi (alt sinif) ---

    def _istek_adresi(self) -> str:
        raise NotImplementedError

    def _basliklar(self) -> dict:
        raise NotImplementedError

    def _govde(self, veri: dict, paket: bool):
        """(govde, baglam). veri: alanlar (tek kayit) ya da kimlik -> alanlar (paket)."""
        raise NotImplementedError

    def _miktar(self, govde: dict) -> int:
        """Istegin sayactan dusecegi miktar: varsayilan istek basina 1."""
        return 1

    def _cikti(self, yanit, veri: dict, paket: bool, baglam):
        """(cikti, kesildi). cikti: veri ile ayni bicimde ceviri sozlugu ya da None (kullanilamaz).
        kesildi: yanit uzunluk sinirinda yarim kaldi. ASLA firlatmaz."""
        raise NotImplementedError

    def _sistemik_hata(self, yanit) -> Optional[str]:
        return f'HTTP {yanit.status_code}' if yanit.status_code in self.sistemik_http else None

    def _kesici_yaniti(self, durum: int) -> None:
        """kesici_http / 5xx yaniti alindi, devre kesici acilmak uzere (DeepL 456: sayaci doldurur)."""

    # --- Kota ---

    def butce_kullanimi(self) -> int:
        return self._sayac().oku(self._donem_anahtari())

    def butce_var(self) -> bool:
        return self.butce_kullanimi() < self.tavan()

    def hazir(self) -> bool:
        """Anahtar dolu, on kosul tamam, devre kesici kapali ve sayac tavanin altinda. Redis erisilemezse False."""
        try:
            return (bool(self._anahtar()) and self._kullanilabilir()
                    and not self._kapi().cooldown_active() and self.butce_var())
        except Exception:
            return False

    def ayarli(self) -> bool:
        """Anahtar dolu ve ayar duzeyi on kosul tamam mi (model adi vb.); sayac/devre kesiciye bakmaz.
        /api/saglik/ yalniz ayarli yedegi listeler. ASLA firlatmaz."""
        try:
            return bool(self._anahtar()) and self._kullanilabilir()
        except Exception:
            return False

    def butce_ozeti(self) -> dict:
        """Anonim /api/saglik/ icin ozet; ASLA firlatmaz ve anahtar/kimlik bilgisi icermez.

        Redis erisilemezse used=0, available=False, cooldown=False doner (serit "bilinmiyor"u
        sessizce gosterir, saglik ucu 500 vermez)."""
        bos = {'used': 0, 'limit': self.tavan(), 'period': self.donem, 'available': False, 'cooldown': False}
        try:
            ozet = dict(bos, used=self.butce_kullanimi(), cooldown=bool(self._kapi().cooldown_active()))
            ozet['available'] = self._hazir_mi()
        except Exception:
            return bos
        return ozet

    def _gecici_hata_bekle(self, sebep: str, saniye: float, etiket: str) -> None:
        self._log.info(f"  [{self.log_adi}] gecici hata ({sebep}); {etiket} {saniye:g} sn sonra yeniden denenecek.")
        _uyu(saniye)

    def _devre_kesici(self, sebep: str) -> None:
        self._log.warning(f"  [{self.log_adi}] erisilemiyor ({sebep}); {self.bekleme} sn atlanacak.")
        self._kapi().start_cooldown(self.bekleme)

    def _istek_at(self, govde: dict, etiket: str = 'genel kaydi', kayit_sayisi: int = 1,
                  miktar: int = 1) -> Optional[requests.Response]:
        """Kota kurallariyla tek istek atar. 200 yanitini ya da None doner (sebep loglandi).

        hazir() kontrolu cagirana aittir. Sayac istek ONCESI miktar kadar artar; tavan asildiysa istek atilmaz.
        Gecici hata (GECICI_HTTP, baglanti kopmasi) -> GECICI_HATA_BEKLEMELERI ile yeniden denenir.
        kesici_http / 5xx / ag hatasi / beklenmeyen istisna -> devre kesici, sayac geri alinmaz.
        Diger 200 disi yanitlar -> sayac geri alinir; sistemikse (_sistemik_hata) devre kesici de acilir.
        etiket ve kayit_sayisi yalniz log icindir (kayit_sayisi >= 2 olan istegin 4xx'i WARNING)."""
        butce, anahtar = self._sayac(), self._donem_anahtari()
        if butce.artir(anahtar, miktar) > self.tavan():
            butce.azalt(anahtar, miktar)
            if miktar > 1:
                # Miktar karakterse (DeepL) donemin kalani bu istege yetmedi. Sayac geri alinip birakilirsa
                # hazir() True kalir ve retranslate istek atilmayan saglam kayitlari icerik hatasi sayip
                # yukseltme kuyrugundan dusururdu. Sayac tavana doldurulur (456 gibi): hazir() donem
                # degisene kadar False, cagiran yeniden secer. Istek basina 1 (Gemini/OpenRouter) etkilenmez.
                eksik = self.tavan() - butce.oku(anahtar)
                if eksik > 0:
                    butce.artir(anahtar, eksik)
            self._log.warning(f"  [{self.log_adi}] {self.donem_metni} butce doldu ({self.tavan()}); "
                              f"{etiket} cevrilmedi.")
            return None

        beklemeler = tuple(GECICI_HATA_BEKLEMELERI)
        for deneme in range(len(beklemeler) + 1):
            self._kapi().wait_for_slot(self.aralik())
            try:
                yanit = requests.post(self._istek_adresi(), headers=self._basliklar(), json=govde,
                                      timeout=self.zaman_asimi)
            except requests.RequestException as hata:
                if deneme < len(beklemeler) and _gecici_ag_hatasi(hata):
                    self._gecici_hata_bekle(type(hata).__name__, beklemeler[deneme], etiket)
                    continue
                self._devre_kesici(type(hata).__name__)
                return None
            except Exception as hata:  # beklenmeyen hata retranslate'i durdurmasin
                # Kod hatasi her kayitta tekrarlar: kaydin sucu sayilmasin, devre kesici acilsin
                self._log.warning(f"  [{self.log_adi}] beklenmeyen hata: {type(hata).__name__}")
                self._devre_kesici(type(hata).__name__)
                return None
            if deneme < len(beklemeler) and yanit.status_code in GECICI_HTTP:
                # "high demand" 503 gibi gecici sunucu hatalari genelde saniyeler icinde gecer.
                # Hemen devre kesici acilirsa saatlik turun tamami bosa gider (2026-11-05: 12 tur).
                self._gecici_hata_bekle(f'HTTP {yanit.status_code}', beklemeler[deneme], etiket)
                continue
            break

        if yanit.status_code in self.kesici_http or yanit.status_code >= 500:
            self._kesici_yaniti(yanit.status_code)
            self._devre_kesici(f'HTTP {yanit.status_code}')
            return None
        if yanit.status_code != 200:
            butce.azalt(anahtar, miktar)  # 4xx: kota harcanmadi
            sistemik = self._sistemik_hata(yanit)
            if sistemik:
                # Anahtar iptal / yetki yok / hesap / model yok: her istek ayni yaniti alir. Devre kesici
                # acilmazsa hazir() True kalir ve retranslate her adayi icerik hatasi sayip
                # RETRANSLATE_MAX_ATTEMPTS turda tum yukseltme adaylarini kuyruktan dusururdu.
                self._devre_kesici(sistemik)
                return None
            # Kayda ozgu istek sorunu (400 gecersiz govde vb.): devre kesici acilmaz
            # Paket duzeyi 4xx (sema/govde cok buyuk vb.) gorunur olmali; tek kayitlik istek sessiz kalir
            self._log.log(logging.WARNING if kayit_sayisi >= 2 else logging.INFO,
                          f"  [{self.log_adi}] istek reddedildi (HTTP {yanit.status_code}): "
                          f"{str(yanit.text)[:200]}")
            return None
        return yanit

    # --- Ceviri ---

    def kaydi_cevir(self, alanlar: Dict[str, str], bolum: Optional[str] = None) -> Optional[Dict[str, str]]:
        """Kaydin cevrilecek alanlarini tek istekle cevirir. None: cevrilemedi (sebep loglandi)."""
        alanlar = _dolu_alanlar(alanlar)
        if not alanlar or not self._hazir_mi():
            return None
        govde, baglam = self._govde(alanlar, False)
        yanit = self._istek_at(govde, f"{bolum or 'genel'} kaydi", miktar=self._miktar(govde))
        if yanit is None:
            return None
        cikti, _ = self._cikti(yanit, alanlar, False, baglam)
        if cikti is None:
            return None
        return _kayit_cevirisi(alanlar, cikti, log_adi=self.log_adi)

    def paket_cevir(self, kayitlar: Dict[str, Dict[str, str]], bolum: Optional[str] = None) -> PaketSonucu:
        """Birden cok kaydi TEK istekte cevirir; kurallar ve sonuc bayraklari modul paket_cevir'deki gibi."""
        gonderilecek, bos = paketi_ayir(kayitlar)
        if not gonderilecek:
            return PaketSonucu(reddedilen=bos)
        if not self._hazir_mi():
            return PaketSonucu(istek_hatasi=True)

        etiket = f"{bolum or 'genel'} paketi ({len(gonderilecek)} kayit)"
        govde, baglam = self._govde(gonderilecek, True)
        yanit = self._istek_at(govde, etiket, len(gonderilecek), self._miktar(govde))
        if yanit is None:
            return PaketSonucu(istek_hatasi=True)
        cikti, kesildi = self._cikti(yanit, gonderilecek, True, baglam)
        if kesildi:
            return PaketSonucu(kesildi=True)
        if cikti is None:
            return PaketSonucu(yanit_bozuk=True)
        return paket_ciktisini_dogrula(gonderilecek, bos, cikti, self.log_adi)


class GeminiCevirmen(KayitCevirmeni):
    """Bir Gemini modeli. Google kotasi model basinadir: her model kendi kapisi, devre kesicisi ve
    gunluk sayaciyla (<onek>:budget:<Pasifik gunu>) calisir; anahtar (GEMINI_API_KEY) ortaktir.
    DB'ye iki model de 'gemini' olarak yazilir; model ayrimi log ve sayactadir."""

    name = 'gemini'

    def __init__(self, model: str, onek: str = 'gemini', tavan: Optional[int] = None,
                 aralik: Optional[float] = None):
        super().__init__(onek, GEMINI_DAILY_BUDGET if tavan is None else tavan,
                         GEMINI_MIN_INTERVAL if aralik is None else aralik)
        self.model = (model or '').strip()
        self.log_adi = 'Gemini' if onek == 'gemini' else f'Gemini-2 {self.model}'

    @property
    def zaman_asimi(self):
        return GEMINI_TIMEOUT

    @property
    def bekleme(self):
        return GEMINI_COOLDOWN

    def model_adi(self) -> str:
        return self.model

    def _anahtar(self) -> str:
        return _anahtar()

    def _kullanilabilir(self) -> bool:
        return bool(self.model_adi())

    def _donem_anahtari(self) -> str:
        return butce_anahtari()

    def _istek_adresi(self) -> str:
        return GEMINI_URL.format(model=self.model_adi())

    def _basliklar(self) -> dict:
        return {'x-goog-api-key': self._anahtar(), 'Content-Type': 'application/json'}

    def _govde(self, veri: dict, paket: bool):
        if paket:
            return _istek_govdesi(veri, _paket_semasi(veri), PAKET_TALIMATI), None
        return _istek_govdesi(veri, _alan_semasi(veri), SISTEM_TALIMATI), None

    def _cikti(self, yanit, veri: dict, paket: bool, baglam):
        cikti, sebep = _aday_ciktisi(yanit, self.log_adi)
        return cikti, sebep == 'MAX_TOKENS'

    def _sistemik_hata(self, yanit) -> Optional[str]:
        return _sistemik_hata(yanit)


class _BirincilGemini(GeminiCevirmen):
    """GEMINI_MODEL, onek 'gemini'. Durumu ve ayarlari her cagrida modul globallerinden okur: cagiranlar
    ve testlerin yamalari (gemini._gate, gemini._butce, GEMINI_DAILY_BUDGET, GEMINI_MIN_INTERVAL,
    gemini.hazir) bugunku gibi etkili kalir; Redis anahtarlari degismez (gemini:budget:<gun>)."""

    def __init__(self):
        super().__init__(GEMINI_MODEL, onek='gemini')

    def model_adi(self) -> str:
        return GEMINI_MODEL

    def _kapi(self):
        return _get_gate()

    def _sayac(self):
        return _get_butce()

    def tavan(self) -> int:
        return GEMINI_DAILY_BUDGET

    def aralik(self) -> float:
        return GEMINI_MIN_INTERVAL

    def _hazir_mi(self) -> bool:
        return hazir()  # modul fonksiyonu (yamalanabilir); o da KayitCevirmeni.hazir'i calistirir


BIRINCIL = _BirincilGemini()
