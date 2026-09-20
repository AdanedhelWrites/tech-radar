"""v1 yol tanimlari."""
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from . import views
from .schema import (
    DELTA_SEMALARI, HEALTH_SEMASI, JOB_SEMASI, REFRESH_ALL_SEMASI,
    REFRESH_SEMASI, STATUS_SEMASI,
)

# Sema ve docs uclari da kimlik dogrulamasi ister (v1'de yalniz /health/ aciktir).
# TokenAuthentication listede ILK olmalidir: DRF WWW-Authenticate basligini ilk
# authenticator'dan turetir, dolayisiyla kimliksiz istek 403 degil 401 alir.
# SessionAuthentication tarayici icindir -- tarayici Authorization basligi
# gondermez, o olmadan /docs/ arayuzu hicbir zaman acilamazdi.
SemaGorunumu = SpectacularAPIView.as_view(
    authentication_classes=[TokenAuthentication, SessionAuthentication],
    permission_classes=[IsAuthenticated],
)

DocsGorunumu = SpectacularSwaggerView.as_view(
    url_name='v1-schema',
    authentication_classes=[TokenAuthentication, SessionAuthentication],
    permission_classes=[IsAuthenticated],
)

urlpatterns = [
    path('schema/', SemaGorunumu, name='v1-schema'),
    path('docs/', DocsGorunumu, name='v1-docs'),
    path('health/', HEALTH_SEMASI(views.HealthView).as_view(), name='v1-health'),
    path('status/', STATUS_SEMASI(views.StatusView).as_view(), name='v1-status'),
    path('refresh/', REFRESH_ALL_SEMASI(views.RefreshAllView).as_view(),
         name='v1-refresh-all'),
    path('news/', DELTA_SEMALARI['news'](views.NewsDeltaView).as_view(), name='v1-news'),
    path('cve/', DELTA_SEMALARI['cve'](views.CVEDeltaView).as_view(), name='v1-cve'),
    path('kubernetes/', DELTA_SEMALARI['kubernetes'](views.KubernetesDeltaView).as_view(),
         name='v1-kubernetes'),
    path('sre/', DELTA_SEMALARI['sre'](views.SREDeltaView).as_view(), name='v1-sre'),
    path('devtools/', DELTA_SEMALARI['devtools'](views.DevToolsDeltaView).as_view(),
         name='v1-devtools'),
    path('ai/', DELTA_SEMALARI['ai'](views.AIDeltaView).as_view(), name='v1-ai'),
    path('<str:section>/refresh/', REFRESH_SEMASI(views.RefreshView).as_view(),
         name='v1-refresh'),
    path('jobs/<str:job_id>/', JOB_SEMASI(views.JobView).as_view(), name='v1-job'),
]
