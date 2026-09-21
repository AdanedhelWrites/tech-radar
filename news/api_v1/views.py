"""v1 entegrasyon uc noktalari.

Mevcut /api/* uc noktalari frontend'e hizmet eder ve degistirilmez. Buradaki
uc noktalar dis tuketici uygulamalar icindir: token ister, cache'e bakmaz,
her zaman (updated_at, id) sirasinda doner.

Bu view'larin OpenAPI semasi burada degil news/api_v1/schema.py'de tanimlidir
ve urls.py'de extend_schema_view ile uygulanir (A5b).
"""
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

from .cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
from .filters import (
    min_severity_tr_listesi, ortak_filtreler, parse_csv, severity_tr_listesi,
)
from .serializers import (
    AINewsEntryV1Serializer, CVEEntryV1Serializer, DevToolsEntryV1Serializer,
    KubernetesEntryV1Serializer, NewsArticleV1Serializer, SREEntryV1Serializer,
)
from . import refresh
from celery.result import AsyncResult

from cybernews.celery import app as celery_app


def _hata(kod: str, mesaj: str, http_durum: int):
    """Tek bicim hata yaniti uretir."""
    return Response({'error': {'code': kod, 'message': mesaj}}, status=http_durum)


# DRF istisnalarini sozlesmedeki hata kodlarina esler.
DRF_DURUM_KODLARI = {
    400: 'invalid_parameter',
    401: 'unauthorized',
    403: 'forbidden',
    404: 'not_found',
    405: 'method_not_allowed',
    429: 'throttled',
}


