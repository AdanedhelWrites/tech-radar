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
"""
import json
import os
import re
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

# Proje kurali "kod ASCII Turkce" bu metne UYGULANMAZ: talimat modele gider ve model yazimini taklit
# eder. 2026-10-16'ya kadar diakritiksiz yazilmisti; Gemini cevirilerinin yarisi (CVE'de %53) Turkce
# karaktersiz geldi ('kimligi dogrulanmamis saldirgan'). Ornekler ve kural bu yuzden duzgun Turkcedir.
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


def _get_gate():
    """Aralik kapisi + devre kesici; Redis varsa tum worker'larda paylasilir."""
    global _gate
    if _gate is None:
        client = _redis_client()
        _gate = tu._RedisGate(client, prefix='gemini') if client else tu._LocalGate()
    return _gate


class _LocalButce:
    """Tek surec icin gunluk sayac (Redis yoksa ve testlerde)."""

    def __init__(self):
        self.sayaclar = {}

    def artir(self, anahtar: str) -> int:
        self.sayaclar[anahtar] = self.sayaclar.get(anahtar, 0) + 1
        return self.sayaclar[anahtar]

    def azalt(self, anahtar: str) -> None:
        self.sayaclar[anahtar] = max(self.sayaclar.get(anahtar, 0) - 1, 0)

    def oku(self, anahtar: str) -> int:
        return self.sayaclar.get(anahtar, 0)


class _RedisButce:
    """Tum worker sureclerinin paylastigi gunluk sayac; anahtar 48 saat sonra kendiliginden silinir."""

    def __init__(self, client, prefix: str = 'gemini'):
        self.client = client
        self.prefix = prefix

    def _tam(self, anahtar: str) -> str:
        return f'{self.prefix}:{anahtar}'

    def artir(self, anahtar: str) -> int:
        tam = self._tam(anahtar)
        deger = int(self.client.incr(tam))
        if deger == 1:
            self.client.expire(tam, 48 * 3600)
        return deger

    def azalt(self, anahtar: str) -> None:
        self.client.decr(self._tam(anahtar))

    def oku(self, anahtar: str) -> int:
        return int(self.client.get(self._tam(anahtar)) or 0)


def _get_butce():
    global _butce
    if _butce is None:
        client = _redis_client()
        _butce = _RedisButce(client) if client else _LocalButce()
    return _butce


def butce_anahtari() -> str:
    """Google RPD kotasi Pasifik gece yarisinda sifirlanir; anahtar o gune gore."""
    return f'budget:{datetime.now(PASIFIK):%Y-%m-%d}'


def butce_kullanimi() -> int:
    return _get_butce().oku(butce_anahtari())


def butce_tavani() -> int:
    """Gunluk istek tavani; sayac tum bolumler ve worker'lar arasinda paylasilir."""
    return GEMINI_DAILY_BUDGET


def butce_var() -> bool:
    return butce_kullanimi() < butce_tavani()


def hazir() -> bool:
    """Anahtar dolu, devre kesici kapali ve gunluk butce var mi. Redis erisilemezse False."""
    try:
        return bool(_anahtar()) and not _get_gate().cooldown_active() and butce_var()
    except Exception:
        return False


def butce_ozeti() -> dict:
    """Anonim /api/saglik/ icin butce ozeti; ASLA firlatmaz ve anahtar/kimlik bilgisi icermez.

    Redis erisilemezse used=0, available=False, cooldown=False doner (serit "bilinmiyor"u
    sessizce gosterir, saglik ucu 500 vermez).
    """
    ozet = {'used': 0, 'limit': butce_tavani(), 'period': 'day', 'available': False, 'cooldown': False}
    try:
        ozet['used'] = butce_kullanimi()
        ozet['cooldown'] = bool(_get_gate().cooldown_active())
        ozet['available'] = hazir()
    except Exception:
        return {'used': 0, 'limit': butce_tavani(), 'period': 'day', 'available': False, 'cooldown': False}
    return ozet


def _devre_kesici(sebep: str) -> None:
    log.warning(f"  [Gemini] erisilemiyor ({sebep}); {GEMINI_COOLDOWN} sn atlanacak.")
    _get_gate().start_cooldown(GEMINI_COOLDOWN)


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


