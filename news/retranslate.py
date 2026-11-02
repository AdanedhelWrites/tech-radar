"""Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir ve LibreTranslate
cevirilerini Gemini ile yukseltir (spec 2026-09-15-gemini-yukseltme, bolum 3.3).

Asama 1 — Bekleyenler (needs_translation=True): once Gemini kayit duzeyinde
(baslik + aciklama tek istek); cevrilemezse saglayici zinciri (LibreTranslate).
A3 plani netlestirme 8'deki imlec kurallari aynen gecerlidir: her bolum icin
Redis'te bir imlec ({prefix}:cursor:{bolum}); icerik yuzunden cevrilemeyen
kayit sirada kalir ama imlec onu gecer; sona gelinince imlec silinir. Gorev
yalnizca HICBIR saglayici (Gemini dahil) hazir degilse durur; imlec o kaydi gecmez.

Asama 2 — Yukseltme (needs_translation=False, translation_provider='libretranslate'),
yalnizca Gemini ile (spec 2026-11-02-ceviri-yayma G1-G2, G5 deneme sayaci). Imlec
yoktur: her tur en yeni adaylardan baslar (created_at azalan). Gemini tum alanlari
dogrulamadan gecirdiyse yazilir (hepsi ya da hicbiri, gemini.kaydi_cevir icinde);
Gemini hazirken reddederse (dogrulama, cok uzun kayit, k8s isaret kaybi) icerik
hatasidir ve translation_attempts artar, RETRANSLATE_MAX_ATTEMPTS'a ulasan kayit
aday olmaktan cikar. Gemini hazir degilse (anahtar yok / devre kesici / gunluk
butce) asama baslamaz ya da durur; sayac artmaz, kalanlar sonraki tura kalir. Bir bolumde
ARDISIK_HATA_SINIRI ardisik icerik hatasi gelirse o bolumun asamasi o tur durur
(sections[ad]['stopped_reason']='ardisik_icerik_hatasi'); kalanlar sayilmaz.
Eski 'google' etiketli kayitlar yukseltilmez.
`stopped_reason='gemini_budget'` iken `stopped` False olabilir: LibreTranslate zinciri surer.

Tur payi (spec 2026-11-02 G4): gunluk Gemini butcesi gunun kalan Beat turlarina yayilir; bir tur
en fazla ceil(kalan_butce / kalan_tur_sayisi) istek harcar (_Tur). Pay bitince yukseltme durur
(stopped_reason='gemini_tur_payi'; gunluk butce de bittiyse 'gemini_budget' onceliklidir), bekleyen
asamasi zincirle (LibreTranslate) surer. Pay bitmesi "Gemini hazir degil" sayilmaz (G6): kayit
icerik hatasi sayilmaz, sonraki turu bekler.

Onem sinifi (G1): CVE'lerde yalniz CVSS >= CVE_GEMINI_ESIGI ya da KEV'deki kayitlar
Gemini adayidir, iki asamada da; digerleri LibreTranslate cevirisiyle kalir.

Yazma kurallari:
  - Basarisiz denemede kayda yazilmaz: updated_at ilerlemez.
  - Basarida Turkce alanlar, needs_translation=False, translation_provider ve
    updated_at yazilir; ceviri delta akisindan tuketiciye gider.
"""
import os
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Dict, Optional
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import DatabaseError, OperationalError
from django.db.models import F, Q
from django.utils import timezone

from . import gemini
from . import translation_utils as tu
from .api_v1.cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
from .cache_utils import cache_yenile
from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)
import logging

log = logging.getLogger(__name__)

