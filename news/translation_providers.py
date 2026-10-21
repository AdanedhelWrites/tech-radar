"""Ceviri saglayicilari (spec 2026-09-14-ceviri-saglayici-zinciri, bolum 4.1).

translation_utils.translate_text saglayicilari SAGLAYICILAR sirasiyla dener.
Her saglayici ayni arayuzu uygular:

    name: str                             veritabanina yazilan ad
    available() -> bool                   simdi denenebilir mi
    translate(protected) -> str | None    terimleri korunmus metni cevirir; erisilemezse None

Cekim aninda tek saglayici LibreTranslate'tir; Gemini yalniz retranslate'te
kayit duzeyinde kullanilir (news/gemini.py).
"""
import os
import re
from collections import Counter
from typing import List, Optional

import requests
from django.conf import settings

from . import translation_utils as tu
import logging

log = logging.getLogger(__name__)

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
        log.warning(f"  [Ceviri] LibreTranslate erisilemiyor ({sebep}); "
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

        cevrilen = self._istek(adres, parcalar)
        if cevrilen is None:
            return None
        return birlestir(satirlar, self._onar(adres, parcalar, cevrilen))

    def _onar(self, adres: str, parcalar: List[str], cevrilen: List[str]) -> List[str]:
        """Bozuk parcalari tek ek istekle onarir (2026-10-21 bulgu 9). Yer tutucu basina kayip
        %4.4 ama 4500 karakterlik metin ~20 yer tutucu tasidigi icin metinlerin %37'si tumden
        reddediliyordu. Yalniz bozuk parca yeniden cevrilir:
          - yer tutucusu eksik/yinelenen parca: yer tutucular arasindaki metinler ayri ayri
            cevrilip yer tutucular yerine geri dizilir (cumle bolunur ama hicbir terim kaybolmaz)
          - baslik bicimli (Title Case) yanki: model ozel ad sanip aynen dondurur; cumle
            bicimiyle yeniden denenir, cevrilmeyen ozel adlarin buyuk harfi geri konur
        Ek istek basarisizsa ilk ceviri doner; dogrulama (verify_translation) onu yine reddeder."""
        sonuc = list(cevrilen)
        isler = []  # (parca indisi, tur, veri)
        q = []
        for i, (kaynak, ceviri) in enumerate(zip(parcalar, cevrilen)):
            if _yer_tutucular(kaynak) != _yer_tutucular(tu._repair_placeholders(ceviri)):
                dilimler = _YER_TUTUCU_BOL.split(kaynak)
                hedefler = [j for j, d in enumerate(dilimler) if _HARFLI.search(d) and not _YER_TUTUCU_TAM.match(d)]
                if not hedefler:
                    sonuc[i] = kaynak  # yalniz isaret/sayi: cevrilecek bir sey yok
                    continue
                isler.append((i, 'dilim', (dilimler, hedefler, len(q))))
                q.extend(dilimler[j].strip() for j in hedefler)
            elif (tu._normalize_for_echo(ceviri) == tu._normalize_for_echo(kaynak)
                  and tu._translatable_word_count(kaynak) >= tu.ECHO_MIN_WORDS and _baslik_bicimli(kaynak)):
                cumle, geri = _cumle_bicimi(kaynak)
                isler.append((i, 'baslik', (geri, len(q))))
                q.append(cumle)
        if not q:
            return sonuc
        ek = self._istek(adres, q)
        if ek is None:
            return list(cevrilen)
        for i, tur, veri in isler:
            if tur == 'dilim':
                dilimler, hedefler, bas = veri
                dilimler = list(dilimler)
                for sira, j in enumerate(hedefler):
                    eski = dilimler[j]
                    on = eski[:len(eski) - len(eski.lstrip())]
                    son = eski[len(eski.rstrip()):]
                    dilimler[j] = on + ek[bas + sira].strip() + son
                sonuc[i] = ''.join(dilimler)
            else:
                geri, bas = veri
                metin = ek[bas]
                for kucuk, ozgun in geri.items():
                    metin = re.sub(rf'(?<!\w){re.escape(kucuk)}(?!\w)', ozgun, metin)
                sonuc[i] = metin
        return sonuc

    def _istek(self, adres: str, parcalar: List[str]) -> Optional[List[str]]:
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
            log.warning(f"  [Ceviri] LibreTranslate istegi reddetti (HTTP {yanit.status_code}).")
            return None

        try:
            cevrilen = yanit.json()['translatedText']
        except (ValueError, KeyError, TypeError):
            log.warning("  [Ceviri] LibreTranslate gecersiz yanit dondurdu.")
            return None
        if not isinstance(cevrilen, list) or len(cevrilen) != len(parcalar):
            log.warning("  [Ceviri] LibreTranslate parca sayisi uyusmadi.")
            return None
        return cevrilen


_YER_TUTUCU_BOL = re.compile(r'(XTRM\d{4}X)')
_YER_TUTUCU_TAM = re.compile(r'^XTRM\d{4}X$')
_HARFLI = re.compile(r'[^\W\d_]{2,}')
_KELIME = re.compile(r'[^\W\d_]+')
# Kelimelerin bu orani buyuk harfle basliyorsa parca baslik bicimlidir
BASLIK_BICIMI_ORANI = 0.6


def _yer_tutucular(metin: str) -> Counter:
    return Counter(tu._PLACEHOLDER_RE.findall(metin))


def _baslik_bicimli(parca: str) -> bool:
    kelimeler = _KELIME.findall(tu._PLACEHOLDER_RE.sub(' ', parca))
    if len(kelimeler) < tu.ECHO_MIN_WORDS:
        return False
    return sum(1 for k in kelimeler if k[0].isupper()) / len(kelimeler) >= BASLIK_BICIMI_ORANI


def _cumle_bicimi(parca: str):
    """'Rival Gangs Vie For Market' -> 'Rival gangs vie for market'. Ilk kelime, tamami buyuk
    (CVE, CAs) ve karisik harfli (eMudhra) kelimeler korunur. Donus: (metin, {kucuk: ozgun})."""
    geri = {}
    ilk = [True]

    def degistir(m):
        kelime = m.group(0)
        if ilk[0]:
            ilk[0] = False
            return kelime
        if len(kelime) > 1 and kelime[0].isupper() and kelime[1:].islower():
            geri[kelime.lower()] = kelime
            return kelime.lower()
        return kelime

    dilimler = _YER_TUTUCU_BOL.split(parca)
    return ''.join(d if _YER_TUTUCU_TAM.match(d) else _KELIME.sub(degistir, d) for d in dilimler), geri


SAGLAYICILAR = (LibreTranslateProvider(),)
