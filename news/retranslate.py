"""Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir ve LibreTranslate
cevirilerini Gemini ile yukseltir (spec 2026-09-15-gemini-yukseltme, bolum 3.3).

Asama 1 — Bekleyenler (needs_translation=True): once Gemini kayit duzeyinde
(baslik + aciklama tek istek); cevrilemezse saglayici zinciri (LibreTranslate).
A3 plani netlestirme 8'deki imlec kurallari aynen gecerlidir: her bolum icin
Redis'te bir imlec ({prefix}:cursor:{bolum}); icerik yuzunden cevrilemeyen
kayit sirada kalir ama imlec onu gecer; sona gelinince imlec silinir. Gorev
yalnizca HICBIR saglayici (Gemini dahil) hazir degilse durur; imlec o kaydi gecmez.

Asama 2 — Yukseltme (needs_translation=False, translation_provider='libretranslate'),
yalnizca Gemini ile. Gemini tum alanlari dogrulamadan gecirdiyse yazilir (hepsi ya
da hicbiri, gemini.kaydi_cevir icinde); aksi halde LibreTranslate cevirisi yerinde
kalir ve imlec ilerler. Gemini hazir degilse (anahtar yok / devre kesici / gunluk
butce) asama baslamaz; butce asama ortasinda biterse imlec ilerletilmeden durur.
Kendi imleci vardir ({prefix}:upgrade-cursor:{bolum}). Google kayitlari yukseltilmez.

Yazma kurallari:
  - Basarisiz denemede kayda yazilmaz: updated_at ilerlemez.
  - Basarida Turkce alanlar, needs_translation=False, translation_provider ve
    updated_at yazilir; ceviri delta akisindan tuketiciye gider.
"""
import os
from typing import Dict, Optional

from . import gemini
from . import translation_utils as tu
from .api_v1.cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
from .cache_utils import cache_yenile
from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

# Bolum basina. LibreTranslate yerel ve hizli oldugu icin bekleyen siniri yuksek.
RETRANSLATE_BATCH = int(os.environ.get('RETRANSLATE_BATCH', '100'))
# Yukseltme Gemini gunluk butcesini kullanir; asil sinir butcedir (gemini.GEMINI_DAILY_BUDGET).
RETRANSLATE_UPGRADE_BATCH = int(os.environ.get('RETRANSLATE_UPGRADE_BATCH', '40'))


def _baslik_ve_uzun_aciklama(kayit) -> Dict[str, str]:
    # scraper_multi, sre_scraper, devtools_scraper ve ai_scraper ile ayni kural
    alanlar = {'turkish_title': tu.translate_text(kayit.original_title)}
    # Orijinal bos ise cevrilecek bir sey yok; mevcut Turkce govde ezilmesin
    # (2026-09-15: haber kayitlarinda orijinal hic saklanmiyordu, 18 kayit boslandi)
    if (kayit.original_description or '').strip():
        alanlar['turkish_description'] = tu.translate_long_text(kayit.original_description)
    return alanlar


def _cve(kayit) -> Dict[str, str]:
    # cve_scraper.process_cves ile ayni: baslik cevrilmez, 30 karakterden kisa aciklama oldugu gibi kalir
    aciklama = kayit.original_description or ''
    return {
        'turkish_title': kayit.original_title,
        'turkish_description': tu.translate_text(aciklama) if len(aciklama.strip()) > 30 else aciklama,
    }


def _kubernetes(kayit) -> Dict[str, str]:
    # k8s_scraper.MultiK8sScraper.process_entries ile ayni ayrim
    aciklama = kayit.original_description or ''
    if kayit.source == 'GitHub Releases' and '===SECTION:' in aciklama:
        from .k8s_scraper import MultiK8sScraper
        turkce_aciklama = MultiK8sScraper()._translate_structured_changelog(aciklama)
    else:
        turkce_aciklama = tu.translate_long_text(aciklama)
    return {
        'turkish_title': tu.translate_text(kayit.original_title),
        'turkish_description': turkce_aciklama,
    }


