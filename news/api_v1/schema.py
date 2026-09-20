"""v1 OpenAPI semasinin tanimi.

Sema metadata'si bilincli olarak view'lardan ayri tutulur: views.py zaten
imlec, filtre, hata esleme ve Celery durum cevirisi tasiyor; her uca cok
satirli dekorator eklemek dosyayi okunmaz hale getirirdi. Burada toplandiginda
"dis sozlesme neye benziyor" sorusu tek dosya okunarak yanitlanir.

Uygulama urls.py'de extend_schema_view ile yapilir. DIKKAT: extend_schema_view
view sinifini YERINDE degistirir, yeni bir sinif dondurmez -- yani views.py
metinsel olarak degismese de calisma zamaninda siniflar dekore edilir.
"""

V1_ONEKI = '/api/v1/'


def yalniz_v1(endpoints):
    """Semayi /api/v1/ ile sinirlar (preprocessing hook).

    Eski /api/* uclari frontend'e hizmet eder ve ADR-0003 onlara dis sozlesme
    vermez. Bu filtre olmadan semaya 30 eski yol girer ve istemeden sozlesme
    haline gelirler.
    """
    return [dortlu for dortlu in endpoints if dortlu[0].startswith(V1_ONEKI)]


from drf_spectacular.utils import (
    OpenApiParameter, extend_schema, extend_schema_view,
)
from rest_framework import serializers

from .serializers import (
    AINewsEntryV1Serializer, CVEEntryV1Serializer, DevToolsEntryV1Serializer,
    KubernetesEntryV1Serializer, NewsArticleV1Serializer, SEVERITY_ORDER,
    SREEntryV1Serializer,
)


def zarf_serializer(kayit_serializer, ad):
    """Delta yanit zarfini uretir: {results, next_cursor, has_more, count}.

    Alti bolum icin elle alti sinif yazmak yerine fabrika kullaniliyor; zarf
    sekli tek yerde tanimli kalir.
    """
    alanlar = {
        'results': kayit_serializer(many=True),
        'next_cursor': serializers.CharField(
            allow_null=True,
            help_text='Opak imlec. Icini acmayin; saklayip since_cursor ile '
                      'geri gonderin. Bos sonucta bile doner.'),
        'has_more': serializers.BooleanField(
            help_text='true ise ayni imlecle cekmeye devam edin.'),
        'count': serializers.IntegerField(
            help_text='Yalnizca bu sayfadaki kayit sayisi; toplam degildir.'),
    }
    return type(ad, (serializers.Serializer,), alanlar)


# Alti bolumde de gecerli parametreler.
ORTAK_PARAMETRELER = [
    OpenApiParameter(
        'since_cursor', str, description='Opak imlec. Verildiginde since yok sayilir.'),
    OpenApiParameter(
        'since', str,
        description='YYYY-MM-DD. Yalnizca since_cursor verilmediginde gecerlidir; '
                    'ilk senkronu daraltmak icindir.'),
    OpenApiParameter(
        'limit', int, description='Varsayilan 100, tavan 500.'),
    OpenApiParameter(
        'source', str, description='Virgulle ayrilmis kaynak adlari.'),
    OpenApiParameter(
        'needs_translation', bool,
        description='Cevirisi bekleyen kayitlari suzer.'),
]

SIDDET_PARAMETRELERI = [
    OpenApiParameter(
        'min_severity', str, enum=SEVERITY_ORDER,
        description='Esik ve uzeri. Siddeti bilinmeyen kayit dahil edilmez.'),
    OpenApiParameter(
        'severity', str,
        description='Virgulle ayrilmis tam eslesme, ornegin critical,high.'),
]

BOLUM_SERIALIZERLARI = {
    'news': NewsArticleV1Serializer,
    'cve': CVEEntryV1Serializer,
    'kubernetes': KubernetesEntryV1Serializer,
    'sre': SREEntryV1Serializer,
    'devtools': DevToolsEntryV1Serializer,
    'ai': AINewsEntryV1Serializer,
}

EK_PARAMETRELER = {
    'cve': SIDDET_PARAMETRELERI,
    'kubernetes': [OpenApiParameter(
        'category', str, description='Virgulle ayrilmis kategori.')],
    'devtools': [OpenApiParameter(
        'entry_type', str, description='Virgulle ayrilmis tur.')],
}

ZARF_ADLARI = {
    'news': 'NewsZarf', 'cve': 'CVEZarf', 'kubernetes': 'KubernetesZarf',
    'sre': 'SREZarf', 'devtools': 'DevToolsZarf', 'ai': 'AIZarf',
}


def _delta_semasi(bolum):
    return extend_schema_view(get=extend_schema(
        summary=f"'{bolum}' bolumunu imlecli delta ile okur",
        parameters=ORTAK_PARAMETRELER + EK_PARAMETRELER.get(bolum, []),
        responses={200: zarf_serializer(BOLUM_SERIALIZERLARI[bolum], ZARF_ADLARI[bolum])},
    ))


DELTA_SEMALARI = {bolum: _delta_semasi(bolum) for bolum in BOLUM_SERIALIZERLARI}
