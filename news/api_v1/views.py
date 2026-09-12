"""v1 entegrasyon uc noktalari.

Mevcut /api/* uc noktalari frontend'e hizmet eder ve degistirilmez. Buradaki
uc noktalar dis tuketici uygulamalar icindir: token ister, cache'e bakmaz,
her zaman (updated_at, id) sirasinda doner.
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
from .serializers import (
    AINewsEntryV1Serializer, CVEEntryV1Serializer, DevToolsEntryV1Serializer,
    KubernetesEntryV1Serializer, NewsArticleV1Serializer, SREEntryV1Serializer,
)


class V1APIView(APIView):
    """v1 uc noktalarinin ortak tabani: token dogrulamasi ve hiz siniri."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'v1_read'


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


def _hata(kod: str, mesaj: str, http_durum: int):
    """Tek bicim hata yaniti uretir."""
    return Response({'error': {'code': kod, 'message': mesaj}}, status=http_durum)


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
        """Bolume ozel filtreler. Task 7'de doldurulacak; simdilik degistirmez."""
        return queryset

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
            gun = parse_date(params['since'])
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


class KubernetesDeltaView(DeltaListAPIView):
    model = KubernetesEntry
    serializer_class = KubernetesEntryV1Serializer


class SREDeltaView(DeltaListAPIView):
    model = SREEntry
    serializer_class = SREEntryV1Serializer


class DevToolsDeltaView(DeltaListAPIView):
    model = DevToolsEntry
    serializer_class = DevToolsEntryV1Serializer


class AIDeltaView(DeltaListAPIView):
    model = AINewsEntry
    serializer_class = AINewsEntryV1Serializer