_GEMINI_DB_ALANI = {'title': 'turkish_title', 'description': 'turkish_description'}


def _gemini_alanlari(ad: str, kayit) -> Dict[str, str]:
    """Gemini'ye gidecek alanlar (spec 3.3). Bos sozluk: kayit Gemini adayi degil."""
    aciklama = (kayit.original_description or '').strip()
    if ad == 'cve':
        # cve_scraper kurali: baslik cevrilmez, 30 karakterden kisa aciklama oldugu gibi kalir
        return {'description': aciklama} if len(aciklama) > 30 else {}
    alanlar = {'title': (kayit.original_title or '').strip()}
    if aciklama:  # 2026-09-15 haber kurali: orijinal bossa Turkce govdeye dokunma
        alanlar['description'] = aciklama
    return {alan: metin for alan, metin in alanlar.items() if metin}


def _gemini_ile_cevir(ad: str, kayit) -> Optional[Dict[str, str]]:
    """Kaydi Gemini ile cevirir; DB alan adlariyla sozluk ya da None (aday degil / hazir degil / cevrilemedi)."""
    alanlar = _gemini_alanlari(ad, kayit)
    if not alanlar or not gemini.hazir():
        return None
    sonuc = gemini.kaydi_cevir(alanlar)
    if sonuc is None:
        return None
    return {_GEMINI_DB_ALANI[alan]: metin for alan, metin in sonuc.items()}


BOLUMLER = (
    ('news', NewsArticle, _baslik_ve_uzun_aciklama),
    ('cve', CVEEntry, _cve),
    ('kubernetes', KubernetesEntry, _kubernetes),
    ('sre', SREEntry, _baslik_ve_uzun_aciklama),
    ('devtools', DevToolsEntry, _baslik_ve_uzun_aciklama),
    ('ai', AINewsEntry, _baslik_ve_uzun_aciklama),
)


def _canli_redis():
    from django_redis import get_redis_connection
    return get_redis_connection('default')


def _imlecten_sonraki(redis_client, anahtar, sorgu, sinir):
    ham = redis_client.get(anahtar)
    if ham:
        try:
            sorgu = apply_cursor(sorgu, *decode_cursor(ham.decode('utf-8')))
        except InvalidCursor:
            redis_client.delete(anahtar)
    return list(sorgu[:sinir])


def _cevir_ve_olc(cevir, kayit):
    """Kaydi cevirir; (alanlar, basarisizlik_sayisi, kullanilan_saglayicilar) dondurur."""
    tu.consume_translation_failures()
    tu.consume_translation_providers()
    alanlar = cevir(kayit)
    return alanlar, tu.consume_translation_failures(), tu.consume_translation_providers()


def _yaz(kayit, alanlar, saglayici):
    for alan, deger in alanlar.items():
        setattr(kayit, alan, deger)
    kayit.needs_translation = False
    kayit.translation_provider = saglayici
    kayit.save(update_fields=[*alanlar, 'needs_translation', 'translation_provider', 'updated_at'])


