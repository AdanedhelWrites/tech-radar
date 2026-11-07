import logging

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.response import Response
from django.core.cache import cache
from .models import (
    NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry
)
from .api_v1 import refresh
from .liste_sorgusu import liste_yaniti
from .serializers import (
    NewsArticleSerializer, FetchNewsRequestSerializer,
    FetchCVERequestSerializer,
    KubernetesEntrySerializer, FetchK8sRequestSerializer,
    SREEntrySerializer, FetchSRERequestSerializer,
    DevToolsEntrySerializer, FetchDevToolsRequestSerializer,
    AINewsEntrySerializer, FetchAINewsRequestSerializer
)

logger = logging.getLogger(__name__)

# Istemciye donen genel hata mesaji; gercek istisna sunucu loguna yazilir,
# yanit govdesine iceri yapisi/dosya yollari/sorgu metnini sizdirmaz.
GENEL_SUNUCU_HATASI = 'Islem sirasinda sunucuda beklenmeyen bir hata olustu.'


# Eski /api/*/fetch/ uclari: bolum -> (istek serializer'i, mesajdaki ad).
# Bolum adlari news/api_v1/refresh.py::SECTIONS ile ayni.
_FETCH_BOLUMLERI = {
    'news': (FetchNewsRequestSerializer, 'Haber'),
    'cve': (FetchCVERequestSerializer, 'CVE'),
    'kubernetes': (FetchK8sRequestSerializer, 'K8s haber'),
    'sre': (FetchSRERequestSerializer, 'SRE haber'),
    'devtools': (FetchDevToolsRequestSerializer, 'DevTools'),
    'ai': (FetchAINewsRequestSerializer, 'AI haber'),
}


def _tetikle(request, bolum):
    """Eski fetch uclarinin ortak govdesi: dogrula, v1 kapisindan gecir, yanitla.

    Kilit ve 15 dk soguma v1 (/api/v1/<bolum>/refresh/) ile paylasilir; kaynak
    sitelere giden yuk tetikleyenden bagimsiz sinirlanir (ADR-0003 karar 5).
    """
    serializer_sinifi, ad = _FETCH_BOLUMLERI[bolum]
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
        mesaj = f'{ad} cekimi baslatildi. Otomatik yansiyacak.'
    else:
        mesaj = f'{ad} cekimi zaten suruyor. Kayitlar otomatik yansiyacak.'
    return Response({'success': True, 'message': mesaj, 'job_id': sonuc.job_id,
                     'count': 0, 'data': []})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_news(request):
    """Haberleri suzulmus, siralanmis ve sayfalanmis getir (news/liste_sorgusu.py)"""
    return liste_yaniti(request, 'news')


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_news(request):
    """Siber guvenlik haberi cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'news')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_cache(request):
    """Veritabanini temizle"""
    try:
        NewsArticle.objects.all().delete()

        return Response({
            'success': True,
            'message': 'Veritabani temizlendi'
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
    })


# ==================== CVE ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_cves(request):
    """CVE'leri suzulmus, siralanmis ve sayfalanmis getir (news/liste_sorgusu.py)"""
    return liste_yaniti(request, 'cve')


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_cves(request):
    """CVE cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'cve')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_cve_cache(request):
    """CVE veritabanini temizle"""
    try:
        CVEEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'CVE veritabani temizlendi'
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
    })


# ==================== KUBERNETES ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_k8s(request):
    """Kubernetes haberlerini suzulmus, siralanmis ve sayfalanmis getir (news/liste_sorgusu.py)"""
    return liste_yaniti(request, 'kubernetes')


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_k8s(request):
    """Kubernetes haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'kubernetes')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_k8s_cache(request):
    """Kubernetes veritabanini temizle"""
    try:
        KubernetesEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'Kubernetes veritabani temizlendi'
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
    })


