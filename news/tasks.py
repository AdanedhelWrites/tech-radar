# Celery tasks
import os
import uuid
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from .models import NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry
from .translation_utils import (
    consume_translation_failures, consume_translation_providers, kayit_saglayicisi,
)
from .kaynaklar import kayit_tavani, kaynak_sayaclari, kaynak_yazildi

from scraper_multi import MultiSourceScraper
from .cve_scraper import MultiCVEScraper
from . import cve_guncelleme
from .k8s_scraper import MultiK8sScraper
from .sre_scraper import MultiSREScraper
from .devtools_scraper import MultiDevToolsScraper
from .ai_scraper import MultiAINewsScraper
import logging

log = logging.getLogger(__name__)


# ADR-0005: saklama olcusu "kaydin yayim tarihi" degil "bu kayda en son ne zaman
# dokunduk"tur. published_date'e bakmak sil/yeniden yaz dongusune yol aciyordu:
# NVD Guncel akisi eski yayimlanmis ama yeni guncellenmis CVE'leri donuyor, biz
# onlari siliyor, kaynak tekrar donuyor, update_or_create yeni id ile yaziyordu.
RETENTION_DAYS = int(os.environ.get('RETENTION_DAYS', '90'))


def _saklama_temizligi(model):
    """Saklama penceresi disinda kalan kayitlari siler.

    Cekim penceresinden (task'larin `days` parametresi) bagimsizdir: `days`
    kaynaktan ne kadar geriye gidilecegini belirler, bu fonksiyon veritabaninda
    ne kadar kalinacagini.
    """
    cutoff = timezone.now() - timedelta(days=RETENTION_DAYS)
    model.objects.filter(updated_at__lt=cutoff).delete()


def _drop_existing(entries, model, field, key='link'):
    """Veritabaninda zaten cevrilmis olan kayitlari listeden cikarir (tekrar cevrilmesin diye).
    Ceviri bekleyen (needs_translation) kayitlar listede kalir ve yeniden islenir.
    Ceviri saglayicisinin yukunu/kotasini korumak icin kullanilir."""
    keys = [e.get(key) for e in entries if e.get(key)]
    existing = set(model.objects.filter(**{f'{field}__in': keys}, needs_translation=False)
                   .values_list(field, flat=True))
    return [e for e in entries if e.get(key) not in existing]


# Not: `needs_translation` degeri, generator kaydi cevirip yield ettikten sonra
# okunur; consume_translation_failures() sayaci her kayitta sifirlar.
# translation_provider ayni anda okunur: kaydin cevirisinde kullanilan
# saglayicilarin en dusuk kalitelisi (bkz. translation_utils.kayit_saglayicisi).

@shared_task
def fetch_news_task(days=7, selected_sources=None, clear_existing=False, skip_existing=True):
    try:
        # Saklama penceresi disindaki kayitlari temizle
        _saklama_temizligi(NewsArticle)

        scraper = MultiSourceScraper()
        articles = scraper.fetch_all_news(days=days, selected_sources=selected_sources, sinirla=False)
        kaynaktan_gelen = len(articles)  # _drop_existing'den ONCE: kaynaktan kac kayit geldi
        kaynak_sayaci = kaynak_sayaclari('news', selected_sources, articles)
        if skip_existing:
            articles = _drop_existing(articles, NewsArticle, 'link')
        articles = kayit_tavani(articles, len(kaynak_sayaci))
        if articles:
            saved_count = 0
            consume_translation_failures()
            consume_translation_providers()
            ceviri_hatalari = 0
            for article in scraper.process_news(articles):
                basarisizlik = consume_translation_failures()
                ceviri_hatalari += basarisizlik
                NewsArticle.objects.update_or_create(
                    link=article['link'],
                    defaults={
                        'source': article['source'],
                        'original_title': article['original_title'],
                        'turkish_title': article['turkish_title'],
                        'original_description': article.get('original_description', ''),
                        'turkish_description': article.get('turkish_description', ''),
                        'turkish_summary': article.get('turkish_summary', ''),
                        'date': article['date'],
                        'original_date': article.get('original_date', ''),
                        'needs_translation': basarisizlik > 0,
                        'translation_provider': kayit_saglayicisi(consume_translation_providers()),
                    }
                )
                saved_count += 1
                kaynak_yazildi(kaynak_sayaci, article['source'])
            return {'success': True, 'count': saved_count,
                    'fetched_count': kaynaktan_gelen, 'translation_failures': ceviri_hatalari,
                    'by_source': kaynak_sayaci}
        return {'success': False, 'count': 0,
                'fetched_count': kaynaktan_gelen, 'translation_failures': 0,
                'by_source': kaynak_sayaci}
    except Exception as e:
        # Tur adi da yazilir: SoftTimeLimitExceeded'in metni bostur, FetchRun.error'da gorunsun
        return {'success': False, 'error': f'{type(e).__name__}: {e}'}

