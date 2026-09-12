"""v1 yol tanimlari."""
from django.urls import path

from . import views

urlpatterns = [
    path('health/', views.HealthView.as_view(), name='v1-health'),
]
