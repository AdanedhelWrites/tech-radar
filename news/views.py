import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from datetime import datetime
from .models import (
    NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry
)
from .api_v1 import refresh
from .serializers import (
    NewsArticleSerializer, FetchNewsRequestSerializer,
    CVEEntrySerializer, FetchCVERequestSerializer,
    KubernetesEntrySerializer, FetchK8sRequestSerializer,
    SREEntrySerializer, FetchSRERequestSerializer,
    DevToolsEntrySerializer, FetchDevToolsRequestSerializer,
    AINewsEntrySerializer, FetchAINewsRequestSerializer,
    StatsSerializer
)
from scraper_multi import MultiSourceScraper
from .cve_scraper import MultiCVEScraper
from .k8s_scraper import MultiK8sScraper
from .sre_scraper import MultiSREScraper
from .devtools_scraper import MultiDevToolsScraper
from .ai_scraper import MultiAINewsScraper

logger = logging.getLogger(__name__)

# Istemciye donen genel hata mesaji; gercek istisna sunucu loguna yazilir,
# yanit govdesine iceri yapisi/dosya yollari/sorgu metnini sizdirmaz.
GENEL_SUNUCU_HATASI = 'Islem sirasinda sunucuda beklenmeyen bir hata olustu.'


# Eski /api/*/fetch/ uclari: bolum -> (istek serializer'i, silinecek frontend cache
# anahtarlari, mesajdaki ad). Bolum adlari news/api_v1/refresh.py::SECTIONS ile ayni.
_FETCH_BOLUMLERI = {
    'news': (FetchNewsRequestSerializer, ('cybersecurity_news', 'last_update'), 'Haber'),
    'cve': (FetchCVERequestSerializer, ('cve_entries', 'cve_last_update'), 'CVE'),
    'kubernetes': (FetchK8sRequestSerializer, ('k8s_entries', 'k8s_last_update'), 'K8s haber'),
    'sre': (FetchSRERequestSerializer, ('sre_entries', 'sre_last_update'), 'SRE haber'),
    'devtools': (FetchDevToolsRequestSerializer, ('devtools_entries', 'devtools_last_update'), 'DevTools'),
    'ai': (FetchAINewsRequestSerializer, ('ai_entries', 'ai_last_update'), 'AI haber'),
}