# ==================== SRE ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_sre(request):
    """SRE haberlerini suzulmus, siralanmis ve sayfalanmis getir (news/liste_sorgusu.py)"""
    return liste_yaniti(request, 'sre')


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_sre(request):
    """SRE haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'sre')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_sre_cache(request):
    """SRE veritabanini temizle"""
    try:
        SREEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'SRE veritabani temizlendi'
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
    })


# ==================== DEVTOOLS ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_devtools(request):
    """DevTools guncellemelerini suzulmus, siralanmis ve sayfalanmis getir (news/liste_sorgusu.py)"""
    return liste_yaniti(request, 'devtools')


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_devtools(request):
    """DevTools cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'devtools')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_devtools_cache(request):
    """DevTools veritabanini temizle"""
    try:
        DevToolsEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'DevTools veritabani temizlendi'
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
    })


# ==================== AI NEWS ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([AllowAny])
def get_ai_news(request):
    """AI haberlerini suzulmus, siralanmis ve sayfalanmis getir (news/liste_sorgusu.py)"""
    return liste_yaniti(request, 'ai')


@api_view(['POST'])
@permission_classes([AllowAny])
def fetch_ai_news(request):
    """AI haber cekimini tetikler (bolum kilidi + soguma, v1 ile ortak)."""
    return _tetikle(request, 'ai')


@api_view(['POST'])
@permission_classes([IsAdminUser])
def clear_ai_cache(request):
    """AI veritabanini temizle"""
    try:
        AINewsEntry.objects.all().delete()

        return Response({
            'success': True,
            'message': 'AI veritabani temizlendi'
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
    })


SAGLIK_CACHE_SURESI = 60


@api_view(['GET'])
@permission_classes([AllowAny])
def get_saglik(request):
    """Ana sayfa saglik seridi: bolum basina son basarili cekim ve sessiz kaynaklar (2026-10-14).

    Tokensizdir (arayuz anonim); bu yuzden v1 /status/'un dar alt kumesidir ve 60 sn cache'lenir
    (kaynak_durumlari bolum basina FetchRun + Max(created_at) sorgusu yapar).
    """
    from django.utils.timezone import now

    from . import gemini, kayit_cevirmenleri
    from .fetch_runs import bolum_ozetleri, ceviri_kuyrugu_ozeti

    govde = cache.get('saglik_ozeti')
    if govde is None:
        # Birincil Gemini hep; yedek (gemini2/openrouter/deepl, sayac oneki) yalniz ayarliysa: anahtar
        # (ve gerekiyorsa model) dolu. Ozetler anahtar degeri tasimaz (G7, PR-C).
        butce = {'gemini': gemini.butce_ozeti()}
        butce.update({cevirmen.onek: cevirmen.butce_ozeti()
                      for cevirmen in kayit_cevirmenleri.YEDEKLER if cevirmen.ayarli()})
        govde = {'generated_at': now().isoformat(), 'sections': bolum_ozetleri(),
                 'translation_queue': ceviri_kuyrugu_ozeti(),
                 'translation_budget': butce}
        cache.set('saglik_ozeti', govde, SAGLIK_CACHE_SURESI)
    return Response(govde)


GUNDEM_CACHE_SURESI = 120
GUNDEM_CACHE_ANAHTARI = 'gundem_ozeti'


def _gundem_ogeleri(simdi):
    """Bes bolumden son 72 saatin kayitlari (CVE yok); her model tek sorgu, yalniz gerekli alanlar."""
    from datetime import timedelta

    from .gundem import PENCERE_SAAT, Ogeler

    alt = simdi - timedelta(hours=PENCERE_SAAT)
    kaynaklar = (('news', NewsArticle, 'date'), ('kubernetes', KubernetesEntry, 'published_date'),
                 ('sre', SREEntry, 'published_date'), ('devtools', DevToolsEntry, 'published_date'),
                 ('ai', AINewsEntry, 'published_date'))
    ogeler = []
    for bolum, model, yayin_alani in kaynaklar:
        satirlar = model.objects.filter(created_at__gte=alt).values(
            'id', 'source', 'original_title', 'created_at', yayin_alani, 'translation_provider', 'turkish_title',
            'link')
        ogeler.extend(
            Ogeler(bolum=bolum, id=s['id'], source=s['source'], baslik=s['original_title'],
                   created_at=s['created_at'], yayin=s[yayin_alani], ceviri=s['translation_provider'],
                   tr_baslik=s['turkish_title'], link=s['link'] or '')
            for s in satirlar)
    return ogeler