class V1APIView(APIView):
    """v1 uc noktalarinin ortak tabani: token dogrulamasi, hiz siniri, hata bicimi."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'v1_read'

    def handle_exception(self, exc):
        """DRF'in kendi hata bicimini sozlesmedeki tek bicime cevirir.

        Bu yalnizca v1 view'larini etkiler; mevcut /api/* uc noktalari kendi
        bicimlerini korur.
        """
        try:
            yanit = super().handle_exception(exc)
        except Exception:
            return _hata('internal', 'Beklenmeyen bir sunucu hatasi olustu.',
                         status.HTTP_500_INTERNAL_SERVER_ERROR)
        kod = DRF_DURUM_KODLARI.get(yanit.status_code, 'internal')

        ayrinti = yanit.data
        if isinstance(ayrinti, dict):
            mesaj = str(ayrinti.get('detail', ayrinti))
        elif isinstance(ayrinti, list):
            mesaj = '; '.join(str(oge) for oge in ayrinti)
        else:
            mesaj = str(ayrinti)

        yanit.data = {'error': {'code': kod, 'message': mesaj}}
        return yanit


class HealthView(APIView):
    """Servisin ayakta olup olmadigini soyler.

    Kimlik dogrulama ve throttle bilincli olarak yok: Kubernetes liveness ve
    readiness probe'lari token tasiyamaz ve hiz sinirina takilmamalidir.
    """

    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = []

    def get(self, request):
        return Response({'status': 'ok', 'version': 'v1'})


class DeltaListAPIView(V1APIView):
    """Imlec tabanli delta okuma uc noktalarinin ortak tabani.

    Siralama her zaman (updated_at, id) artan; bu, imlecin dogrulugu icin
    zorunludur. Bu, akis sirasidir — ekrana basma sirasi degildir.

    Bu uc noktalar Redis cache'e bakmaz: cache dolu iken parametreleri yok
    saymak filtreleri bozardi.
    """

    model = None
    serializer_class = None
    default_limit = 100
    max_limit = 500

    def get_queryset(self):
        return self.model.objects.all()

    def apply_filters(self, queryset, params):
        """Alti bolumde ortak filtreler. Alt siniflar super() cagirip genisletir."""
        return ortak_filtreler(queryset, params)

    def _limit_coz(self, ham):
        if ham is None:
            return self.default_limit
        try:
            deger = int(ham)
        except (TypeError, ValueError):
            raise ValueError('limit bir tam sayi olmali.')
        if deger < 1:
            raise ValueError('limit en az 1 olmali.')
        return min(deger, self.max_limit)

    def get(self, request):
        params = request.query_params

        try:
            limit = self._limit_coz(params.get('limit'))
        except ValueError as hata:
            return _hata('invalid_parameter', str(hata), status.HTTP_400_BAD_REQUEST)

        sorgu = self.get_queryset().order_by('updated_at', 'id')

        imlec = params.get('since_cursor')
        if imlec:
            try:
                moment, pk = decode_cursor(imlec)
            except InvalidCursor as hata:
                return _hata('invalid_cursor', str(hata), status.HTTP_400_BAD_REQUEST)
            sorgu = apply_cursor(sorgu, moment, pk)
        elif params.get('since'):
            try:
                gun = parse_date(params['since'])
            except ValueError:
                gun = None
            if gun is None:
                return _hata('invalid_parameter',
                             'since YYYY-MM-DD biciminde olmali.',
                             status.HTTP_400_BAD_REQUEST)
            sorgu = sorgu.filter(updated_at__date__gte=gun)

        try:
            sorgu = self.apply_filters(sorgu, params)
        except ValueError as hata:
            return _hata('invalid_parameter', str(hata), status.HTTP_400_BAD_REQUEST)

        # limit + 1 cekilir: fazladan gelen satir "daha var mi" sorusunu yanitlar
        satirlar = list(sorgu[:limit + 1])
        has_more = len(satirlar) > limit
        satirlar = satirlar[:limit]

        if satirlar:
            son = satirlar[-1]
            next_cursor = encode_cursor(son.updated_at, son.id)
        else:
            # Sonuc bos: gelen imlec aynen geri verilir ki tuketicinin
            # saklayacak bir degeri hep olsun. Imlec hic verilmemisse None doner.
            next_cursor = imlec or None

        return Response({
            'results': self.serializer_class(satirlar, many=True).data,
            'next_cursor': next_cursor,
            'has_more': has_more,
            'count': len(satirlar),
        })


class NewsDeltaView(DeltaListAPIView):
    model = NewsArticle
    serializer_class = NewsArticleV1Serializer


class CVEDeltaView(DeltaListAPIView):
    model = CVEEntry
    serializer_class = CVEEntryV1Serializer

    def apply_filters(self, queryset, params):
        queryset = super().apply_filters(queryset, params)
        if params.get('min_severity'):
            queryset = queryset.filter(severity__in=min_severity_tr_listesi(params['min_severity']))
        if params.get('severity'):
            queryset = queryset.filter(severity__in=severity_tr_listesi(params['severity']))
        return queryset


class KubernetesDeltaView(DeltaListAPIView):
    model = KubernetesEntry
    serializer_class = KubernetesEntryV1Serializer

    def apply_filters(self, queryset, params):
        queryset = super().apply_filters(queryset, params)
        kategoriler = parse_csv(params.get('category'))
        if kategoriler:
            queryset = queryset.filter(category__in=kategoriler)
        return queryset


class SREDeltaView(DeltaListAPIView):
    model = SREEntry
    serializer_class = SREEntryV1Serializer


class DevToolsDeltaView(DeltaListAPIView):
    model = DevToolsEntry
    serializer_class = DevToolsEntryV1Serializer

    def apply_filters(self, queryset, params):
        queryset = super().apply_filters(queryset, params)
        turler = parse_csv(params.get('entry_type'))
        if turler:
            queryset = queryset.filter(entry_type__in=turler)
        return queryset


class AIDeltaView(DeltaListAPIView):
    model = AINewsEntry
    serializer_class = AINewsEntryV1Serializer


def _is_govdesi(sonuc):
    """Baslatilan veya zaten calisan bir is icin tuketiciye donen govde."""
    return {
        'job_id': sonuc.job_id,
        'section': sonuc.section,
        'status': sonuc.status,
        'status_url': f'/api/v1/jobs/{sonuc.job_id}/' if sonuc.job_id else None,
    }


class RefreshView(V1APIView):
    """Tek bir bolum icin manuel cekim tetikler (spec bolum 8).

    Uc katman korur: bolum kilidi (cift kazima olmaz), 15 dk bolum sogumasi
    (kaynak sitelere yuk binmez) ve token basina v1_refresh hiz siniri.
    """

    throttle_scope = 'v1_refresh'

    def post(self, request, section):
        if section not in refresh.SECTIONS:
            return _hata('not_found', f"Bilinmeyen bolum: '{section}'.",
                         status.HTTP_404_NOT_FOUND)

        sonuc = refresh.trigger(section)
        if sonuc.status == 'cooldown':
            yanit = _hata('cooldown',
                          f"'{section}' bolumu yakin zamanda yenilendi; "
                          f"{sonuc.retry_after} sn sonra tekrar deneyin.",
                          status.HTTP_429_TOO_MANY_REQUESTS)
            yanit['Retry-After'] = str(sonuc.retry_after)
            return yanit

        return Response(_is_govdesi(sonuc), status=status.HTTP_202_ACCEPTED)


class RefreshAllView(V1APIView):
    """Alti bolumu birden tetikler. Her bolum kendi kilidine ve sogumasina tabidir.

    Her zaman 202 doner; tuketici hangi bolumlerin baslatildigini, zaten
    calistigini veya sogumada oldugu icin atlandigini listelerden okur.
    """

    throttle_scope = 'v1_refresh'

    def post(self, request):
        gate = refresh.get_gate()
        govde = {'started': [], 'already_running': [], 'skipped': []}
        for section in refresh.SECTIONS:
            sonuc = refresh.trigger(section, gate=gate)
            if sonuc.status == 'cooldown':
                govde['skipped'].append({'section': section, 'retry_after': sonuc.retry_after})
            else:
                govde[sonuc.status].append(_is_govdesi(sonuc))
        return Response(govde, status=status.HTTP_202_ACCEPTED)


# Celery durumlari -> sozlesmedeki durumlar
CELERY_DURUMLARI = {
    'PENDING': 'pending',
    'RECEIVED': 'pending',
    'STARTED': 'started',
    'RETRY': 'started',
    'SUCCESS': 'success',
    'FAILURE': 'failure',
    'REVOKED': 'failure',
}


class JobView(V1APIView):
    """Manuel tetiklenen bir isin durumunu dondurur.

    Celery bilinmeyen bir id icin de PENDING dondurdugu icin once job kaydina
    bakilir; kaydi olmayan (hic verilmemis veya 1 gunden eski) kimlik 404'tur.
    """

    def get(self, request, job_id):
        section = refresh.get_gate().job_section(job_id)
        if section is None:
            return _hata('not_found', 'Bilinmeyen veya suresi dolmus is kimligi.',
                         status.HTTP_404_NOT_FOUND)

        sonuc = AsyncResult(job_id, app=celery_app)
        govde = {'job_id': job_id, 'section': section,
                 'status': CELERY_DURUMLARI.get(sonuc.state, 'pending')}

        if govde['status'] == 'success':
            deger = sonuc.result if isinstance(sonuc.result, dict) else {}
            if deger.get('success') is False and deger.get('error'):
                # Task istisnayi yakalayip dondurdu: Celery icin basarili, tuketici icin degil
                govde['status'] = 'failure'
                govde['error'] = str(deger['error'])
            else:
                govde['count'] = deger.get('count', 0)
        elif govde['status'] == 'failure':
            govde['error'] = str(sonuc.result)

        return Response(govde)


class StatusView(V1APIView):
    """Veri tazeligi raporu (spec 2026-09-20-a4, bolum 3.5).

    Bilincli olarak DARDIR: yalnizca tuketicinin "veri bayat mi" sorusunu
    yanitlar. Operator verisi (Gemini butcesi, by_provider, stopped_reason,
    trigger, error) buraya girmez; o FetchRun'da ve admin'dedir.
    """

    def get(self, request):
        from django.utils import timezone

        from news.fetch_runs import BOLUM_MODELLERI
        from news.models import FetchRun

        bolumler = {}
        for ad, model in BOLUM_MODELLERI.items():
            son = FetchRun.objects.filter(section=ad).first()
            son_basarili = FetchRun.objects.filter(section=ad, status='success').first()
            bolumler[ad] = {
                'last_success_at': son_basarili.finished_at if son_basarili else None,
                'last_status': son.status if son else None,
                'last_fetched_count': son.fetched_count if son else None,
                'last_saved_count': son.saved_count if son else None,
                'pending_translation': model.objects.filter(needs_translation=True).count(),
                'total': model.objects.count(),
            }
        return Response({'generated_at': timezone.now(), 'sections': bolumler})