def _bekleyenler(ad, model, cevir, redis_client, prefix, sinir, sonuc):
    """Asama 1. Donus: (cevrilen, basarisiz, durdu)."""
    anahtar = f'{prefix}:cursor:{ad}'
    sorgu = model.objects.filter(needs_translation=True).order_by('updated_at', 'id')
    kayitlar = _imlecten_sonraki(redis_client, anahtar, sorgu, sinir)

    cevrilen = basarisiz = 0
    durdu = False
    for kayit in kayitlar:
        if not (tu.herhangi_saglayici_hazir() or gemini.hazir()):
            durdu = True
            break
        deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)

        gemini_alanlar = _gemini_ile_cevir(ad, kayit)
        if gemini_alanlar is not None:
            _yaz(kayit, gemini_alanlar, 'gemini')
            cevrilen += 1
            sonuc['by_provider']['gemini'] += 1
            redis_client.set(anahtar, deneme_oncesi)
            continue

        if not tu.herhangi_saglayici_hazir():
            durdu = True  # Gemini cevirmedi, zincir kapali: imleci ilerletme
            break
        alanlar, hata, kullanilan = _cevir_ve_olc(cevir, kayit)

        if hata:
            if not tu.herhangi_saglayici_hazir():
                # Erisim sorunu: imleci ilerletme, bir sonraki tur once bu kaydi denesin
                durdu = True
                break
            basarisiz += 1  # icerik hatasi: imlec gecer, kayit sirada kalir
        else:
            saglayici = tu.kayit_saglayicisi(kullanilan)
            _yaz(kayit, alanlar, saglayici)
            cevrilen += 1
            if saglayici:
                sonuc['by_provider'][saglayici] = sonuc['by_provider'].get(saglayici, 0) + 1
        redis_client.set(anahtar, deneme_oncesi)

    if not durdu and len(kayitlar) < sinir:
        redis_client.delete(anahtar)  # sona gelindi; bir sonraki tur bastan
    return cevrilen, basarisiz, durdu


def _yukselt(ad, model, redis_client, prefix, sinir, sonuc):
    """Asama 2. Yalnizca Gemini. Donus: yukseltilen kayit sayisi."""
    if not gemini.hazir():
        if not gemini.butce_var():
            sonuc['stopped_reason'] = 'gemini_budget'
        return 0
    anahtar = f'{prefix}:upgrade-cursor:{ad}'
    sorgu = (model.objects.filter(needs_translation=False, translation_provider='libretranslate')
             .order_by('updated_at', 'id'))
    kayitlar = _imlecten_sonraki(redis_client, anahtar, sorgu, sinir)

    yukseltilen = 0
    durdu = False
    for kayit in kayitlar:
        if not gemini.hazir():
            durdu = True  # butce/devre kesici asama ortasinda; imleci ilerletme
            if not gemini.butce_var():
                sonuc['stopped_reason'] = 'gemini_budget'
            break
        deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)
        alanlar = _gemini_ile_cevir(ad, kayit)
        if alanlar is not None:
            _yaz(kayit, alanlar, 'gemini')
            yukseltilen += 1
        redis_client.set(anahtar, deneme_oncesi)

    if not durdu and len(kayitlar) < sinir:
        redis_client.delete(anahtar)
    return yukseltilen


def retranslate_pending(redis_client=None, prefix: str = 'retranslate',
                        batch: int = None, upgrade_batch: int = None) -> Dict:
    redis_client = redis_client or _canli_redis()
    batch = RETRANSLATE_BATCH if batch is None else batch
    upgrade_batch = RETRANSLATE_UPGRADE_BATCH if upgrade_batch is None else upgrade_batch
    sonuc = {'translated': 0, 'failed': 0, 'upgraded': 0, 'stopped': False, 'stopped_reason': None,
             'by_provider': {'gemini': 0, 'libretranslate': 0}, 'sections': {}}

    for ad, model, cevir in BOLUMLER:
        if not (tu.herhangi_saglayici_hazir() or gemini.hazir()):
            sonuc['stopped'] = True
            sonuc['stopped_reason'] = 'no_provider'
            break

        cevrilen, basarisiz, durdu = _bekleyenler(ad, model, cevir, redis_client, prefix, batch, sonuc)
        yukseltilen = 0 if durdu else _yukselt(ad, model, redis_client, prefix, upgrade_batch, sonuc)

        if cevrilen or yukseltilen:
            cache_yenile(ad)
        sonuc['sections'][ad] = {'translated': cevrilen, 'failed': basarisiz, 'upgraded': yukseltilen}
        sonuc['translated'] += cevrilen
        sonuc['failed'] += basarisiz
        sonuc['upgraded'] += yukseltilen

        if durdu:
            sonuc['stopped'] = True
            sonuc['stopped_reason'] = 'no_provider'
            break

    return sonuc
