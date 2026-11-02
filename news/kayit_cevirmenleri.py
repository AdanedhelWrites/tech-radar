"""Kayit duzeyi yedek cevirmenler ve saglayici zinciri (spec 2026-11-02-ceviri-yayma G6).

ZINCIR sirasi: Gemini birincil (gemini.BIRINCIL), Gemini ikinci model (GEMINI_FALLBACK_MODEL; bossa
zincirde yok), OpenRouter ucretsiz model, DeepL API Free. ZINCIR[0] disindakiler yedektir. Hepsi
gemini.KayitCevirmeni arayuzunu (name, hazir, kaydi_cevir, paket_cevir, butce_ozeti) ve ortak kota,
HTTP ve dogrulama kurallarini paylasir. Anahtari bos olan saglayici hazir degildir (atlanir).
Anahtar degerleri yalniz istek basligina girer; loga, ozete ve hata metnine yazilmaz.
HTTP cagrisi tabanin _istek_at'indadir (news.gemini); testler news.gemini.requests.post'u yamalar.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, Optional

from django.conf import settings

from . import gemini
from . import translation_utils as tu

log = logging.getLogger(__name__)

# Gemini ikinci model: ayni anahtar, model basina ayri Google kotasi. Bos: zincirde yok.
GEMINI_FALLBACK_MODEL = os.environ.get('GEMINI_FALLBACK_MODEL', '').strip()
GEMINI_FALLBACK_DAILY_BUDGET = int(os.environ.get('GEMINI_FALLBACK_DAILY_BUDGET', '450'))

OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'
# Bos: hazir degil. Adi ':free' ile bitmeyen model reddedilir (yanlislikla ucret cikmasin).
OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL', '').strip()
# Ucretsiz modellerin gunluk siniri hesap durumuna gore degisir (kredisiz hesapta ~50 istek/gun)
OPENROUTER_DAILY_BUDGET = int(os.environ.get('OPENROUTER_DAILY_BUDGET', '50'))
OPENROUTER_MIN_INTERVAL = float(os.environ.get('OPENROUTER_MIN_INTERVAL', '4'))   # ~20 istek/dk altinda
OPENROUTER_TIMEOUT = float(os.environ.get('OPENROUTER_TIMEOUT', '60'))
OPENROUTER_COOLDOWN = int(os.environ.get('OPENROUTER_COOLDOWN', '600'))
UCRETSIZ_SONEK = ':free'

DEEPL_URL = 'https://api-free.deepl.com/v2/translate'
DEEPL_FREE_SONEK = ':fx'   # DeepL API Free anahtarlarinin soneki
# DeepL Free ayda 500.000 karakter; 50.000 guvenlik payi
DEEPL_MONTHLY_CHARS = int(os.environ.get('DEEPL_MONTHLY_CHARS', '450000'))
DEEPL_MIN_INTERVAL = float(os.environ.get('DEEPL_MIN_INTERVAL', '1'))
DEEPL_TIMEOUT = float(os.environ.get('DEEPL_TIMEOUT', '30'))
DEEPL_COOLDOWN = int(os.environ.get('DEEPL_COOLDOWN', '600'))
AYLIK_SAYAC_TTL = 35 * 24 * 3600   # aylik sayac ay bitene kadar yasar, sonra kendiliginden silinir

_KOD_CITI = re.compile(r'^\s*```(?:json)?\s*|\s*```\s*$', re.IGNORECASE)
# DeepL icin _protect_terms'e ek: harf+rakam karisik urun/kutuphane adlari (libxml2, log4j, H100).
# Mevcut XTRM yer tutuculari haric tutulur.
_URUN_ADI = re.compile(r'\b(?!XTRM\d{4}X)[A-Za-z]+\d[A-Za-z0-9]*\b')


def _ayar(ad: str) -> str:
    return (getattr(settings, ad, '') or '').strip()


def _hata_kodu(hata) -> Optional[int]:
    try:
        return int(hata.get('code'))
    except Exception:  # hata dict degil / kod yok / sayi degil
        return None


def _govde_hatasi(yanit):
    """OpenRouter 200 yaniti aslinda saglayici hatasi mi: (kod, sebep) ya da None. ASLA firlatmaz.

    Hata sayilan: ust duzey error (choices yok), bos/eksik choices, finish_reason 'error', 'stop' ile
    bos/None icerik. Cozulemeyen govde, content_filter ve cozulemeyen icerik burada degil, _cikti'da
    yanit_bozuk olur."""
    try:
        govde = yanit.json()
    except Exception:
        return None
    if not isinstance(govde, dict):
        return None
    ust_hata = govde.get('error')
    secenekler = govde.get('choices')
    if not isinstance(secenekler, list) or not secenekler:
        kod = _hata_kodu(ust_hata)
        return kod, f"HTTP 200 hata {kod if kod is not None else 'choices yok'}"
    secenek = secenekler[0]
    if not isinstance(secenek, dict):
        return None
    if secenek.get('finish_reason') == 'error':
        kod = _hata_kodu(secenek.get('error'))
        kod = kod if kod is not None else _hata_kodu(ust_hata)
        return kod, f"HTTP 200 hata {kod if kod is not None else 'finish_reason error'}"
    mesaj = secenek.get('message')
    icerik = mesaj.get('content') if isinstance(mesaj, dict) else None
    if secenek.get('finish_reason') in (None, 'stop') and not (isinstance(icerik, str) and icerik.strip()):
        kod = _hata_kodu(ust_hata)
        return kod, f"HTTP 200 hata {kod if kod is not None else 'bos icerik'}"
    return None


class OpenRouterCevirmen(gemini.KayitCevirmeni):
    """OpenRouter ucretsiz modeli (chat/completions, json_object). Gemini ile ayni sistem talimati ve
    paket bicimi; yanitin choices[0].message.content'i ayni paket JSON'u olarak cozulur.
    Gunluk istek sayaci UTC gunune gore (openrouter:budget:YYYY-MM-DD)."""

    name = 'openrouter'
    log_adi = 'OpenRouter'
    zaman_asimi = OPENROUTER_TIMEOUT
    bekleme = OPENROUTER_COOLDOWN
    kesici_http = frozenset({408, 429})          # zaman asimi / hiz siniri: istek duzeyi
    # 402 kredi/odeme gerekli, 404 model ya da uc yok: her istek ayni yaniti alir
    sistemik_http = frozenset({401, 402, 403, 404})

    def __init__(self, model: str = OPENROUTER_MODEL, tavan: int = OPENROUTER_DAILY_BUDGET,
                 aralik: float = OPENROUTER_MIN_INTERVAL):
        super().__init__('openrouter', tavan, aralik)
        self.model = (model or '').strip()
        self._ucretli_uyarildi = False
        self._modelsiz_uyarildi = False

    def _anahtar(self) -> str:
        return _ayar('OPENROUTER_API_KEY')

    def _kullanilabilir(self) -> bool:
        """Anahtar dolu iken sorulur (hazir/ayarli): uyarilar yalniz anahtar girilmis kurulumda cikar."""
        if not self.model:
            if not self._modelsiz_uyarildi:
                self._modelsiz_uyarildi = True
                log.warning("  [OpenRouter] OPENROUTER_API_KEY dolu ama OPENROUTER_MODEL bos; OpenRouter "
                            "kullanilmiyor.")
            return False
        if not self.model.endswith(UCRETSIZ_SONEK):
            if not self._ucretli_uyarildi:
                self._ucretli_uyarildi = True
                log.warning(f"  [OpenRouter] OPENROUTER_MODEL '{self.model}' '{UCRETSIZ_SONEK}' ile bitmiyor; "
                            "ucret cikmasin diye kullanilmiyor.")
            return False
        return True

    def _donem_anahtari(self) -> str:
        return f'budget:{datetime.now(timezone.utc):%Y-%m-%d}'

    def _istek_adresi(self) -> str:
        return OPENROUTER_URL

    def _basliklar(self) -> dict:
        return {'Authorization': f'Bearer {self._anahtar()}', 'Content-Type': 'application/json'}

    def _govde(self, veri: dict, paket: bool):
        talimat = gemini.PAKET_TALIMATI if paket else gemini.SISTEM_TALIMATI
        return {
            'model': self.model,
            'temperature': 0.2,
            'response_format': {'type': 'json_object'},
            'messages': [{'role': 'system', 'content': talimat},
                         {'role': 'user', 'content': json.dumps(veri, ensure_ascii=False)}],
        }, None

    def _istek_at(self, govde: dict, etiket: str = 'genel kaydi', kayit_sayisi: int = 1, miktar: int = 1):
        """Taban kurallari + 200 icinde gelen saglayici hatasi (ucretsiz katmanda ust saglayici hiz
        siniri/asiri yuk). Bu istek duzeyi hatadir: kayit sucu sayilmaz, devre kesici acilir, None doner
        (paket_cevir -> istek_hatasi). error.code sistemikse (401/402/403/404) sayac geri alinir;
        degilse istek harcanmis sayilir."""
        yanit = super()._istek_at(govde, etiket, kayit_sayisi, miktar)
        if yanit is None:
            return None
        hata = _govde_hatasi(yanit)
        if hata is None:
            return yanit
        kod, sebep = hata
        if kod in self.sistemik_http:
            self._sayac().azalt(self._donem_anahtari(), miktar)
        self._devre_kesici(sebep)
        return None

    def _cikti(self, yanit, veri: dict, paket: bool, baglam):
        try:
            secenek = yanit.json()['choices'][0]
            sebep = secenek.get('finish_reason')
            if sebep == 'length':
                log.warning("  [OpenRouter] yanit tamamlanmadi (length).")
                return None, True
            if sebep not in (None, 'stop'):
                log.warning(f"  [OpenRouter] yanit tamamlanmadi ({sebep}).")
                return None, False
            cikti = json.loads(_KOD_CITI.sub('', secenek['message']['content']))
        except Exception as hata:  # ValueError/KeyError/IndexError/TypeError/AttributeError vb.
            log.warning(f"  [OpenRouter] yanit cozulemedi ({type(hata).__name__}).")
            return None, False
        if not isinstance(cikti, dict):
            log.warning("  [OpenRouter] yanit JSON nesnesi degil.")
            return None, False
        return cikti, False


def _terimleri_koru(metin: str):
    """(korunmus, yerine): _protect_terms + harf/rakam karisik urun adlari; numaralama surer."""
    korunmus, yerine = tu._protect_terms(metin)
    sayac = len(yerine)

    def degistir(eslesme):
        nonlocal sayac
        sayac += 1
        kod = f'XTRM{sayac:04d}X'
        yerine[kod] = eslesme.group(0)
        return kod
    return _URUN_ADI.sub(degistir, korunmus), yerine


def _terimleri_geri_koy(ceviri: str, korunmus: str, yerine: Dict[str, str]) -> Optional[str]:
    """Yer tutuculari geri koyar. None: gonderilen bir yer tutucu ceviride kayboldu ya da geri
    konamayan yer tutucu kaldi (terim kaybi; alan dogrulamadan gecmez)."""
    onarilmis = tu._repair_placeholders(ceviri)
    # Ic ice yer tutucu (URL'nin yuttugu kod) metinde gorunmez; yalniz gonderilenler beklenir
    if any(kod not in onarilmis for kod in set(tu._PLACEHOLDER_RE.findall(korunmus))):
        return None
    geri = tu._restore_terms(onarilmis, yerine)
    return None if tu._PLACEHOLDER_RE.search(geri) else geri


class DeepLCevirmen(gemini.KayitCevirmeni):
    """DeepL API Free (LLM degil). Paket = tek istek, cok text; ceviriler sirayla kayit/alana eslenir.
    Terimler XTRM yer tutucularla korunur. Aylik karakter sayaci (deepl:budget:YYYY-MM, UTC ayi)
    istekten once gonderilen karakter kadar artar; 429/456 disi 4xx'te geri alinir."""

    name = 'deepl'
    log_adi = 'DeepL'
    donem = 'month'
    donem_metni = 'aylik'
    sayac_ttl = AYLIK_SAYAC_TTL
    zaman_asimi = DEEPL_TIMEOUT
    bekleme = DEEPL_COOLDOWN
    kesici_http = frozenset({429, 456})          # 456: aylik kota doldu

    def __init__(self, tavan: int = DEEPL_MONTHLY_CHARS, aralik: float = DEEPL_MIN_INTERVAL):
        super().__init__('deepl', tavan, aralik)
        self._free_disi_uyarildi = False

    def _anahtar(self) -> str:
        return _ayar('DEEPL_API_KEY')

    def _kullanilabilir(self) -> bool:
        """DeepL Free anahtarlari ':fx' ile biter. Sonekisiz (Pro) anahtar kullanilmaz: ucret cikmasin, Pro
        anahtari Free ucunda zaten 403 alir. Anahtar dolu iken sorulur; anahtar loga yazilmaz."""
        if self._anahtar().endswith(DEEPL_FREE_SONEK):
            return True
        if not self._free_disi_uyarildi:
            self._free_disi_uyarildi = True
            log.warning(f"  [DeepL] DEEPL_API_KEY '{DEEPL_FREE_SONEK}' ile bitmiyor (DeepL Free anahtari degil); "
                        "ucret cikmasin diye kullanilmiyor.")
        return False

    def _donem_anahtari(self) -> str:
        return f'budget:{datetime.now(timezone.utc):%Y-%m}'

    def _kesici_yaniti(self, durum: int) -> None:
        """456: DeepL aylik kotasi bitti. Sayac ay tavanina doldurulur: hazir() ay degisene kadar False
        kalir, devre kesici her bekleme sonunda yeniden yoklamaz."""
        if durum != 456:
            return
        anahtar = self._donem_anahtari()
        eksik = self.tavan() - self._sayac().oku(anahtar)
        if eksik > 0:
            self._sayac().artir(anahtar, eksik)

    def _istek_adresi(self) -> str:
        return DEEPL_URL

    def _basliklar(self) -> dict:
        return {'Authorization': f'DeepL-Auth-Key {self._anahtar()}', 'Content-Type': 'application/json'}

    def _govde(self, veri: dict, paket: bool):
        """baglam: text sirasiyla (kimlik, alan, korunmus, yerine); tek kayitta kimlik ''."""
        sira, metinler = [], []
        for kimlik, alanlar in (veri if paket else {'': veri}).items():
            for ad, metin in alanlar.items():
                korunmus, yerine = _terimleri_koru(metin)
                sira.append((kimlik, ad, korunmus, yerine))
                metinler.append(korunmus)
        return {'text': metinler, 'source_lang': 'EN', 'target_lang': 'TR', 'preserve_formatting': True}, sira

    def _miktar(self, govde: dict) -> int:
        return sum(len(metin) for metin in govde['text'])

    def _cikti(self, yanit, veri: dict, paket: bool, sira):
        try:
            ceviriler = [ceviri['text'] for ceviri in yanit.json()['translations']]
        except Exception as hata:
            log.warning(f"  [DeepL] yanit cozulemedi ({type(hata).__name__}).")
            return None, False
        if len(ceviriler) != len(sira) or not all(isinstance(ceviri, str) for ceviri in ceviriler):
            log.warning(f"  [DeepL] ceviri sayisi tutmuyor ({len(ceviriler)}/{len(sira)}).")
            return None, False
        cikti = {}
        for (kimlik, ad, korunmus, yerine), ceviri in zip(sira, ceviriler):
            alanlar = cikti.setdefault(kimlik, {})
            geri = _terimleri_geri_koy(ceviri, korunmus, yerine)
            if geri is None:
                log.warning(f"  [DeepL] yer tutucu kayboldu ({kimlik + '/' if kimlik else ''}{ad}).")
            else:
                alanlar[ad] = geri  # eksik alan dogrulamada 'bos' olur, kayit reddedilir
        return (cikti if paket else cikti.get('', {})), False


GEMINI2 = gemini.GeminiCevirmen(GEMINI_FALLBACK_MODEL, onek='gemini2', tavan=GEMINI_FALLBACK_DAILY_BUDGET)
OPENROUTER = OpenRouterCevirmen()
DEEPL = DeepLCevirmen()
# Zincire girsin girmesin tum yedek ornekler (test calistiricisi durumlarini surec ici yapar)
YEDEKLER = (GEMINI2, OPENROUTER, DEEPL)


def _zinciri_kur(gemini2: gemini.GeminiCevirmen = GEMINI2) -> list:
    """Saglayici sirasi; modeli bos ikinci Gemini zincire girmez."""
    return [gemini.BIRINCIL] + ([gemini2] if gemini2.model else []) + [OPENROUTER, DEEPL]


ZINCIR = _zinciri_kur()