def _istek_at(govde: dict, etiket: str = 'genel kaydi') -> Optional[requests.Response]:
    """Kota kurallariyla tek istek atar. 200 yanitini ya da None doner (sebep loglandi).

    hazir() kontrolu cagirana aittir. Butce istek ONCESI artar; tavan asildiysa istek atilmaz.
    429 / 5xx / ag hatasi / beklenmeyen istisna -> devre kesici, butce geri alinmaz.
    Diger 200 disi yanitlar -> butce geri alinir; sistemikse (_sistemik_hata) devre kesici de acilir.
    etiket yalniz log metni icindir."""
    butce, anahtar = _get_butce(), butce_anahtari()
    if butce.artir(anahtar) > butce_tavani():
        butce.azalt(anahtar)
        log.warning(f"  [Gemini] gunluk butce doldu ({butce_tavani()}); {etiket} cevrilmedi.")
        return None

    _get_gate().wait_for_slot(GEMINI_MIN_INTERVAL)
    try:
        yanit = requests.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={'x-goog-api-key': _anahtar(), 'Content-Type': 'application/json'},
            json=govde,
            timeout=GEMINI_TIMEOUT,
        )
    except requests.RequestException as hata:
        _devre_kesici(type(hata).__name__)
        return None
    except Exception as hata:  # beklenmeyen hata retranslate'i durdurmasin
        # Kod hatasi her kayitta tekrarlar: kaydin sucu sayilmasin, devre kesici acilsin
        log.warning(f"  [Gemini] beklenmeyen hata: {type(hata).__name__}")
        _devre_kesici(type(hata).__name__)
        return None

    if yanit.status_code == 429 or yanit.status_code >= 500:
        _devre_kesici(f'HTTP {yanit.status_code}')
        return None
    if yanit.status_code != 200:
        butce.azalt(anahtar)  # 4xx: kota harcanmadi
        sistemik = _sistemik_hata(yanit)
        if sistemik:
            # Anahtar iptal / yetki yok / hesap / model yok: her istek ayni yaniti alir. Devre kesici
            # acilmazsa hazir() True kalir ve retranslate her adayi icerik hatasi sayip
            # RETRANSLATE_MAX_ATTEMPTS turda tum yukseltme adaylarini kuyruktan dusururdu.
            _devre_kesici(sistemik)
            return None
        # Kayda ozgu istek sorunu (400 gecersiz govde vb.): devre kesici acilmaz
        log.info(f"  [Gemini] istek reddedildi (HTTP {yanit.status_code}): {str(yanit.text)[:200]}")
        return None
    return yanit


def _aday_ciktisi(yanit):
    """(cikti, finishReason). cikti None: yanit tamamlanmadi ya da JSON nesnesi cozulemedi. ASLA firlatmaz."""
    sebep = None
    try:
        aday = yanit.json()['candidates'][0]
        sebep = aday.get('finishReason')
        if sebep not in (None, 'STOP'):
            log.warning(f"  [Gemini] yanit tamamlanmadi ({sebep}).")
            return None, sebep
        cikti = json.loads(aday['content']['parts'][0]['text'])
    except Exception as hata:  # ValueError/KeyError/IndexError/TypeError/AttributeError vb.
        log.warning(f"  [Gemini] yanit cozulemedi ({type(hata).__name__}).")
        return None, sebep
    if not isinstance(cikti, dict):
        log.warning("  [Gemini] yanit JSON nesnesi degil.")
        return None, sebep
    return cikti, sebep


def _yaniti_coz(yanit) -> Optional[dict]:
    return _aday_ciktisi(yanit)[0]


def _dolu_alanlar(alanlar) -> Dict[str, str]:
    if not isinstance(alanlar, dict):
        return {}
    return {ad: metin for ad, metin in alanlar.items() if isinstance(metin, str) and metin.strip()}


def _kayit_cevirisi(alanlar: Dict[str, str], cikti: dict, onek: str = '') -> Optional[Dict[str, str]]:
    """Kaydin tum alanlari dogrulamadan gecerse cevirileri (hepsi ya da hicbiri), yoksa None.
    Istenmeyen alanlar yok sayilir. onek yalniz log icindir (paket kimligi)."""
    sonuc = {}
    for ad, orijinal in alanlar.items():
        sorun = _alan_sorunu(orijinal, cikti.get(ad))
        if sorun:
            log.warning(f"  [Gemini] dogrulama basarisiz ({onek}{ad}: {sorun}).")
            return None
        sonuc[ad] = cikti[ad].strip()
    return sonuc


