"""v1 yol tanimlari."""
from django.urls import path

from . import views

urlpatterns = [
    path('health/', views.HealthView.as_view(), name='v1-health'),
    path('news/', views.NewsDeltaView.as_view(), name='v1-news'),
    path('cve/', views.CVEDeltaView.as_view(), name='v1-cve'),
    path('kubernetes/', views.KubernetesDeltaView.as_view(), name='v1-kubernetes'),
    path('sre/', views.SREDeltaView.as_view(), name='v1-sre'),
    path('devtools/', views.DevToolsDeltaView.as_view(), name='v1-devtools'),
    path('ai/', views.AIDeltaView.as_view(), name='v1-ai'),
]
