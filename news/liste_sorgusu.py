"""Bolum liste uclarinin ortak sorgusu: suzme, siralama, sayfalama (2026-11-05 spec G2/G3/G5).

Liste onbellegi okunmaz: filtreli istek bayat ya da yanlis filtreli veri dondurmemeli.
Yeni kayit, arayuzun 5 sn'lik yenilemesinde dogrudan veritabanindan gorunur.
"""
from datetime import timedelta
from typing import Dict, Tuple

from django.db.models import F
from django.utils import timezone
from rest_framework.response import Response

from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)
from .serializers import (
    AINewsEntrySerializer, CVEEntrySerializer, DevToolsEntrySerializer,
    KubernetesEntrySerializer, NewsArticleSerializer, SREEntrySerializer,
)

LISTE_BOLUMLERI: Dict[str, Tuple[type, type]] = {
    'news': (NewsArticle, NewsArticleSerializer),
    'cve': (CVEEntry, CVEEntrySerializer),
    'kubernetes': (KubernetesEntry, KubernetesEntrySerializer),
    'sre': (SREEntry, SREEntrySerializer),
    'devtools': (DevToolsEntry, DevToolsEntrySerializer),
    'ai': (AINewsEntry, AINewsEntrySerializer),
}

GUN_SECENEKLERI = (1, 3, 7, 14, 30)
VARSAYILAN_BOYUT = 25
EN_FAZLA_BOYUT = 100

# onem -> (alt sinir dahil, ust sinir haric); None = sinirsiz. Skorsuz kayit hicbirine girmez.
ONEM_ARALIKLARI = {
    'kritik': (9.0, None),
    'yuksek': (7.0, 9.0),
    'orta': (4.0, 7.0),
    'dusuk': (0.0, 4.0),
}


def _tam_sayi(ham, varsayilan):
    try:
        return int(ham)
    except (TypeError, ValueError):
        return varsayilan


def liste_yaniti(request, bolum: str) -> Response:
    """`bolum` listesini istegin sorgu parametrelerine gore suzer, siralar ve sayfalar."""
    model, serializer_sinifi = LISTE_BOLUMLERI[bolum]
    parametre = request.query_params
    sorgu = model.objects.all()

    gun = _tam_sayi(parametre.get('gun'), None)
    if gun in GUN_SECENEKLERI:
        sorgu = sorgu.filter(created_at__gte=timezone.now() - timedelta(days=gun))

    kaynaklar = [k for k in (parametre.get('kaynak') or '').split(',') if k]
    if kaynaklar:
        sorgu = sorgu.filter(source__in=kaynaklar)

    if bolum == 'cve' and parametre.get('onem') in ONEM_ARALIKLARI:
        alt, ust = ONEM_ARALIKLARI[parametre['onem']]
        sorgu = sorgu.filter(cvss_score__gte=alt)
        if ust is not None:
            sorgu = sorgu.filter(cvss_score__lt=ust)

    if bolum == 'kubernetes' and parametre.get('kategori'):
        sorgu = sorgu.filter(category=parametre['kategori'])

    sirala = parametre.get('sirala')
    if sirala == 'eski':
        siralama = ('created_at', 'id')
    elif sirala == 'cvss' and bolum == 'cve':
        siralama = (F('cvss_score').desc(nulls_last=True), '-created_at', '-id')
    else:
        siralama = ('-created_at', '-id')
    sorgu = sorgu.order_by(*siralama)

    boyut = _tam_sayi(parametre.get('boyut'), VARSAYILAN_BOYUT)
    if boyut < 1:
        boyut = VARSAYILAN_BOYUT
    boyut = min(boyut, EN_FAZLA_BOYUT)

    toplam = sorgu.count()
    sayfa_sayisi = max(1, -(-toplam // boyut))
    sayfa = min(max(_tam_sayi(parametre.get('sayfa'), 1), 1), sayfa_sayisi)
    baslangic = (sayfa - 1) * boyut
    veri = serializer_sinifi(sorgu[baslangic:baslangic + boyut], many=True).data

    return Response({
        'success': True,
        'data': veri,
        'cached': False,
        'count': len(veri),
        'toplam': toplam,
        'sayfa': sayfa,
        'sayfa_sayisi': sayfa_sayisi,
        'boyut': boyut,
    })