def _tetikle(request, bolum):
    """Eski fetch uclarinin ortak govdesi: dogrula, v1 kapisindan gecir, yanitla.

    Kilit ve 15 dk soguma v1 (/api/v1/<bolum>/refresh/) ile paylasilir; kaynak
    sitelere giden yuk tetikleyenden bagimsiz sinirlanir (ADR-0003 karar 5).
    """
    serializer_sinifi, cache_anahtarlari, ad = _FETCH_BOLUMLERI[bolum]
    serializer = serializer_sinifi(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'message': 'Gecersiz istek'},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        sonuc = refresh.trigger(
            bolum,
            task_kwargs={'days': serializer.validated_data['days'],
                         'selected_sources': serializer.validated_data.get('sources')},
            # FetchRun.TETIKLEYICILER'de 'admin' "Arayuz" olarak gosterilir
            trigger_label='admin',
        )
    except Exception:
        logger.exception('%s cekimi tetiklenemedi', bolum)
        return Response({'success': False, 'message': GENEL_SUNUCU_HATASI, 'count': 0, 'data': []},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if sonuc.status == 'cooldown':
        dakika = -(-sonuc.retry_after // 60)  # yukari yuvarla
        yanit = Response({
            'success': False,
            'message': f'{ad} cekimi az once yapildi; {dakika} dk sonra tekrar deneyin.',
            'retry_after': sonuc.retry_after,
            'count': 0,
            'data': [],
        }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        yanit['Retry-After'] = str(sonuc.retry_after)
        return yanit

    if sonuc.status == 'started':
        # Yalniz yeni is basladiysa: calisan is ya da soguma varken silmek listeyi bosaltirdi
        cache.delete_many(cache_anahtarlari)
        mesaj = f'{ad} cekimi baslatildi. Otomatik yansiyacak.'
    else:
        mesaj = f'{ad} cekimi zaten suruyor. Kayitlar otomatik yansiyacak.'
    return Response({'success': True, 'message': mesaj, 'job_id': sonuc.job_id,
                     'count': 0, 'data': []})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_news(request):
    """Haberleri getir (cache veya database'den)"""
    # Once cache'den dene
    cached_news = cache.get('cybersecurity_news')
    if cached_news:
        return Response({
            'success': True,
            'data': cached_news,
            'cached': True,
            'count': len(cached_news)
        })
    
    # Cache yoksa database'den cek
    articles = NewsArticle.objects.all().order_by('-date')[:100]
    serializer = NewsArticleSerializer(articles, many=True)
    data = serializer.data
    
    # Cache'e kaydet
    if data:
        cache.set('cybersecurity_news', data, 3600)
    
    return Response({
        'success': True,
        'data': data,
        'cached': False,
        'count': len(data)
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_news(request):
    """Siber guvenlik haberi cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'news')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_cache(request):
    """Cache ve database'i temizle"""
    try:
        # Cache temizle
        cache.delete('cybersecurity_news')
        cache.delete('last_update')
        
        # Database temizle
        NewsArticle.objects.all().delete()
        
        return Response({
            'success': True,
            'message': 'Cache ve veritabani temizlendi'
        })
    except Exception:
        logger.exception('clear_cache basarisiz')
        return Response({
            'success': False,
            'message': GENEL_SUNUCU_HATASI
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_stats(request):
    """Istatistikleri getir"""
    total = NewsArticle.objects.count()
    
    # Kaynaklara gore dagilim
    from django.db.models import Count
    source_stats = NewsArticle.objects.values('source').annotate(
        count=Count('source')
    ).order_by('-count')
    
    by_source = {item['source']: item['count'] for item in source_stats}
    
    # Son guncelleme
    last_article = NewsArticle.objects.order_by('-created_at').first()
    last_update = last_article.created_at.isoformat() if last_article else None
    
    return Response({
        'success': True,
        'total': total,
        'by_source': by_source,
        'last_update': last_update,
        'cached': cache.get('cybersecurity_news') is not None
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def export_news(request):
    """Haberleri JSON olarak disari aktar"""
    articles = NewsArticle.objects.all().order_by('-date')
    serializer = NewsArticleSerializer(articles, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data,
        'exported_at': datetime.now().isoformat(),
        'count': len(serializer.data)
    })


# ==================== CVE ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_cves(request):
    """CVE'leri getir (cache veya database'den)"""
    # Once cache'den dene
    cached_cves = cache.get('cve_entries')
    if cached_cves:
        return Response({
            'success': True,
            'data': cached_cves,
            'cached': True,
            'count': len(cached_cves)
        })
    
    # Cache yoksa database'den cek
    cves = CVEEntry.objects.all().order_by('-published_date')[:100]
    serializer = CVEEntrySerializer(cves, many=True)
    data = serializer.data
    
    # Cache'e kaydet
    if data:
        cache.set('cve_entries', data, 3600)
    
    return Response({
        'success': True,
        'data': data,
        'cached': False,
        'count': len(data)
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_cves(request):
    """CVE cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'cve')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_cve_cache(request):
    """CVE cache ve database'i temizle"""
    try:
        # Cache temizle
        cache.delete('cve_entries')
        cache.delete('cve_last_update')
        
        # Database temizle
        CVEEntry.objects.all().delete()
        
        return Response({
            'success': True,
            'message': 'CVE cache ve veritabani temizlendi'
        })
    except Exception:
        logger.exception('clear_cve_cache basarisiz')
        return Response({
            'success': False,
            'message': GENEL_SUNUCU_HATASI
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_cve_stats(request):
    """CVE istatistiklerini getir"""
    total = CVEEntry.objects.count()
    
    # Kaynaklara gore dagilim
    from django.db.models import Count
    source_stats = CVEEntry.objects.values('source').annotate(
        count=Count('source')
    ).order_by('-count')
    
    by_source = {item['source']: item['count'] for item in source_stats}
    
    # Siddet seviyesine gore dagilim
    severity_stats = CVEEntry.objects.values('severity').annotate(
        count=Count('severity')
    ).order_by('-count')
    
    by_severity = {item['severity']: item['count'] for item in severity_stats}
    
    # Son guncelleme
    last_cve = CVEEntry.objects.order_by('-created_at').first()
    last_update = last_cve.created_at.isoformat() if last_cve else None
    
    return Response({
        'success': True,
        'total': total,
        'by_source': by_source,
        'by_severity': by_severity,
        'last_update': last_update,
        'cached': cache.get('cve_entries') is not None
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def export_cves(request):
    """CVE'leri JSON olarak disari aktar"""
    cves = CVEEntry.objects.all().order_by('-published_date')
    serializer = CVEEntrySerializer(cves, many=True)
    
    return Response({
        'success': True,
        'data': serializer.data,
        'exported_at': datetime.now().isoformat(),
        'count': len(serializer.data)
    })


# ==================== KUBERNETES ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_k8s(request):
    """Kubernetes haberlerini getir (cache veya database'den)"""
    cached_k8s = cache.get('k8s_entries')
    if cached_k8s:
        return Response({
            'success': True,
            'data': cached_k8s,
            'cached': True,
            'count': len(cached_k8s)
        })

    entries = KubernetesEntry.objects.all().order_by('-published_date')[:100]
    serializer = KubernetesEntrySerializer(entries, many=True)
    data = serializer.data

    if data:
        cache.set('k8s_entries', data, 3600)

    return Response({
        'success': True,
        'data': data,
        'cached': False,
        'count': len(data)
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_k8s(request):
    """Kubernetes haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'kubernetes')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_k8s_cache(request):
    """Kubernetes cache ve database'i temizle"""
    try:
        cache.delete('k8s_entries')
        cache.delete('k8s_last_update')

        KubernetesEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'Kubernetes cache ve veritabani temizlendi'
        })
    except Exception:
        logger.exception('clear_k8s_cache basarisiz')
        return Response({
            'success': False,
            'message': GENEL_SUNUCU_HATASI
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_k8s_stats(request):
    """Kubernetes istatistiklerini getir"""
    total = KubernetesEntry.objects.count()

    from django.db.models import Count
    source_stats = KubernetesEntry.objects.values('source').annotate(
        count=Count('source')
    ).order_by('-count')

    by_source = {item['source']: item['count'] for item in source_stats}

    category_stats = KubernetesEntry.objects.values('category').annotate(
        count=Count('category')
    ).order_by('-count')

    by_category = {item['category']: item['count'] for item in category_stats}

    last_entry = KubernetesEntry.objects.order_by('-created_at').first()
    last_update = last_entry.created_at.isoformat() if last_entry else None

    return Response({
        'success': True,
        'total': total,
        'by_source': by_source,
        'by_category': by_category,
        'last_update': last_update,
        'cached': cache.get('k8s_entries') is not None
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def export_k8s(request):
    """Kubernetes haberlerini JSON olarak disari aktar"""
    entries = KubernetesEntry.objects.all().order_by('-published_date')
    serializer = KubernetesEntrySerializer(entries, many=True)

    return Response({
        'success': True,
        'data': serializer.data,
        'exported_at': datetime.now().isoformat(),
        'count': len(serializer.data)
    })


# ==================== SRE ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_sre(request):
    """SRE haberlerini getir (cache veya database'den)"""
    cached_sre = cache.get('sre_entries')
    if cached_sre:
        return Response({
            'success': True,
            'data': cached_sre,
            'cached': True,
            'count': len(cached_sre)
        })

    entries = SREEntry.objects.all().order_by('-published_date')[:100]
    serializer = SREEntrySerializer(entries, many=True)
    data = serializer.data

    if data:
        cache.set('sre_entries', data, 3600)

    return Response({
        'success': True,
        'data': data,
        'cached': False,
        'count': len(data)
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_sre(request):
    """SRE haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'sre')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_sre_cache(request):
    """SRE cache ve database'i temizle"""
    try:
        cache.delete('sre_entries')
        cache.delete('sre_last_update')

        SREEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'SRE cache ve veritabani temizlendi'
        })
    except Exception:
        logger.exception('clear_sre_cache basarisiz')
        return Response({
            'success': False,
            'message': GENEL_SUNUCU_HATASI
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_sre_stats(request):
    """SRE istatistiklerini getir"""
    total = SREEntry.objects.count()

    from django.db.models import Count
    source_stats = SREEntry.objects.values('source').annotate(
        count=Count('source')
    ).order_by('-count')

    by_source = {item['source']: item['count'] for item in source_stats}

    last_entry = SREEntry.objects.order_by('-created_at').first()
    last_update = last_entry.created_at.isoformat() if last_entry else None

    return Response({
        'success': True,
        'total': total,
        'by_source': by_source,
        'last_update': last_update,
        'cached': cache.get('sre_entries') is not None
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def export_sre(request):
    """SRE haberlerini JSON olarak disari aktar"""
    entries = SREEntry.objects.all().order_by('-published_date')
    serializer = SREEntrySerializer(entries, many=True)

    return Response({
        'success': True,
        'data': serializer.data,
        'exported_at': datetime.now().isoformat(),
        'count': len(serializer.data)
    })


# ==================== DEVTOOLS ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_devtools(request):
    """DevTools guncellemelerini getir (cache veya database'den)"""
    cached_devtools = cache.get('devtools_entries')
    if cached_devtools:
        return Response({
            'success': True,
            'data': cached_devtools,
            'cached': True,
            'count': len(cached_devtools)
        })

    entries = DevToolsEntry.objects.all().order_by('-published_date')[:100]
    serializer = DevToolsEntrySerializer(entries, many=True)
    data = serializer.data

    if data:
        cache.set('devtools_entries', data, 3600)

    return Response({
        'success': True,
        'data': data,
        'cached': False,
        'count': len(data)
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_devtools(request):
    """DevTools cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'devtools')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_devtools_cache(request):
    """DevTools cache ve database'i temizle"""
    try:
        cache.delete('devtools_entries')
        cache.delete('devtools_last_update')

        DevToolsEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'DevTools cache ve veritabani temizlendi'
        })
    except Exception:
        logger.exception('clear_devtools_cache basarisiz')
        return Response({
            'success': False,
            'message': GENEL_SUNUCU_HATASI
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_devtools_stats(request):
    """DevTools istatistiklerini getir"""
    total = DevToolsEntry.objects.count()

    from django.db.models import Count
    source_stats = DevToolsEntry.objects.values('source').annotate(
        count=Count('source')
    ).order_by('-count')

    by_source = {item['source']: item['count'] for item in source_stats}

    type_stats = DevToolsEntry.objects.values('entry_type').annotate(
        count=Count('entry_type')
    ).order_by('-count')

    by_type = {item['entry_type']: item['count'] for item in type_stats}

    last_entry = DevToolsEntry.objects.order_by('-created_at').first()
    last_update = last_entry.created_at.isoformat() if last_entry else None

    return Response({
        'success': True,
        'total': total,
        'by_source': by_source,
        'by_type': by_type,
        'last_update': last_update,
        'cached': cache.get('devtools_entries') is not None
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def export_devtools(request):
    """DevTools guncellemelerini JSON olarak disari aktar"""
    entries = DevToolsEntry.objects.all().order_by('-published_date')
    serializer = DevToolsEntrySerializer(entries, many=True)

    return Response({
        'success': True,
        'data': serializer.data,
        'exported_at': datetime.now().isoformat(),
        'count': len(serializer.data)
    })

# ==================== AI NEWS ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_ai_news(request):
    """AI Haberlerini getir (cache veya database'den)"""
    cached_ai = cache.get('ai_entries')
    if cached_ai:
        return Response({
            'success': True,
            'data': cached_ai,
            'cached': True,
            'count': len(cached_ai)
        })

    entries = AINewsEntry.objects.all().order_by('-published_date')[:100]
    serializer = AINewsEntrySerializer(entries, many=True)
    data = serializer.data

    if data:
        cache.set('ai_entries', data, 3600)

    return Response({
        'success': True,
        'data': data,
        'cached': False,
        'count': len(data)
    })

@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_ai_news(request):
    """AI haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'ai')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_ai_cache(request):
    """AI cache ve database'i temizle"""
    try:
        cache.delete('ai_entries')
        cache.delete('ai_last_update')

        AINewsEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'AI cache ve veritabani temizlendi'
        })
    except Exception:
        logger.exception('clear_ai_cache basarisiz')
        return Response({
            'success': False,
            'message': GENEL_SUNUCU_HATASI
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([AllowAny])
def get_ai_stats(request):
    """AI istatistiklerini getir"""
    total = AINewsEntry.objects.count()

    from django.db.models import Count
    source_stats = AINewsEntry.objects.values('source').annotate(
        count=Count('source')
    ).order_by('-count')

    by_source = {item['source']: item['count'] for item in source_stats}

    last_entry = AINewsEntry.objects.order_by('-created_at').first()
    last_update = last_entry.created_at.isoformat() if last_entry else None

    return Response({
        'success': True,
        'total': total,
        'by_source': by_source,
        'last_update': last_update,
        'cached': cache.get('ai_entries') is not None
    })

@api_view(['GET'])
@permission_classes([AllowAny])
def export_ai_news(request):
    """AI Haberlerini JSON olarak disari aktar"""
    entries = AINewsEntry.objects.all().order_by('-published_date')
    serializer = AINewsEntrySerializer(entries, many=True)

    return Response({
        'success': True,
        'data': serializer.data,
        'exported_at': datetime.now().isoformat(),
        'count': len(serializer.data)
    })