@shared_task
def fetch_cve_task(days=7, selected_sources=None, skip_existing=True):
    try:
        _saklama_temizligi(CVEEntry)

        scraper = MultiCVEScraper()
        cves = scraper.fetch_all_cves(days=days, selected_sources=selected_sources)
        kaynaktan_gelen = len(cves)  # _drop_existing'den ONCE: kaynaktan kac kayit geldi
        kaynak_sayaci = kaynak_sayaclari('cve', selected_sources, cves)
        if skip_existing:
            # Cevrilmis CVE'ler yeniden cevrilmez ama ceviri disi alanlari (KEV, CVSS, yer tutucu
            # aciklama) guncellenir (cve_guncelleme, 2026-11-07); yalniz yeniler ve bekleyenler kalir.
            mevcut = {k.cve_id: k for k in CVEEntry.objects.filter(
                cve_id__in=[c['cve_id'] for c in cves], needs_translation=False)}
            yeniler = []
            for cve in cves:
                kayit = mevcut.get(cve['cve_id'])
                if kayit is None:
                    yeniler.append(cve)
                elif cve_guncelleme.guncelle(kayit, cve):
                    sayac = kaynak_sayaci.setdefault(cve['source'], {'fetched': 0, 'saved': 0})
                    sayac['updated'] = sayac.get('updated', 0) + 1
            cves = yeniler
        cves = cve_guncelleme.yeni_kayit_secimi(cves, days)
        if cves:
            saved_count = 0
            consume_translation_failures()
            consume_translation_providers()
            ceviri_hatalari = 0
            for cve in scraper.process_cves(cves):
                basarisizlik = consume_translation_failures()
                ceviri_hatalari += basarisizlik
                defaults = {
                    'source': cve['source'],
                    'original_title': cve['original_title'],
                    'turkish_title': cve.get('turkish_title', ''),
                    'original_description': cve.get('original_description', ''),
                    'turkish_description': cve.get('turkish_description', ''),
                    'severity': cve.get('severity', 'Bilinmiyor'),
                    'cvss_score': cve.get('cvss_score'),
                    'published_date': cve.get('published_date'),
                    'modified_date': cve.get('modified_date'),
                    'link': cve.get('link', ''),
                    'cwe_ids': cve.get('cwe_ids', []),
                    'references': cve.get('references', []),
                    'affected_products': cve.get('affected_products', ''),
                    'needs_translation': basarisizlik > 0,
                    'translation_provider': kayit_saglayicisi(consume_translation_providers()),
                }
                # KEV tarihi yalniz KEV kaynagi verdiginde yazilir: ayni CVE'yi NVD yolu yeniden
                # yazdiginda (anahtar yok) mevcut tarih None ile ezilmesin
                if cve.get('kev_added_date'):
                    defaults['kev_added_date'] = cve['kev_added_date']
                CVEEntry.objects.update_or_create(cve_id=cve['cve_id'], defaults=defaults)
                saved_count += 1
                kaynak_yazildi(kaynak_sayaci, cve['source'])
            return {'success': True, 'count': saved_count,
                    'fetched_count': kaynaktan_gelen, 'translation_failures': ceviri_hatalari,
                    'by_source': kaynak_sayaci}
        return {'success': False, 'count': 0,
                'fetched_count': kaynaktan_gelen, 'translation_failures': 0,
                'by_source': kaynak_sayaci}
    except Exception as e:
        # Tur adi da yazilir: SoftTimeLimitExceeded'in metni bostur, FetchRun.error'da gorunsun
        return {'success': False, 'error': f'{type(e).__name__}: {e}'}

@shared_task
def fetch_k8s_task(days=30, selected_sources=None, skip_existing=True):
    try:
        _saklama_temizligi(KubernetesEntry)

        scraper = MultiK8sScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        kaynaktan_gelen = len(entries)  # _drop_existing'den ONCE: kaynaktan kac kayit geldi
        kaynak_sayaci = kaynak_sayaclari('kubernetes', selected_sources, entries)
        if skip_existing:
            entries = _drop_existing(entries, KubernetesEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            consume_translation_providers()
            ceviri_hatalari = 0
            for entry in scraper.process_entries(entries):
                basarisizlik = consume_translation_failures()
                ceviri_hatalari += basarisizlik
                KubernetesEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'category': entry.get('category', 'blog'),
                        'version': entry.get('version', ''),
                        'published_date': entry['published_date'],
                        'needs_translation': basarisizlik > 0,
                        'translation_provider': kayit_saglayicisi(consume_translation_providers()),
                    }
                )
                saved_count += 1
                kaynak_yazildi(kaynak_sayaci, entry['source'])
            return {'success': True, 'count': saved_count,
                    'fetched_count': kaynaktan_gelen, 'translation_failures': ceviri_hatalari,
                    'by_source': kaynak_sayaci}
        return {'success': False, 'count': 0,
                'fetched_count': kaynaktan_gelen, 'translation_failures': 0,
                'by_source': kaynak_sayaci}
    except Exception as e:
        # Tur adi da yazilir: SoftTimeLimitExceeded'in metni bostur, FetchRun.error'da gorunsun
        return {'success': False, 'error': f'{type(e).__name__}: {e}'}