def kaydi_cevir(alanlar: Dict[str, str], bolum: Optional[str] = None) -> Optional[Dict[str, str]]:
    """Kaydin cevrilecek alanlarini tek istekle cevirir. None: cevrilemedi (sebep loglandi).

    bolum yalniz log metni icindir; tavan tum bolumler icin aynidir."""
    alanlar = _dolu_alanlar(alanlar)
    if not alanlar or not hazir():
        return None
    yanit = _istek_at(_istek_govdesi(alanlar, _alan_semasi(alanlar), SISTEM_TALIMATI),
                      f"{bolum or 'genel'} kaydi")
    if yanit is None:
        return None
    cikti = _yaniti_coz(yanit)
    if cikti is None:
        return None
    return _kayit_cevirisi(alanlar, cikti)


@dataclass
class PaketSonucu:
    """paket_cevir sonucu.

    istek_hatasi: istek gitmedi (hazir degil / butce) ya da istek duzeyinde basarisiz oldu (ag, 429,
      5xx, 200 disi yanit); hicbir kaydin sucu degil.
    kesildi: yanit MAX_TOKENS ile yarim kaldi; paket boyu sorunudur (cagiran bolup yeniden dener).
    Bu ikisinden biri True ise ceviriler ve reddedilen bostur. Ikisi de False ise her girdi kimligi
    ya ceviriler'de ya reddedilen'dedir (icerik hatasi: dogrulama, eksik kimlik, cozulemeyen yanit)."""
    ceviriler: Dict[str, Dict[str, str]] = field(default_factory=dict)
    reddedilen: Set[str] = field(default_factory=set)
    istek_hatasi: bool = False
    kesildi: bool = False


def paket_cevir(kayitlar: Dict[str, Dict[str, str]], bolum: Optional[str] = None) -> PaketSonucu:
    """Birden cok kaydi TEK istekte cevirir (spec G5). Anahtarlar kimlik ('k0', 'k1'...), degerler
    alanlar ({'title': ..., 'description': ...}). Butce istek basina bir artar.

    Bos alanlar istege girmez; tum alanlari bos kayit gonderilmez ve reddedilir. Modelin kimligi
    dusurdugu, nesne olmayan deger dondurdugu ya da bir alani dogrulamadan gecemeyen kayit yalniz
    kendisi reddedilir; digerleri cevrilir. finishReason MAX_TOKENS -> kesildi; diger tamamlanmamis
    (SAFETY vb.) ya da cozulemeyen yanit -> tum kayitlar reddedilir. Hicbir istisna disari cikmaz."""
    gonderilecek, bos = {}, set()
    for kimlik, alanlar in kayitlar.items():
        dolu = _dolu_alanlar(alanlar)
        if dolu:
            gonderilecek[kimlik] = dolu
        else:
            bos.add(kimlik)
    if not gonderilecek:
        return PaketSonucu(reddedilen=bos)
    if not hazir():
        return PaketSonucu(istek_hatasi=True)

    etiket = f"{bolum or 'genel'} paketi ({len(gonderilecek)} kayit)"
    yanit = _istek_at(_istek_govdesi(gonderilecek, _paket_semasi(gonderilecek), PAKET_TALIMATI), etiket)
    if yanit is None:
        return PaketSonucu(istek_hatasi=True)
    cikti, sebep = _aday_ciktisi(yanit)
    if sebep == 'MAX_TOKENS':
        return PaketSonucu(kesildi=True)
    if cikti is None:
        return PaketSonucu(reddedilen=bos | set(gonderilecek))

    sonuc = PaketSonucu(reddedilen=bos)
    for kimlik, alanlar in gonderilecek.items():
        deger = cikti.get(kimlik)
        if not isinstance(deger, dict):
            log.warning(f"  [Gemini] dogrulama basarisiz ({kimlik}: "
                        f"{'yanitta yok' if deger is None else 'nesne degil'}).")
            sonuc.reddedilen.add(kimlik)
            continue
        ceviri = _kayit_cevirisi(alanlar, deger, f'{kimlik}/')
        if ceviri is None:
            sonuc.reddedilen.add(kimlik)
        else:
            sonuc.ceviriler[kimlik] = ceviri
    return sonuc