# Bolum basina. LibreTranslate yerel ve hizli oldugu icin bekleyen siniri yuksek.
RETRANSLATE_BATCH = int(os.environ.get('RETRANSLATE_BATCH', '100'))
# Yukseltme Gemini gunluk butcesini kullanir; asil sinir butcedir (gemini.GEMINI_DAILY_BUDGET).
RETRANSLATE_UPGRADE_BATCH = int(os.environ.get('RETRANSLATE_UPGRADE_BATCH', '40'))
# Icerik hatasi (saglayici reddetti / dogrulama gecmedi) bu kadar kez tekrarlanan kayit
# kuyruktan duser: needs_translation kalir ama sorgu onu elemez; status ucu
# translation_given_up ile sayar. 2026-10-08: ayni ~23 kayit her 2 saatte Gemini
# kotasi yiyerek yeniden reddediliyordu (turda 23-39 "hata", bekleyen toplam 23).
RETRANSLATE_MAX_ATTEMPTS = int(os.environ.get('RETRANSLATE_MAX_ATTEMPTS', '5'))
# Yukseltmede bir bolumde ayni turda bu kadar ardisik icerik hatasi gelirse bolumun asamasi o tur
# durur (sayilanlar sayili kalir, basari seriyi sifirlar). gemini.py'nin taniyamadigi yeni bir
# sistemik hata (orn. anahtar sorununun farkli bir yaniti) butun birikimi deneme tavanina itmesin.
ARDISIK_HATA_SINIRI = 5
# Spec 2026-11-02 G1 (kullanicinin karari): orta/dusuk CVE'ye Gemini kotasi harcanmaz.
# Esik ya da KEV kaydi aday yapar; skoru sonradan gelen kayit sonraki turda kendiliginden aday olur.
CVE_GEMINI_ESIGI = 7.0
# Tur sure butcesi (sn). 2026-10-21: SoftTimeLimitExceeded siradan bir Exception'dir; ceviri
# katmanindaki genis except'ler onu yutuyor, tur sert sinirda (1800 sn) olduruluyordu. Tur her
# kayittan once butceye bakar; yumusak sinirdan once temiz biter, imlec yerinde kalir. Pay, tek
# bir kaydin en uzun suresidir (10k karakter LibreTranslate parcalari + zaman asimlari).
RETRANSLATE_TIME_BUDGET = int(os.environ.get(
    'RETRANSLATE_TIME_BUDGET', str(max(60, settings.CELERY_TASK_SOFT_TIME_LIMIT - 300))))


def _sure_doldu(bitis) -> bool:
    return bitis is not None and time.monotonic() >= bitis


# Spec 2026-11-02 G4: Gemini gunluk butcesi bu Beat girdisinin turlarina yayilir (cybernews/settings.py).
RETRANSLATE_BEAT_ANAHTARI = 'retranslate-pending-hourly'
# Tur Beat anindan gec baslayabilir (kuyruk, onceki is): bu kadar geriye kadarki an simdiki turdur.
SIMDIKI_TUR_TOLERANSI = timedelta(minutes=30)


def kalan_tur_sayisi(simdi: datetime) -> int:
    """Simdiden sonraki Pasifik gece yarisina (Gemini gun donumu) kadar Beat'in retranslate turu
    calistiracagi an sayisi. Simdiki tur dahildir: simdi - 30 dk sonrasindaki ilk an.

    Takvimin hour/minute kumeleri okunur (gun/ay alanlari '*' varsayilir); saat dilimi Beat'inki,
    CELERY_TIMEZONE (Istanbul). En az 1: gunun son turu kalan butcenin tamamini alir, pay sonsuza kacmaz.
    """
    takvim = settings.CELERY_BEAT_SCHEDULE[RETRANSLATE_BEAT_ANAHTARI]['schedule']
    yerel = ZoneInfo(settings.CELERY_TIMEZONE)
    pasifik_gunu = simdi.astimezone(gemini.PASIFIK).date()
    gun_sonu = datetime.combine(pasifik_gunu + timedelta(days=1), datetime.min.time(), tzinfo=gemini.PASIFIK)
    alt = simdi - SIMDIKI_TUR_TOLERANSI
    # UTC'de saat saat yurunur, her saat yerel duvar saatine cevrilir (yaz saati gecisi saat atlatmaz)
    an = alt.astimezone(dt_timezone.utc).replace(minute=0, second=0, microsecond=0)
    sayi = 0
    while an < gun_sonu:
        yerel_an = an.astimezone(yerel)
        if yerel_an.hour in takvim.hour:
            for dakika in takvim.minute:
                aday = yerel_an.replace(minute=dakika, second=0, microsecond=0)
                if alt < aday < gun_sonu:
                    sayi += 1
        an += timedelta(hours=1)
    return max(1, sayi)


