"""Gemini API ile kayit duzeyinde ceviri (spec 2026-09-15-gemini-yukseltme, bolum 3.2).

Yalnizca retranslate kullanir. Kayit basina TEK istek: cevrilecek alanlar JSON
olarak gider, ayni anahtarlarla Turkce doner. Kota korumasi:
  - Redis paylasimli aralik kapisi: istekler arasi en az GEMINI_MIN_INTERVAL sn
  - Gunluk istek butcesi (GEMINI_DAILY_BUDGET): istek ONCESI artar, 4xx'te geri alinir
  - 429 / 5xx / ag hatasi -> GEMINI_COOLDOWN sn devre kesici
Hicbir istisna disari cikmaz; cevrilemeyen kayit icin None doner.
XTRM yer tutucu korumasi ve turkish_post_process uygulanmaz: terimler prompt'la korunur.
"""
import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, Optional

import requests
from django.conf import settings

from . import translation_utils as tu

GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')
GEMINI_TIMEOUT = float(os.environ.get('GEMINI_TIMEOUT', '60'))
GEMINI_MIN_INTERVAL = float(os.environ.get('GEMINI_MIN_INTERVAL', '5'))   # 15 RPM'in altinda kal
GEMINI_DAILY_BUDGET = int(os.environ.get('GEMINI_DAILY_BUDGET', '400'))   # 500 RPD'nin altinda kal
GEMINI_COOLDOWN = int(os.environ.get('GEMINI_COOLDOWN', '600'))
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
MAX_RATIO = 3.0
ECHO_MIN_WORDS = 4

SISTEM_TALIMATI = (
    "Sen teknik haber ve guvenlik bultenleri ceviren bir cevirmensin. Verilen JSON nesnesindeki "
    "her alanin Ingilizce metnini dogal ve anlasilir Turkceye cevir; ayni anahtarlarla bir JSON nesnesi dondur.\n"
    "Kurallar:\n"
    "- Teknik terimleri, urun/kutuphane/sirket/kisi adlarini, kod parcalarini, dosya yollarini, fonksiyon "
    "adlarini, CVE numaralarini, surum ve commit numaralarini AYNEN birak; Turkce ek getirmek disinda degistirme.\n"
    "- Satir sonlarini, madde isaretlerini, numaralandirmayi ve '===SECTION:' gibi yapisal isaretleri "
    "oldugu gibi koru.\n"
    "- Ozetleme, ekleme, yorum yapma; metnin tamamini cevir.\n"
    "- Guvenlik terimlerini teknik anlamiyla cevir (orn. 'unauthenticated attacker' -> "
    "'kimligi dogrulanmamis saldirgan', 'remote code execution' -> 'uzaktan kod calistirma').\n"
    "- Yalnizca JSON dondur."
)

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
    """UTC gune gore: Google kotasi da UTC'de sifirlanir."""
    return f'budget:{datetime.now(timezone.utc):%Y-%m-%d}'


def butce_kullanimi() -> int:
    return _get_butce().oku(butce_anahtari())


def butce_var() -> bool:
    return butce_kullanimi() < GEMINI_DAILY_BUDGET


def hazir() -> bool:
    return bool(_anahtar()) and not _get_gate().cooldown_active() and butce_var()


def _devre_kesici(sebep: str) -> None:
    print(f"  [Gemini] erisilemiyor ({sebep}); {GEMINI_COOLDOWN} sn atlanacak.")
    _get_gate().start_cooldown(GEMINI_COOLDOWN)


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
    return None


def _istek_govdesi(alanlar: Dict[str, str]) -> dict:
    return {
        'systemInstruction': {'parts': [{'text': SISTEM_TALIMATI}]},
        'contents': [{'role': 'user', 'parts': [{'text': json.dumps(alanlar, ensure_ascii=False)}]}],
        'generationConfig': {
            'temperature': 0.2,
            'responseMimeType': 'application/json',
            'responseSchema': {
                'type': 'OBJECT',
                'properties': {ad: {'type': 'STRING'} for ad in alanlar},
                'required': list(alanlar),
            },
        },
    }


def _yaniti_coz(yanit) -> Optional[dict]:
    try:
        aday = yanit.json()['candidates'][0]
        if aday.get('finishReason') not in (None, 'STOP'):
            print(f"  [Gemini] yanit tamamlanmadi ({aday.get('finishReason')}).")
            return None
        cikti = json.loads(aday['content']['parts'][0]['text'])
    except (ValueError, KeyError, IndexError, TypeError) as hata:
        print(f"  [Gemini] yanit cozulemedi ({type(hata).__name__}).")
        return None
    if not isinstance(cikti, dict):
        print("  [Gemini] yanit JSON nesnesi degil.")
        return None
    return cikti


def kaydi_cevir(alanlar: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Kaydin cevrilecek alanlarini tek istekle cevirir. None: cevrilemedi (sebep loglandi)."""
    alanlar = {ad: metin for ad, metin in alanlar.items() if isinstance(metin, str) and metin.strip()}
    if not alanlar or not hazir():
        return None

    butce, anahtar = _get_butce(), butce_anahtari()
    if butce.artir(anahtar) > GEMINI_DAILY_BUDGET:
        butce.azalt(anahtar)
        print(f"  [Gemini] gunluk butce doldu ({GEMINI_DAILY_BUDGET}).")
        return None

    _get_gate().wait_for_slot(GEMINI_MIN_INTERVAL)
    try:
        yanit = requests.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={'x-goog-api-key': _anahtar(), 'Content-Type': 'application/json'},
            json=_istek_govdesi(alanlar),
            timeout=GEMINI_TIMEOUT,
        )
    except requests.RequestException as hata:
        _devre_kesici(type(hata).__name__)
        return None
    except Exception as hata:  # beklenmeyen hata retranslate'i durdurmasin
        print(f"  [Gemini] beklenmeyen hata: {type(hata).__name__}")
        return None

    if yanit.status_code == 429 or yanit.status_code >= 500:
        _devre_kesici(f'HTTP {yanit.status_code}')
        return None
    if yanit.status_code != 200:
        # Istek sorunu (anahtar, gecersiz govde): kota harcanmadi, devre kesici acilmaz
        butce.azalt(anahtar)
        print(f"  [Gemini] istek reddedildi (HTTP {yanit.status_code}): {yanit.text[:200]}")
        return None

    cikti = _yaniti_coz(yanit)
    if cikti is None:
        return None
    sonuc = {}
    for ad, orijinal in alanlar.items():
        sorun = _alan_sorunu(orijinal, cikti.get(ad))
        if sorun:
            print(f"  [Gemini] dogrulama basarisiz ({ad}: {sorun}).")
            return None
        sonuc[ad] = cikti[ad].strip()
    return sonuc
