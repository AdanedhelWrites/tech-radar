"""Bolum basina kaynak adlari ve kaynak sagligi (2026-10-08).

Neden: 2026-10-08 olcumunde 8 kaynak aylarca sessizce olmustu (Bleeping Computer
hic kayit uretmemis, SecurityWeek bos linke cokmus, MongoDB/InfoQ/DZone akislari
donmus). FetchRun yalniz bolum toplamini tutuyordu; bolum "success" gorundugu
surece tek bir kaynagin 0 donmesi hicbir yerde gorunmuyordu.

Iki parca:
  - bolum_kaynaklari(bolum): scraper kayit defterlerindeki kaynak adlari. Task'lar
    bununla secili her kaynagi 0'dan baslatir; boylece "secilmedi" ile "secildi
    ama hic kayit donmedi" ayrilir (FetchRun.by_source).
  - kaynak_durumlari(bolum, model): /api/v1/status/ icin kaynak basina son kayit
    zamani, son turda gelen sayi ve ardisik sifir tur sayisi. SOURCE_SILENT_RUNS
    (varsayilan 4 = Beat'te 24 saat) ardisik sifir tur "sessiz" sayilir.

"Gelen" sayisi _drop_existing'den ONCEKI sayidir: saglikli ama seyrek yazan bir
kaynak (PagerDuty, Krebs) kendi `days` penceresinde yine kayit dondurur; yeni
kayit olmamasi sessizlik degildir, kaynaktan hic kayit gelmemesi sessizliktir.
"""
import os
from functools import lru_cache
from typing import Dict, List

SESSIZ_TUR_ESIGI = int(os.environ.get('SOURCE_SILENT_RUNS', '4'))
# Sessizlik hesabinda geriye bakilan tamamlanmis tur sayisi
TUR_PENCERESI = 20

BOLUMLER = ('news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai')


@lru_cache(maxsize=None)
def bolum_kaynaklari(bolum: str) -> List[str]:
    """Bolumun kayit defterindeki kaynak adlari, scraper sirasiyla."""
    if bolum == 'news':
        from scraper_multi import MultiSourceScraper
        return [s.get_name() for s in MultiSourceScraper().sources]
    if bolum == 'cve':
        from .cve_scraper import MultiCVEScraper
        return list(MultiCVEScraper().sources)
    if bolum == 'kubernetes':
        from .k8s_scraper import MultiK8sScraper
        return list(MultiK8sScraper().sources)
    if bolum == 'sre':
        from .sre_scraper import MultiSREScraper
        return list(MultiSREScraper().sources)
    if bolum == 'devtools':
        from .devtools_scraper import MultiDevToolsScraper
        return list(MultiDevToolsScraper().scrapers)
    if bolum == 'ai':
        from .ai_scraper import MultiAINewsScraper
        return list(MultiAINewsScraper().scrapers)
    raise KeyError(bolum)


def kaynak_sayaclari(bolum: str, selected_sources, entries) -> Dict[str, Dict[str, int]]:
    """FetchRun.by_source icin {kaynak: {'fetched': n, 'saved': 0}} baslangici.

    Secili kaynaklar 0 ile acilir; entries'teki 'source' anahtarlari sayilir.
    Kaynak secimi scraper'larda bazen buyuk/kucuk harf duyarsiz (DevTools), o
    yuzden eslesme kucuk harfle yapilir.
    """
    adlar = bolum_kaynaklari(bolum)
    if selected_sources:
        secili = {str(s).lower() for s in selected_sources}
        adlar = [a for a in adlar if a.lower() in secili]
    sayac = {a: {'fetched': 0, 'saved': 0} for a in adlar}
    for e in entries:
        ad = e.get('source') or ''
        sayac.setdefault(ad, {'fetched': 0, 'saved': 0})['fetched'] += 1
    return sayac


def kaynak_yazildi(sayac: Dict[str, Dict[str, int]], ad: str) -> None:
    sayac.setdefault(ad or '', {'fetched': 0, 'saved': 0})['saved'] += 1


def kaynak_durumlari(bolum: str, model) -> Dict[str, dict]:
    """Status ucu: kaynak basina sessizlik bilgisi.

    Yalniz by_source tasiyan tamamlanmis turlara bakilir (bu alan 2026-10-08'den
    once bos). Kaynagin yer almadigi tur (secili degildi) atlanir; ardisik sifir
    sayimi ilk >0 turda durur.
    """
    from django.db.models import Max

    from .models import FetchRun

    turlar = list(
        FetchRun.objects.filter(section=bolum)
        .exclude(status='running')
        .exclude(by_source={})
        .order_by('-started_at')[:TUR_PENCERESI]
    )
    son_kayit = {
        satir['source']: satir['son']
        for satir in model.objects.values('source').annotate(son=Max('created_at'))
    }
    durum = {}
    for ad in bolum_kaynaklari(bolum):
        sifir = 0
        son_gelen = None
        for tur in turlar:
            sayac = (tur.by_source or {}).get(ad)
            if sayac is None:
                continue
            gelen = int(sayac.get('fetched', 0) or 0)
            if son_gelen is None:
                son_gelen = gelen
            if gelen > 0:
                break
            sifir += 1
        durum[ad] = {
            'last_record_at': son_kayit.get(ad),
            'last_fetched_count': son_gelen,
            'zero_runs': sifir,
            'silent': sifir >= SESSIZ_TUR_ESIGI,
        }
    return durum