def tur_payi(simdi: datetime) -> int:
    """Bu turun Gemini istek payi: ceil(kalan gunluk butce / gunun kalan tur sayisi), en az 0.
    Kullanilmayan pay sonraki turlara kalir: kalan butce her turda yeniden hesaplanir."""
    kalan_butce = max(0, gemini.butce_tavani() - gemini.butce_kullanimi())
    return -(-kalan_butce // kalan_tur_sayisi(simdi))


class _Tur:
    """Bir retranslate turunun Gemini payi (G4). Harcama, turun basindaki gunluk sayaca gore olculur."""

    def __init__(self, pay: int, baslangic: int):
        self.pay = pay
        self.baslangic = baslangic

    def kalan(self) -> int:
        try:
            return max(0, self.pay - (gemini.butce_kullanimi() - self.baslangic))
        except Exception as hata:  # sayac okunamiyorsa Gemini'ye gidilmez (hazir() de False doner)
            log.warning(f"  [Retranslate] Gemini sayaci okunamadi, tur payi 0 sayiliyor: {hata}")
            return 0


def _turu_kur() -> '_Tur':
    try:
        return _Tur(pay=tur_payi(timezone.now()), baslangic=gemini.butce_kullanimi())
    except Exception as hata:  # sayac okunamazsa tur Gemini'siz (zincirle) surer, dusmez
        log.warning(f"  [Retranslate] Tur payi hesaplanamadi, pay 0: {hata}")
        return _Tur(pay=0, baslangic=0)


def _payi_var(tur: Optional[_Tur]) -> bool:
    """tur None: pay siniri yok (yalniz dogrudan cagrilar/testler; retranslate_pending hep tur kurar)."""
    return tur is None or tur.kalan() > 0


def _gemini_kullanilabilir(tur: Optional[_Tur]) -> bool:
    """Gemini hazir ve turun payi var mi. Pay bitmesi "hazir degil" sayilmaz (G6); ayri sebep yazilir."""
    return gemini.hazir() and _payi_var(tur)


def _basarisiz_say(kayit) -> None:
    """Icerik hatasi: deneme sayacini artirir (updated_at ilerlemez, delta akisina girmez)."""
    type(kayit).objects.filter(pk=kayit.pk).update(translation_attempts=F('translation_attempts') + 1)


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
        alanlar = {'description': aciklama} if len(aciklama) > 30 else {}
    else:
        taslak = {'title': (kayit.original_title or '').strip()}
        if aciklama:  # 2026-09-15 haber kurali: orijinal bossa Turkce govdeye dokunma
            taslak['description'] = aciklama
        alanlar = {alan: metin for alan, metin in taslak.items() if metin}

    uzunluk = sum(len(metin) for metin in alanlar.values())
    if uzunluk > gemini.GEMINI_MAX_CHARS:
        log.warning(f"  [Gemini] {ad} kaydi cok uzun ({uzunluk} kr), atlaniyor.")
        return {}
    return alanlar


def _gemini_adayi_mi(ad: str, kayit) -> bool:
    """Onem sinifi (G1): CVE icin CVSS >= esik ya da KEV; diger bolumlerde her kayit."""
    if ad != 'cve':
        return True
    return (kayit.cvss_score or 0) >= CVE_GEMINI_ESIGI or kayit.kev_added_date is not None


def _gemini_ile_cevir(ad: str, kayit, tur: Optional[_Tur] = None) -> Optional[Dict[str, str]]:
    """Kaydi Gemini ile cevirir; DB alan adlariyla sozluk ya da None
    (aday degil / hazir degil / tur payi bitti / cevrilemedi)."""
    if not _gemini_adayi_mi(ad, kayit):
        return None  # onem sinifi disi: istek atilmaz
    alanlar = _gemini_alanlari(ad, kayit)
    if not alanlar or not _gemini_kullanilabilir(tur):
        return None
    sonuc = gemini.kaydi_cevir(alanlar, ad)
    if sonuc is None:
        return None
    if ad == 'kubernetes' and 'description' in sonuc:
        for isaret in ('===SECTION:', '---ITEM---', '<<<PR#'):
            if alanlar['description'].count(isaret) != sonuc['description'].count(isaret):
                log.warning("  [Gemini] kubernetes yapisi bozuldu (isaret sayisi degisti).")
                return None
    return {_GEMINI_DB_ALANI[alan]: metin for alan, metin in sonuc.items()}


# Spec 2026-11-02 G3 (kullanicinin karari): Gemini butcesine bu sirayla erisilir; CVE rezervi
# yoktur, oncelik yalniz siradir. Sira butce dar oldugunda belirleyicidir.
BOLUMLER = (
    ('cve', CVEEntry, _cve),
    ('news', NewsArticle, _baslik_ve_uzun_aciklama),
    ('ai', AINewsEntry, _baslik_ve_uzun_aciklama),
    ('sre', SREEntry, _baslik_ve_uzun_aciklama),
    ('devtools', DevToolsEntry, _baslik_ve_uzun_aciklama),
    ('kubernetes', KubernetesEntry, _kubernetes),
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


def _yaz(kayit, alanlar, saglayici) -> bool:
    """Ceviriyi kayda yazar. False: kayit artik yok, atlanmali.

    Kayit tur ortasinda silinmisse (ornegin views.clear_cve_cache eszamanli
    calisti) update_fields ile yapilan save 0 satir gunceller ve Django
    DatabaseError atar. Bu tum turu dusurmek icin sebep degildir: kayit gitmistir,
    atlanir ve imlec ilerler (2026-09-18: boyle bir istisna bir retranslate turunu
    comertti, o turda diger bolumler hic yukseltme almadi).

    OperationalError (ornegin 'database is locked') gecici bir altyapi hatasidir,
    kaydin yoklugu degil; yutulmaz, yukari cikar.
    """
    for alan, deger in alanlar.items():
        setattr(kayit, alan, deger)
    kayit.needs_translation = False
    kayit.translation_provider = saglayici
    kayit.translation_attempts = 0
    try:
        kayit.save(update_fields=[*alanlar, 'needs_translation', 'translation_provider',
                                  'translation_attempts', 'updated_at'])
    except OperationalError:
        raise
    except DatabaseError:
        log.warning(f"  [Retranslate] kayit {kayit.pk} tur ortasinda silinmis, atlaniyor.")
        return False
    return True


def _bekleyenler(ad, model, cevir, redis_client, prefix, sinir, sonuc, bitis=None, tur=None):
    """Asama 1. Donus: (cevrilen, basarisiz, durdu). Tur payi bitince kayitlar zincirle cevrilir."""
    anahtar = f'{prefix}:cursor:{ad}'
    sorgu = (model.objects.filter(needs_translation=True, translation_attempts__lt=RETRANSLATE_MAX_ATTEMPTS)
             .order_by('updated_at', 'id'))
    kayitlar = _imlecten_sonraki(redis_client, anahtar, sorgu, sinir)

    cevrilen = basarisiz = 0
    durdu = False
    for kayit in kayitlar:
        if _sure_doldu(bitis):
            durdu = True  # imlec ilerlemez: sonraki tur bu kayittan baslar
            break
        if not (tu.herhangi_saglayici_hazir() or gemini.hazir()):
            durdu = True
            break
        deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)

        payi_vardi = _payi_var(tur)  # istek oncesi: pay bittiyse istek atilmadi, red sayilmaz
        gemini_alanlar = _gemini_ile_cevir(ad, kayit, tur)
        if gemini_alanlar is not None:
            if _yaz(kayit, gemini_alanlar, 'gemini'):
                cevrilen += 1
                sonuc['by_provider']['gemini'] += 1
            redis_client.set(anahtar, deneme_oncesi)
            continue

        if gemini_alanlar is None and not tu.herhangi_saglayici_hazir():
            if payi_vardi and gemini.hazir() and _gemini_adayi_mi(ad, kayit) and _gemini_alanlari(ad, kayit):
                # Gemini hazirdi ama icerigi reddetti; zincir kapali: icerik hatasi say, imlec gecsin.
                # Aday olmayan kayit (orta CVE) ya da tur payi bitmis Gemini icin bu turda saglayici
                # yoktur: asagida durulur, imlec ilerlemez, sayac artmaz.
                basarisiz += 1
                _basarisiz_say(kayit)
                redis_client.set(anahtar, deneme_oncesi)
                continue
            durdu = True  # ne Gemini ne zincir: imleci ilerletme
            break
        alanlar, hata, kullanilan = _cevir_ve_olc(cevir, kayit)

        if hata:
            if not tu.herhangi_saglayici_hazir():
                # Erisim sorunu: imleci ilerletme, bir sonraki tur once bu kaydi denesin. Ama devre
                # kesiciyi kaydin kendisi aciyor olabilir (2026-10-16: 102k karakterlik bir haber her turda
                # LibreTranslate'i ReadTimeout'a dusurdu, retranslate 3 gun ayni kayitta kaldi). Sayac
                # artmazsa boyle bir kayit kuyrugu sonsuza dek kilitler; artarsa en gec
                # RETRANSLATE_MAX_ATTEMPTS turda kuyruktan duser. Gercek kesintide bedel: bastaki
                # kayit tur basina bir deneme kaybeder.
                _basarisiz_say(kayit)
                durdu = True
                break
            basarisiz += 1  # icerik hatasi: imlec gecer, kayit sirada kalir (sayac esigine kadar)
            _basarisiz_say(kayit)
        else:
            saglayici = tu.kayit_saglayicisi(kullanilan)
            if _yaz(kayit, alanlar, saglayici):
                cevrilen += 1
                if saglayici:
                    sonuc['by_provider'][saglayici] = sonuc['by_provider'].get(saglayici, 0) + 1
        redis_client.set(anahtar, deneme_oncesi)

    if not durdu and len(kayitlar) < sinir:
        redis_client.delete(anahtar)  # sona gelindi; bir sonraki tur bastan
    return cevrilen, basarisiz, durdu


def _yukseltme_adaylari(ad, model, sinir) -> list:
    """En yeni yukseltme adaylari (G2). Sorgu guncel skora bakar: NVD skoru sonradan
    esigi gecen CVE sonraki turda kendiliginden aday olur."""
    sorgu = model.objects.filter(needs_translation=False, translation_provider='libretranslate',
                                 translation_attempts__lt=RETRANSLATE_MAX_ATTEMPTS)
    if ad == 'cve':
        sorgu = sorgu.filter(Q(cvss_score__gte=CVE_GEMINI_ESIGI) | Q(kev_added_date__isnull=False))
    return list(sorgu.order_by('-created_at', '-id')[:sinir])


def _gemini_sebebini_yaz(sonuc, tur=None) -> None:
    """Gemini durduysa sebebi turun stopped_reason'ina yazar: gunluk butce onceliklidir; tur payi
    yalniz baska sebep yazilmamissa yazilir. Yalniz devre kesici aciksa sebep yazilmaz."""
    if not gemini.butce_var():
        sonuc['stopped_reason'] = 'gemini_budget'
    elif not _payi_var(tur) and sonuc.get('stopped_reason') is None:
        sonuc['stopped_reason'] = 'gemini_tur_payi'


def _yukselt(ad, model, sinir, sonuc, bitis=None, tur=None):
    """Asama 2. Yalnizca Gemini, imlecsiz. Donus: (yukseltilen, basarisiz). Tur payi bitince durur."""
    if not _gemini_kullanilabilir(tur):
        _gemini_sebebini_yaz(sonuc, tur)
        return 0, 0

    yukseltilen = basarisiz = ardisik = 0
    for kayit in _yukseltme_adaylari(ad, model, sinir):
        if _sure_doldu(bitis):
            break
        if ardisik >= ARDISIK_HATA_SINIRI:
            # Kalan adaylar sayilmadan sonraki tura kalir; tur duzeyi stopped_reason'a dokunulmaz
            sonuc.setdefault('sections', {}).setdefault(ad, {})['stopped_reason'] = 'ardisik_icerik_hatasi'
            log.warning(f"  [Retranslate] {ad}: {ardisik} ardisik Gemini reddi, yukseltme bu tur durdu.")
            break
        if not _gemini_kullanilabilir(tur):
            # butce/devre kesici/tur payi asama ortasinda: kalanlar sonraki tura
            _gemini_sebebini_yaz(sonuc, tur)
            break
        alanlar = _gemini_ile_cevir(ad, kayit, tur)
        if alanlar is None:
            # Pay donguye girerken vardi; burada yalniz hazir() bakilir. Payin son istegi icerik
            # reddi olduysa o da sayilmali; pay bitmesi bir sonraki adimda yakalanir.
            if not gemini.hazir():
                # Istek duzeyi hata (429/5xx/ag/401/403/404) ya da butce: kaydin sucu degil, sayac artmaz
                _gemini_sebebini_yaz(sonuc, tur)
                break
            # Gemini hazirken reddetti (dogrulama / cok uzun / k8s isaret kaybi / 400): icerik hatasi.
            # Sayilmazsa "en yeni N aday" sorgusu ayni kaydi her tur yeniden dener (G5).
            basarisiz += 1
            ardisik += 1
            _basarisiz_say(kayit)
            continue
        ardisik = 0
        if _yaz(kayit, alanlar, 'gemini'):
            yukseltilen += 1
    return yukseltilen, basarisiz


def retranslate_pending(redis_client=None, prefix: str = 'retranslate',
                        batch: int = None, upgrade_batch: int = None, sure_butcesi: int = None,
                        tur: Optional[_Tur] = None) -> Dict:
    """tur None ise pay simdiki andan kurulur (tur_payi); testler sabit pay verir."""
    redis_client = redis_client or _canli_redis()
    sure_butcesi = RETRANSLATE_TIME_BUDGET if sure_butcesi is None else sure_butcesi
    bitis = time.monotonic() + sure_butcesi
    batch = RETRANSLATE_BATCH if batch is None else batch
    upgrade_batch = RETRANSLATE_UPGRADE_BATCH if upgrade_batch is None else upgrade_batch
    tur = _turu_kur() if tur is None else tur
    sonuc = {'translated': 0, 'failed': 0, 'upgraded': 0, 'stopped': False, 'stopped_reason': None,
             'gemini_tur_payi': tur.pay,
             'by_provider': {'gemini': 0, 'libretranslate': 0}, 'sections': {}}

    for ad, model, cevir in BOLUMLER:
        if _sure_doldu(bitis):
            sonuc['stopped'] = True
            sonuc['stopped_reason'] = 'time_budget'
            break
        if not (tu.herhangi_saglayici_hazir() or gemini.hazir()):
            sonuc['stopped'] = True
            sonuc['stopped_reason'] = 'no_provider'
            break

        cevrilen, basarisiz, durdu = _bekleyenler(ad, model, cevir, redis_client, prefix, batch, sonuc,
                                                  bitis, tur)
        yukseltilen, yukseltme_basarisiz = ((0, 0) if durdu
                                            else _yukselt(ad, model, upgrade_batch, sonuc, bitis, tur))
        basarisiz += yukseltme_basarisiz  # iki asamanin icerik hatalari tek 'failed' sayacinda

        if cevrilen or yukseltilen:
            cache_yenile(ad)
        # update: _yukselt bolum satirina stopped_reason yazmis olabilir (ardisik icerik hatasi)
        sonuc['sections'].setdefault(ad, {}).update(
            {'translated': cevrilen, 'failed': basarisiz, 'upgraded': yukseltilen})
        sonuc['translated'] += cevrilen
        sonuc['failed'] += basarisiz
        sonuc['upgraded'] += yukseltilen

        if _sure_doldu(bitis):
            sonuc['stopped'] = True
            sonuc['stopped_reason'] = 'time_budget'
            break
        if durdu:
            # Bolum durdu ama tur bitmez: diger bolumler hazir bir saglayiciyla (cogunlukla Gemini)
            # islenmeye devam eder. Dongunun basindaki kontrol hicbir saglayici kalmadiysa turu bitirir.
            # 2026-10-16: haberdeki tek bir kayit k8s/sre/devtools/ai'yi 3 gun hic islenmeden birakti.
            sonuc['stopped'] = True
            sonuc['stopped_reason'] = 'no_provider'

    return sonuc
