# Celery tasks
from celery import shared_task
from django.core.cache import cache
from datetime import timedelta, date

from .models import NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry
from .translation_utils import consume_translation_failures
from .cache_utils import CACHE_YENILEME_ARALIGI, cache_yenile

from scraper_multi import MultiSourceScraper
from .cve_scraper import MultiCVEScraper
from .k8s_scraper import MultiK8sScraper
from .sre_scraper import MultiSREScraper
from .devtools_scraper import MultiDevToolsScraper
from .ai_scraper import MultiAINewsScraper


def _drop_existing(entries, model, field, key='link'):
    """Veritabaninda zaten cevrilmis olan kayitlari listeden cikarir (tekrar cevrilmesin diye).
    Ceviri bekleyen (needs_translation) kayitlar listede kalir ve yeniden islenir.
    Ucretsiz Google Translate kotasini korumak icin kullanilir."""
    keys = [e.get(key) for e in entries if e.get(key)]
    existing = set(model.objects.filter(**{f'{field}__in': keys}, needs_translation=False)
                   .values_list(field, flat=True))
    return [e for e in entries if e.get(key) not in existing]


# Not: `needs_translation` degeri, generator kaydi cevirip yield ettikten sonra
# okunur; consume_translation_failures() sayaci her kayitta sifirlar.
#
# Cache: her CACHE_YENILEME_ARALIGI kayitta bir ve cekim sonunda yeniden kurulur
# (bkz. news/cache_utils.py).

@shared_task
def fetch_news_task(days=7, selected_sources=None, clear_existing=False, skip_existing=True):
    try:
        # Eski cache ve gun araliginin disindaki kayitlari temizle
        cache.delete('cybersecurity_news')
        cache.delete('last_update')
        cutoff = date.today() - timedelta(days=days)
        NewsArticle.objects.filter(date__lt=cutoff).delete()

        scraper = MultiSourceScraper()
        articles = scraper.fetch_all_news(days=days, selected_sources=selected_sources)
        if skip_existing:
            articles = _drop_existing(articles, NewsArticle, 'link')
        if articles:
            saved_count = 0
            consume_translation_failures()
            for article in scraper.process_news(articles):
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
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('news')
            cache_yenile('news')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_cve_task(days=7, selected_sources=None, skip_existing=True):
    try:
        cache.delete('cve_entries')
        cache.delete('cve_last_update')
        cutoff = date.today() - timedelta(days=days)
        CVEEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiCVEScraper()
        cves = scraper.fetch_all_cves(days=days, selected_sources=selected_sources)
        if skip_existing:
            cves = _drop_existing(cves, CVEEntry, 'cve_id', key='cve_id')
        if cves:
            saved_count = 0
            consume_translation_failures()
            for cve in scraper.process_cves(cves):
                CVEEntry.objects.update_or_create(
                    cve_id=cve['cve_id'],
                    defaults={
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
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('cve')
            cache_yenile('cve')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_k8s_task(days=30, selected_sources=None, skip_existing=True):
    try:
        cache.delete('k8s_entries')
        cache.delete('k8s_last_update')
        cutoff = date.today() - timedelta(days=days)
        KubernetesEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiK8sScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        if skip_existing:
            entries = _drop_existing(entries, KubernetesEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            for entry in scraper.process_entries(entries):
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
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('kubernetes')
            cache_yenile('kubernetes')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_sre_task(days=30, selected_sources=None, skip_existing=True):
    try:
        cache.delete('sre_entries')
        cache.delete('sre_last_update')
        cutoff = date.today() - timedelta(days=days)
        SREEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiSREScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        if skip_existing:
            entries = _drop_existing(entries, SREEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            for entry in scraper.process_entries(entries):
                SREEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'published_date': entry['published_date'],
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('sre')
            cache_yenile('sre')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_devtools_task(days=30, selected_sources=None, skip_existing=True):
    try:
        cache.delete('devtools_entries')
        cache.delete('devtools_last_update')
        cutoff = date.today() - timedelta(days=days)
        DevToolsEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiDevToolsScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        if skip_existing:
            entries = _drop_existing(entries, DevToolsEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            for entry in scraper.process_entries(entries):
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
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('devtools')
            cache_yenile('devtools')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_ai_news_task(days=30, selected_sources=None, skip_existing=True):
    try:
        cache.delete('ai_entries')
        cache.delete('ai_last_update')
        cutoff = date.today() - timedelta(days=days)
        AINewsEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiAINewsScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        if skip_existing:
            entries = _drop_existing(entries, AINewsEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            for entry in scraper.process_entries(entries):
                AINewsEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'published_date': entry.get('published_date') or entry.get('date'),
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('ai')
            cache_yenile('ai')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}
