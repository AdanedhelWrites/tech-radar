"""Frontend'in kullandigi /api/* liste cache'leri.

Alti fetch task'i ve retranslate gorevi liste cache'ini buradan kurar.
/api/v1/ uc noktalari bu cache'i hic kullanmaz (spec C2).

C5 — Bilincli sinir: liste cache'i yalnizca en yeni CACHE_LISTE_SINIRI kaydi
tutar; veritabaninda daha fazlasi olabilir (2026-09-12: 651 CVE). Frontend'de
gorunmeyen kayitlar kayip degildir; tum kayitlar /api/v1/ delta uc noktalarindan
alinir.
"""
from datetime import datetime

from django.core.cache import cache

from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)
from .serializers import (
    AINewsEntrySerializer, CVEEntrySerializer, DevToolsEntrySerializer,
    KubernetesEntrySerializer, NewsArticleSerializer, SREEntrySerializer,
)

CACHE_LISTE_SINIRI = 100
CACHE_SURESI = 3600

# C1 — Cache her kayitta degil, her CACHE_YENILEME_ARALIGI kayitta bir ve cekim
# sonunda kurulur. Yeniden kurma basina ~60 ms (tam sorgu + 100 nesne
# serilestirme + Redis yazimi) olculdu. Tamamen sona birakilmaz: frontend listeyi
# 5 sn'de bir ister ve cekim surerken yeni kayitlarin ekrana akmasina dayanir.
CACHE_YENILEME_ARALIGI = 10

# bolum -> (model, serializer, siralama, liste anahtari, zaman anahtari)
# Anahtar adlari news/views.py ile ayni olmalidir.
_BOLUMLER = {
    'news': (NewsArticle, NewsArticleSerializer, '-date', 'cybersecurity_news', 'last_update'),
    'cve': (CVEEntry, CVEEntrySerializer, '-published_date', 'cve_entries', 'cve_last_update'),
    'kubernetes': (KubernetesEntry, KubernetesEntrySerializer, '-published_date', 'k8s_entries', 'k8s_last_update'),
    'sre': (SREEntry, SREEntrySerializer, '-published_date', 'sre_entries', 'sre_last_update'),
    'devtools': (DevToolsEntry, DevToolsEntrySerializer, '-published_date', 'devtools_entries', 'devtools_last_update'),
    'ai': (AINewsEntry, AINewsEntrySerializer, '-published_date', 'ai_entries', 'ai_last_update'),
}


def cache_yenile(bolum: str) -> None:
    """Bir bolumun liste cache'ini ve son guncelleme zamanini yeniden kurar."""
    model, serializer, siralama, liste_anahtari, zaman_anahtari = _BOLUMLER[bolum]
    kayitlar = model.objects.all().order_by(siralama)[:CACHE_LISTE_SINIRI]
    cache.set(liste_anahtari, serializer(kayitlar, many=True).data, CACHE_SURESI)
    cache.set(zaman_anahtari, datetime.now().isoformat(), CACHE_SURESI)
