"""Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir (spec 9.3, H2).

Neden gerekli: fetch task'lari ceviri bekleyen bir kaydi yalnizca kaynak feed onu
hala donduruyorsa yeniden isler. Feed penceresinden cikan kayit bir daha hic
cevrilmezdi.

Siralama (A3 plani netlestirme 8): her bolum icin Redis'te bir imlec tutulur
({prefix}:cursor:{bolum}). Her tur imlecten sonraki RETRANSLATE_BATCH bekleyen
kaydi dener. Icerik yuzunden cevrilemeyen kayit sirada kalir ama imlec onu gecer;
boylece hep basarisiz olan birkac kayit kuyrugun onunu kalici olarak tikamaz.
Sona gelinince imlec silinir, bir sonraki tur bastan baslar.

Yazma kurallari:
  - Basarisiz denemede kayda yazilmaz: updated_at ilerlemez, tuketicinin delta
    akisina degismemis kayit dusmez.
  - Basarida Turkce alanlar yazilir, bayrak duser, updated_at ilerler; Turkce
    metin delta akisindan tuketiciye kendiliginden gider.
  - Devre kesici acikken Google'a hic gidilmez; erisim hatasinda imlec o kaydi
    gecmez, bir sonraki tur once onu dener.
"""
import os
from typing import Dict

from . import translation_utils as tu
from .api_v1.cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
from .cache_utils import cache_yenile
from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

# Bolum basina; alti bolumle tur basina en fazla 48 kayit.
RETRANSLATE_BATCH = int(os.environ.get('RETRANSLATE_BATCH', '8'))


def _baslik_ve_uzun_aciklama(kayit) -> Dict[str, str]:
    # scraper_multi, sre_scraper, devtools_scraper ve ai_scraper ile ayni kural
    return {
        'turkish_title': tu.translate_text(kayit.original_title),
        'turkish_description': tu.translate_long_text(kayit.original_description),
    }


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


def retranslate_pending(redis_client=None, prefix: str = 'retranslate', batch: int = None) -> Dict:
    redis_client = redis_client or _canli_redis()
    batch = RETRANSLATE_BATCH if batch is None else batch
    kapi = tu._get_gate()
    sonuc = {'translated': 0, 'failed': 0, 'stopped_by_cooldown': False, 'sections': {}}

    for ad, model, cevir in BOLUMLER:
        if kapi.cooldown_active():
            sonuc['stopped_by_cooldown'] = True
            break

        imlec_anahtari = f'{prefix}:cursor:{ad}'
        sorgu = model.objects.filter(needs_translation=True).order_by('updated_at', 'id')
        ham_imlec = redis_client.get(imlec_anahtari)
        if ham_imlec:
            try:
                sorgu = apply_cursor(sorgu, *decode_cursor(ham_imlec.decode('utf-8')))
            except InvalidCursor:
                redis_client.delete(imlec_anahtari)
        kayitlar = list(sorgu[:batch])

        cevrilen = basarisiz = 0
        yarida_kaldi = False
        for kayit in kayitlar:
            if kapi.cooldown_active():
                yarida_kaldi = True
                break

            deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)
            tu.consume_translation_failures()
            alanlar = cevir(kayit)

            if tu.consume_translation_failures() > 0:
                if kapi.cooldown_active():
                    # Erisim hatasi: imleci ilerletme, bir sonraki tur once bu kaydi denesin
                    yarida_kaldi = True
                    break
                basarisiz += 1  # icerik hatasi (dogrulama): imlec gecer, kayit sirada kalir
            else:
                for alan, deger in alanlar.items():
                    setattr(kayit, alan, deger)
                kayit.needs_translation = False
                kayit.save(update_fields=[*alanlar, 'needs_translation', 'updated_at'])
                cevrilen += 1
            redis_client.set(imlec_anahtari, deneme_oncesi)

        if yarida_kaldi:
            sonuc['stopped_by_cooldown'] = True
        elif len(kayitlar) < batch:
            redis_client.delete(imlec_anahtari)  # sona gelindi; bir sonraki tur bastan

        if cevrilen:
            cache_yenile(ad)
        sonuc['sections'][ad] = {'translated': cevrilen, 'failed': basarisiz}
        sonuc['translated'] += cevrilen
        sonuc['failed'] += basarisiz

        if yarida_kaldi:
            break

    return sonuc
