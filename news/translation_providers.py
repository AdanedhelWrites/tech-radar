"""Ceviri saglayicilari (spec 2026-09-14-ceviri-saglayici-zinciri, bolum 4.1).

translation_utils.translate_text saglayicilari SAGLAYICILAR sirasiyla dener.
Her saglayici ayni arayuzu uygular:

    name: str                             veritabanina yazilan ad
    available() -> bool                   simdi denenebilir mi
    translate(protected) -> str | None    terimleri korunmus metni cevirir; erisilemezse None

Google mantigi (hiz siniri, yeniden deneme, devre kesici) translation_utils
icinde kalir: mevcut testler oradaki adlari mock'luyor. GoogleProvider cagri
aninda oraya basvuran ince bir sarmalayicidir.
"""
import os
import re
from typing import List, Optional

import requests
from django.conf import settings

from . import translation_utils as tu

# LibreTranslate uzun, noktalamasi zayif bolumlerde yer tutucu dusuruyor.
# Denemede (60 gercek metin) <=160 karakterlik parcalar kaybi 14'ten 4'e indirdi.
LIBRETRANSLATE_CHUNK_CHARS = int(os.environ.get('LIBRETRANSLATE_CHUNK_CHARS', '160'))
LIBRETRANSLATE_TIMEOUT = float(os.environ.get('LIBRETRANSLATE_TIMEOUT', '60'))
# Yerel servis dusmusse bekleyip tekrar denemek cekimi yavaslatir; kisa sure atla.
LIBRETRANSLATE_COOLDOWN = int(os.environ.get('LIBRETRANSLATE_COOLDOWN', '60'))

_CUMLE_SONU = re.compile(r'(?<=[.!?])\s+')
_YER_TUTUCU_UZUNLUGU = len('XTRM0001X')


def _kesme_noktasi(cumle: str, sinir: int) -> int:
    virgul = cumle.rfind(', ', 0, sinir)
    if virgul > sinir // 2:
        return virgul + 1  # virgul ilk parcada kalsin
    bosluk = cumle.rfind(' ', 0, sinir)
    if bosluk > sinir // 2:
        return bosluk
    # Bosluk yok: sinira tasan bir yer tutucuyu ortadan bolme
    yer_tutucu = cumle.rfind('XTRM', max(0, sinir - _YER_TUTUCU_UZUNLUGU + 1), sinir)
    if yer_tutucu > 0:
        return yer_tutucu
    return sinir


def parcala(metin: str, sinir: int = None) -> List[List[str]]:
    """Metni satirlara, her satiri en fazla `sinir` karakterlik parcalara boler."""
    sinir = LIBRETRANSLATE_CHUNK_CHARS if sinir is None else sinir
    satirlar = []
    for satir in metin.split('\n'):
        parcalar = []
        for cumle in _CUMLE_SONU.split(satir.strip()):
            cumle = cumle.strip()
            while len(cumle) > sinir:
                kes = _kesme_noktasi(cumle, sinir)
                parcalar.append(cumle[:kes].strip())
                cumle = cumle[kes:].strip()
            if cumle:
                parcalar.append(cumle)
        satirlar.append(parcalar)
    return satirlar


def birlestir(satirlar: List[List[str]], cevrilen: List[str]) -> str:
    """parcala ciktisini cevrilmis parcalarla ayni satir yapisinda birlestirir."""
    kalan = iter(cevrilen)
    return '\n'.join(' '.join(next(kalan).strip() for _ in satir) for satir in satirlar)


class GoogleProvider:
    name = 'google'

    def available(self) -> bool:
        return not tu._get_gate().cooldown_active()

    def translate(self, protected: str) -> Optional[str]:
        return tu._translate_via_google(protected)


_lt_gate = None


def _get_lt_gate():
    """LibreTranslate devre kesicisi; Redis varsa tum worker'larda paylasilir."""
    global _lt_gate
    if _lt_gate is None:
        try:
            from django_redis import get_redis_connection
            client = get_redis_connection('default')
            client.ping()
            _lt_gate = tu._RedisGate(client, prefix='libretranslate')
        except Exception:
            _lt_gate = tu._LocalGate()
    return _lt_gate


class LibreTranslateProvider:
    name = 'libretranslate'

    def _adres(self) -> str:
        return (getattr(settings, 'LIBRETRANSLATE_URL', '') or '').rstrip('/')

    def available(self) -> bool:
        return bool(self._adres()) and not _get_lt_gate().cooldown_active()

    def _devre_kesici(self, sebep: str) -> None:
        print(f"  [Ceviri] LibreTranslate erisilemiyor ({sebep}); "
              f"{LIBRETRANSLATE_COOLDOWN} sn atlanacak.")
        _get_lt_gate().start_cooldown(LIBRETRANSLATE_COOLDOWN)

    def translate(self, protected: str) -> Optional[str]:
        adres = self._adres()
        if not adres:
            return None
        satirlar = parcala(protected)
        parcalar = [parca for satir in satirlar for parca in satir]
        if not parcalar:
            return protected

        try:
            yanit = requests.post(
                f'{adres}/translate',
                json={'q': parcalar, 'source': 'en', 'target': 'tr', 'format': 'text'},
                timeout=LIBRETRANSLATE_TIMEOUT,
            )
        except requests.RequestException as hata:
            self._devre_kesici(type(hata).__name__)
            return None

        if yanit.status_code >= 500:
            self._devre_kesici(f'HTTP {yanit.status_code}')
            return None
        if yanit.status_code != 200:
            # Istek sorunu; servis ayakta, devre kesici acilmaz
            print(f"  [Ceviri] LibreTranslate istegi reddetti (HTTP {yanit.status_code}).")
            return None

        try:
            cevrilen = yanit.json()['translatedText']
        except (ValueError, KeyError, TypeError):
            print("  [Ceviri] LibreTranslate gecersiz yanit dondurdu.")
            return None
        if not isinstance(cevrilen, list) or len(cevrilen) != len(parcalar):
            print("  [Ceviri] LibreTranslate parca sayisi uyusmadi.")
            return None
        return birlestir(satirlar, cevrilen)


SAGLAYICILAR = (GoogleProvider(), LibreTranslateProvider())
