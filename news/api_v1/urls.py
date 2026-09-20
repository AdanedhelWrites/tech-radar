"""v1 yol tanimlari."""
from django.urls import path
from drf_spectacular.views import SpectacularAPIView
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from . import views

# Sema ve docs uclari da kimlik dogrulamasi ister (v1'de yalniz /health/ aciktir).
# TokenAuthentication listede ILK olmalidir: DRF WWW-Authenticate basligini ilk
# authenticator'dan turetir, dolayisiyla kimliksiz istek 403 degil 401 alir.
# SessionAuthentication tarayici icindir -- tarayici Authorization basligi
# gondermez, o olmadan /docs/ arayuzu hicbir zaman acilamazdi.
SemaGorunumu = SpectacularAPIView.as_view(
    authentication_classes=[TokenAuthentication, SessionAuthentication],
    permission_classes=[IsAuthenticated],
)

urlpatterns = [
    path('schema/', SemaGorunumu, name='v1-schema'),
    path('health/', views.HealthView.as_view(), name='v1-health'),
    path('status/', views.StatusView.as_view(), name='v1-status'),
    path('refresh/', views.RefreshAllView.as_view(), name='v1-refresh-all'),
    path('news/', views.NewsDeltaView.as_view(), name='v1-news'),
    path('cve/', views.CVEDeltaView.as_view(), name='v1-cve'),
    path('kubernetes/', views.KubernetesDeltaView.as_view(), name='v1-kubernetes'),
    path('sre/', views.SREDeltaView.as_view(), name='v1-sre'),
    path('devtools/', views.DevToolsDeltaView.as_view(), name='v1-devtools'),
    path('ai/', views.AIDeltaView.as_view(), name='v1-ai'),
    path('<str:section>/refresh/', views.RefreshView.as_view(), name='v1-refresh'),
    path('jobs/<str:job_id>/', views.JobView.as_view(), name='v1-job'),
]
