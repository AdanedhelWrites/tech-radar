"""Veritabanindaki CVE'lerin kaynaktan guncellenmesi ve yeni kayit secimi (2026-11-07, tam inceleme P1).

Onceden fetch_cve_task cevrilmis her CVE'yi `_drop_existing` ile listeden atiyordu; kayit bir kez
yazildiktan sonra KEV'e eklenmesi, CVSS'inin degismesi ya da yer tutucu aciklamasinin ("No description
provided") gercegiyle degismesi hic yansimiyordu. Canlida 16 KEV kaydinin hicbiri olusturulduktan
sonra guncellenmemisti; 57 Tenable kaydi 10-23'ten beri aciklamasizdi.

Guncelleme ceviri butcesi harcamaz: Turkce alanlara dokunmaz. Tek istisna aciklamanin kendisinin
gelmesidir (yer tutucu -> gercek metin); o zaman kayit ceviri kuyruguna (needs_translation) doner ve
saatlik retranslate onu kendi kurallariyla (Gemini yalniz aday CVE'lerde) cevirir.
"""
from datetime import timedelta
from typing import Dict, List

from django.utils import timezone

from .cve_scraper import CISAKEVScraper, aciklama_yer_tutucu_mu
from .models import CVEEntry

# Yalniz NVD ailesi guncelleme yapar: Tenable'in skoru onem kovasinin sabitidir (Critical -> 9.5) ve
# NVD'nin analiz skorunu ezerdi; GHSA basliklari/aciklamalari ayri bir bicimdir.
GUNCELLEME_KAYNAKLARI = frozenset({'CISA KEV', 'NVD', 'NVD Güncel'})

# NVD Guncel son iki gunde degisen her CVE'yi getirir (2019'dan kalanlar dahil). Bunlar yeni kayit
# olarak yalniz yayin tarihi cekim penceresindeyse alinir; digerleri yalniz guncelleme tasir.
YALNIZ_GUNCELLEME_KAYNAGI = 'NVD Güncel'

# Bir turda cevrilip yazilan yeni CVE tavani. Tur kayit basina ~2 sn harcar (scraper zamani ceviri);
# 250 kayit ~8-9 dk, yumusak sinir 25 dk. Tavan disinda kalanlar silinmez: bir sonraki turda yine
# yenidir. Sira: KEV once, sonra CVSS buyukten kucuge; geride kalan dusuk skorlular pencereden
# cikabilir, kritikler kacmaz.
CVE_TUR_TAVANI = 250


def _alanlar(kayit: CVEEntry, cve: Dict) -> Dict:
    alanlar = {}
    if cve.get('cvss_score') is not None:
        alanlar['cvss_score'] = cve['cvss_score']
        if cve.get('severity'):
            alanlar['severity'] = cve['severity']
    if cve.get('modified_date'):
        alanlar['modified_date'] = cve['modified_date']
    if cve.get('cwe_ids'):
        alanlar['cwe_ids'] = list(cve['cwe_ids'])
    if cve.get('references'):
        alanlar['references'] = list(cve['references'])

    kev = cve.get('kev_added_date')
    if kev and kayit.kev_added_date != kev:
        alanlar['kev_added_date'] = kev
        # Kaynak filtresi "CISA KEV" sonradan KEV'e eklenenleri de gostersin
        alanlar['source'] = 'CISA KEV'
    if (kev or kayit.kev_added_date) and 'references' in alanlar \
            and CISAKEVScraper.KEV_KATALOG not in alanlar['references']:
        alanlar['references'] = [CISAKEVScraper.KEV_KATALOG] + alanlar['references'][:4]

    yeni_aciklama = cve.get('original_description') or ''
    if aciklama_yer_tutucu_mu(kayit.original_description) and not aciklama_yer_tutucu_mu(yeni_aciklama):
        alanlar.update(original_description=yeni_aciklama, turkish_description='',
                       needs_translation=True, translation_attempts=0, translation_provider='')
    return alanlar


def guncelle(kayit: CVEEntry, cve: Dict) -> bool:
    """`kayit`in ceviri disi alanlarini `cve` sozlugunden gunceller; degisiklik varsa kaydeder.

    Degismeyen kayit yazilmaz: updated_at (delta API imleci ve saklama penceresi) bosuna ilerlemesin.
    """
    if cve.get('source') not in GUNCELLEME_KAYNAKLARI:
        return False
    degisen = {ad: deger for ad, deger in _alanlar(kayit, cve).items() if getattr(kayit, ad) != deger}
    if not degisen:
        return False
    for ad, deger in degisen.items():
        setattr(kayit, ad, deger)
    kayit.save(update_fields=[*degisen, 'updated_at'])
    return True


def yeni_kayit_secimi(cves: List[Dict], days: int) -> List[Dict]:
    """Yeni kayit olarak islenecek CVE'ler: NVD Guncel'in pencere disi kayitlari elenir, KEV ve CVSS
    sirasiyla CVE_TUR_TAVANI kadari alinir."""
    pencere = timezone.localdate() - timedelta(days=days)
    uygun = [c for c in cves
             if c.get('source') != YALNIZ_GUNCELLEME_KAYNAGI
             or (c.get('published_date') and c['published_date'] >= pencere)]
    uygun.sort(key=lambda c: (c.get('kev_added_date') is None, -(c.get('cvss_score') or 0)))
    return uygun[:CVE_TUR_TAVANI]
