from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.core.cache import cache
from datetime import datetime
from .models import (
    NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry
)
from .tasks import fetch_news_task, fetch_cve_task, fetch_k8s_task, fetch_sre_task, fetch_devtools_task, fetch_ai_news_task
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
    """Yeni Siber Guvenlik Haberlerini cek - ASYNC"""
    try:
        days = request.data.get('days', 7)
        selected_sources = request.data.get('sources', None)
        
        # Cache'i hemen temizle - task baslamadan once bosalt ki
        # polling yeni gelen haberleri direkt gorulsun
        cache.delete('cybersecurity_news')
        cache.delete('last_update')

        # Trigger Celery Task
        fetch_news_task.delay(days=days, selected_sources=selected_sources, clear_existing=False)

        return Response({
            'success': True,
            'message': 'Haber cekimi baslatildi. Haberler ekrana otomatik yansiyacak.',
            'count': 0,
            'data': []
        })
            
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e),
            'count': 0,
            'data': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
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
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
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
    """Yeni CVE'leri cek - ASYNC"""
    try:
        days = request.data.get('days', 7)
        selected_sources = request.data.get('sources', None)

        cache.delete('cve_entries')
        cache.delete('cve_last_update')

        fetch_cve_task.delay(days=days, selected_sources=selected_sources)

        return Response({
            'success': True,
            'message': 'CVE cekimi baslatildi. Otomatik yansiyacak.',
            'count': 0,
            'data': []
        })
            
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e),
            'count': 0,
            'data': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
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
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
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
    """Yeni K8s Haberlerini cek - ASYNC"""
    serializer = FetchK8sRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'message': 'Gecersiz istek'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        days = serializer.validated_data.get('days', 30)
        selected_sources = serializer.validated_data.get('sources', None)

        cache.delete('k8s_entries')
        cache.delete('k8s_last_update')

        fetch_k8s_task.delay(days=days, selected_sources=selected_sources)

        return Response({
            'success': True,
            'message': 'K8s haber cekimi baslatildi. Otomatik yansiyacak.',
            'count': 0,
            'data': []
        })

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e),
            'count': 0,
            'data': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
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
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
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
    """Yeni SRE Haberlerini cek - ASYNC"""
    serializer = FetchSRERequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'message': 'Gecersiz istek'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        days = serializer.validated_data.get('days', 30)
        selected_sources = serializer.validated_data.get('sources', None)

        cache.delete('sre_entries')
        cache.delete('sre_last_update')

        fetch_sre_task.delay(days=days, selected_sources=selected_sources)

        return Response({
            'success': True,
            'message': 'SRE haber cekimi baslatildi. Otomatik yansiyacak.',
            'count': 0,
            'data': []
        })

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e),
            'count': 0,
            'data': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
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
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
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
    """Yeni DevTools Haberlerini cek - ASYNC"""
    serializer = FetchDevToolsRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'message': 'Gecersiz istek'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        days = serializer.validated_data.get('days', 30)
        selected_sources = serializer.validated_data.get('sources', None)

        cache.delete('devtools_entries')
        cache.delete('devtools_last_update')

        fetch_devtools_task.delay(days=days, selected_sources=selected_sources)

        return Response({
            'success': True,
            'message': 'DevTools cekimi baslatildi. Otomatik yansiyacak.',
            'count': 0,
            'data': []
        })

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e),
            'count': 0,
            'data': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([AllowAny])
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
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
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
    """Yeni AI Haberlerini cek - ASYNC"""
    serializer = FetchAINewsRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({'success': False, 'message': 'Gecersiz istek'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        days = serializer.validated_data.get('days', 30)
        selected_sources = serializer.validated_data.get('sources', None)

        cache.delete('ai_entries')
        cache.delete('ai_last_update')

        fetch_ai_news_task.delay(days=days, selected_sources=selected_sources)

        return Response({
            'success': True,
            'message': 'AI haber cekimi baslatildi. Otomatik yansiyacak.',
            'count': 0,
            'data': []
        })

    except Exception as e:
        return Response({
            'success': False,
            'message': str(e),
            'count': 0,
            'data': []
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
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
    except Exception as e:
        return Response({
            'success': False,
            'message': str(e)
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