@shared_task
def fetch_sre_task(days=30, selected_sources=None, skip_existing=True):
    try:
        _saklama_temizligi(SREEntry)

        scraper = MultiSREScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources, sinirla=False)
        kaynaktan_gelen = len(entries)  # _drop_existing'den ONCE: kaynaktan kac kayit geldi
        kaynak_sayaci = kaynak_sayaclari('sre', selected_sources, entries)
        if skip_existing:
            entries = _drop_existing(entries, SREEntry, 'link')
        entries = kayit_tavani(entries, len(kaynak_sayaci))
        if entries:
            saved_count = 0
            consume_translation_failures()
            consume_translation_providers()
            ceviri_hatalari = 0
            for entry in scraper.process_entries(entries):
                basarisizlik = consume_translation_failures()
                ceviri_hatalari += basarisizlik
                SREEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'published_date': entry['published_date'],
                        'needs_translation': basarisizlik > 0,
                        'translation_provider': kayit_saglayicisi(consume_translation_providers()),
                    }
                )
                saved_count += 1
                kaynak_yazildi(kaynak_sayaci, entry['source'])
            return {'success': True, 'count': saved_count,
                    'fetched_count': kaynaktan_gelen, 'translation_failures': ceviri_hatalari,
                    'by_source': kaynak_sayaci}
        return {'success': False, 'count': 0,
                'fetched_count': kaynaktan_gelen, 'translation_failures': 0,
                'by_source': kaynak_sayaci}
    except Exception as e:
        # Tur adi da yazilir: SoftTimeLimitExceeded'in metni bostur, FetchRun.error'da gorunsun
        return {'success': False, 'error': f'{type(e).__name__}: {e}'}

@shared_task
def fetch_devtools_task(days=30, selected_sources=None, skip_existing=True):
    try:
        _saklama_temizligi(DevToolsEntry)

        scraper = MultiDevToolsScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources, sinirla=False)
        kaynaktan_gelen = len(entries)  # _drop_existing'den ONCE: kaynaktan kac kayit geldi
        kaynak_sayaci = kaynak_sayaclari('devtools', selected_sources, entries)
        if skip_existing:
            entries = _drop_existing(entries, DevToolsEntry, 'link')
        entries = kayit_tavani(entries, len(kaynak_sayaci))
        if entries:
            saved_count = 0
            consume_translation_failures()
            consume_translation_providers()
            ceviri_hatalari = 0
            for entry in scraper.process_entries(entries):
                basarisizlik = consume_translation_failures()
                ceviri_hatalari += basarisizlik
                DevToolsEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'version': entry.get('version', ''),
                        'entry_type': entry.get('entry_type', 'release'),
                        'published_date': entry['published_date'],
                        'needs_translation': basarisizlik > 0,
                        'translation_provider': kayit_saglayicisi(consume_translation_providers()),
                    }
                )
                saved_count += 1
                kaynak_yazildi(kaynak_sayaci, entry['source'])
            return {'success': True, 'count': saved_count,
                    'fetched_count': kaynaktan_gelen, 'translation_failures': ceviri_hatalari,
                    'by_source': kaynak_sayaci}
        return {'success': False, 'count': 0,
                'fetched_count': kaynaktan_gelen, 'translation_failures': 0,
                'by_source': kaynak_sayaci}
    except Exception as e:
        # Tur adi da yazilir: SoftTimeLimitExceeded'in metni bostur, FetchRun.error'da gorunsun
        return {'success': False, 'error': f'{type(e).__name__}: {e}'}

