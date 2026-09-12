"""v1 entegrasyon uc noktalari.

Mevcut /api/* uc noktalari frontend'e hizmet eder ve degistirilmez. Buradaki
uc noktalar dis tuketici uygulamalar icindir: token ister, cache'e bakmaz,
her zaman (updated_at, id) sirasinda doner.
"""
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView


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