def _gundem_hesapla():
    """Gundem yanit govdesi: secilen olaylar, temsilci kayitlar bolumun kendi serilestiricisiyle."""
    from django.utils.timezone import now

    from . import gundem

    simdi = now()
    secilenler = gundem.olaylari_sec(_gundem_ogeleri(simdi), simdi)
    serilestiriciler = {'news': (NewsArticle, NewsArticleSerializer),
                        'kubernetes': (KubernetesEntry, KubernetesEntrySerializer),
                        'sre': (SREEntry, SREEntrySerializer),
                        'devtools': (DevToolsEntry, DevToolsEntrySerializer),
                        'ai': (AINewsEntry, AINewsEntrySerializer)}
    idler = {}
    for olay in secilenler:
        idler.setdefault(olay['temsilci'].bolum, []).append(olay['temsilci'].id)
    kayitlar = {}
    for bolum, liste in idler.items():
        model, serilestirici = serilestiriciler[bolum]
        for kayit in model.objects.filter(id__in=liste):
            kayitlar[(bolum, kayit.id)] = serilestirici(kayit).data
    olaylar = [{
        'bolum': olay['temsilci'].bolum,
        'kayit': kayitlar[(olay['temsilci'].bolum, olay['temsilci'].id)],
        'kaynak_sayisi': olay['kaynak_sayisi'],
        'kaynaklar': olay['kaynaklar'],
        'diger_kaynaklar': olay['diger_kaynaklar'],
        'makale_sayisi': olay['makale_sayisi'],
        'bolumler': olay['bolumler'],
        'puan': round(olay['puan'], 2),
        'ilk': olay['ilk'].isoformat(),
        'son': olay['son'].isoformat(),
    } for olay in secilenler]
    return {'success': True, 'olaylar': olaylar, 'hesaplandi': simdi.isoformat()}


@api_view(['GET'])
@permission_classes([AllowAny])
def get_gundem(request):
    """Ana sayfa Gundem karti (2026-11-05): son 72 saatin cok kaynakli olaylari, en cok 6 oge.

    Tokensizdir (arayuz anonim), 120 sn cache'lenir. Hesap hatasi ana sayfayi bozmaz: 500 yerine
    200 + success False doner ve onbellege yazilmaz. LLM ve dis istek yok.
    """
    govde = cache.get(GUNDEM_CACHE_ANAHTARI)
    if govde is None:
        try:
            govde = _gundem_hesapla()
        except Exception:
            logger.exception('Gundem hesaplanamadi')
            return Response({'success': False, 'olaylar': []})
        cache.set(GUNDEM_CACHE_ANAHTARI, govde, GUNDEM_CACHE_SURESI)
    return Response(govde)


OZET_CACHE_SURESI = 60


@api_view(['GET'])
@permission_classes([AllowAny])
def get_ozet(request):
    """Ana sayfa Zafiyet Durumu ozeti (2026-10-31): pencereli CVE sayilari, oncelik listesi, grafik noktalari.

    Tokensizdir (arayuz anonim). `since` disindaki govde 60 sn cache'lenir; `new_since_count`
    her istekte ayri bir count() ile hesaplanir, cache govdesine yazilmaz. Gecersiz `since` yok sayilir.
    """
    from django.utils.dateparse import parse_datetime
    from django.utils.timezone import is_naive, make_aware
    from datetime import timezone as dt_timezone

    from .ozet import ozet_hesapla, yeni_kayit_sayisi

    govde = cache.get('ozet_govdesi')
    if govde is None:
        govde = ozet_hesapla()
        cache.set('ozet_govdesi', govde, OZET_CACHE_SURESI)

    since = None
    ham = request.query_params.get('since')
    if ham:
        try:
            since = parse_datetime(ham)
        except ValueError:
            since = None
    if since is None:
        return Response(govde)
    if is_naive(since):
        since = make_aware(since, dt_timezone.utc)
    return Response({**govde, 'new_since_count': yeni_kayit_sayisi(since)})