@shared_task
def fetch_ai_news_task(days=30, selected_sources=None, skip_existing=True):
    try:
        _saklama_temizligi(AINewsEntry)

        scraper = MultiAINewsScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        kaynaktan_gelen = len(entries)  # _drop_existing'den ONCE: kaynaktan kac kayit geldi
        kaynak_sayaci = kaynak_sayaclari('ai', selected_sources, entries)
        if skip_existing:
            entries = _drop_existing(entries, AINewsEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            consume_translation_providers()
            ceviri_hatalari = 0
            for entry in scraper.process_entries(entries):
                basarisizlik = consume_translation_failures()
                ceviri_hatalari += basarisizlik
                AINewsEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'published_date': entry.get('published_date') or entry.get('date'),
                        'needs_translation': basarisizlik > 0,
                        'translation_provider': kayit_saglayicisi(consume_translation_providers()),
                    }
                )
                saved_count += 1
                kaynak_yazildi(kaynak_sayaci, entry['source'])
            return {'success': True, 'count': saved_count,
                    'fetched_count': kaynaktan_gelen, 'translation_failures': ceviri_hatalari,
                    'by_source': kaynak_sayaci}
        return {'success': False, 'count': 0,
                'fetched_count': kaynaktan_gelen, 'translation_failures': 0,
                'by_source': kaynak_sayaci}
    except Exception as e:
        # Tur adi da yazilir: SoftTimeLimitExceeded'in metni bostur, FetchRun.error'da gorunsun
        return {'success': False, 'error': f'{type(e).__name__}: {e}'}


# Tekil calisma kilidi (spec 2026-11-02 G4): saatlik turlar ust uste binmesin.
RETRANSLATE_KILIT_ANAHTARI = 'retranslate:kilit'


def _retranslate_kilidi_al():
    """Kilidi almaya calisir. Donus: (redis_istemcisi, jeton, alindi).

    Redis'e ulasilamazsa tur KAYBEDILMEZ: uyarilir, kilitsiz kosulur (alindi=True, istemci None).
    Kilit alinamadiysa (baska tur tutuyor) alindi=False doner.
    """
    from .retranslate import RETRANSLATE_TIME_BUDGET, _canli_redis
    jeton = uuid.uuid4().hex
    try:
        redis_client = _canli_redis()
        # Omur: tur butcesi + 600 sn pay, ama en fazla sert sinir + 60 sn (tur bundan uzun yasayamaz).
        # Worker olurse kilit en gec bu surede kendiliginden duser; butce env ile buyutulse de
        # olu kilit sonraki saatlik turu atlatmaz.
        omur = min(RETRANSLATE_TIME_BUDGET + 600, settings.CELERY_TASK_TIME_LIMIT + 60)
        alindi = bool(redis_client.set(RETRANSLATE_KILIT_ANAHTARI, jeton, nx=True, ex=omur))
    except Exception as e:
        log.warning(f'  [retranslate] Kilit alinamadi (Redis?), tur kilitsiz kosuluyor: {e}')
        return None, jeton, True
    return redis_client, jeton, alindi


def _retranslate_kilidini_birak(redis_client, jeton):
    """Kilidi yalniz sahibiyse siler. get+delete atomik degildir: kilidin tam bu iki cagri arasinda
    dusup baskasina gecmesi icin TTL'nin (bkz. _retranslate_kilidi_al) bitmesi gerekir; tek worker sureci ve
    saatlik tur icin bu risk kabul edildi, Lua betigi gereksiz."""
    if redis_client is None:
        return
    try:
        mevcut = redis_client.get(RETRANSLATE_KILIT_ANAHTARI)
        if isinstance(mevcut, bytes):
            mevcut = mevcut.decode()
        if mevcut == jeton:
            redis_client.delete(RETRANSLATE_KILIT_ANAHTARI)
    except Exception as e:
        log.warning(f'  [retranslate] Kilit birakilamadi (TTL ile dusecek): {e}')


@shared_task
def retranslate_pending_task():
    """Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir (bkz. news/retranslate.py).

    Onceki tur hala kilidi tutuyorsa {'skipped': 'locked'} doner (FetchRun satiri birakilmaz,
    bkz. fetch_runs.tur_bitti).
    """
    from .fetch_runs import eski_kayitlari_temizle
    from .retranslate import retranslate_pending
    redis_client, jeton, alindi = _retranslate_kilidi_al()
    if not alindi:
        log.info('  [retranslate] Onceki tur suruyor, bu tur atlandi')
        return {'skipped': 'locked'}
    try:
        sonuc = retranslate_pending()
        # Saklama temizligi asil isin sonucunu etkilememeli: sinyal katmaniyla ayni
        # savunmaci kalip (bkz. fetch_runs.py) - burada da task'in donusunu bozmaz.
        try:
            eski_kayitlari_temizle()  # 30 gunden eski FetchRun satirlari (spec 3.4)
        except Exception as e:
            log.warning(f'  [FetchRun] Eski kayitlar temizlenemedi: {e}')
        return sonuc
    finally:
        _retranslate_kilidini_birak(redis_client, jeton)
