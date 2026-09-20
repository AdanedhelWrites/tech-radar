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
        description=(
            'Siddet esigi ve uzeri kayitlari getirir. Siddet sirasi dusukten '
            'yuksege soyledir: low, medium, high, critical. Verilen deger ve '
            'ondan yuksek olan tum kayitlar donmeye devam eder; ornegin high '
            'verilirse hem high hem critical kayitlar gelir, low ve medium '
            'gelmez. Siddeti bilinmeyen kayit esik ne olursa olsun hicbir '
            'zaman dahil edilmez. Not: bu semadaki enum listesi kutuphane '
            'tarafindan alfabetik sirayla yazilir (critical, high, low, '
            'medium); bu siralama yukaridaki siddet sirasi DEGILDIR, '
            'yalnizca kutuphanenin enum listeleme bicimidir.')),
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


class HataGovdesiV1Serializer(serializers.Serializer):
    """ADR-0003 bolum 8'deki kod listesi; message insan okur, code makine."""
    code = serializers.ChoiceField(choices=[
        'unauthorized', 'invalid_cursor', 'invalid_parameter', 'not_found',
        'throttled', 'cooldown', 'internal',
    ])
    message = serializers.CharField()


class HataV1Serializer(serializers.Serializer):
    """Tek bicim hata sozlesmesi: {"error": {"code", "message"}} (ADR-0003 bolum 8)."""
    error = HataGovdesiV1Serializer()


# Her ucun gercekten uretebildigi kodlar eklenir; tamami ADR-0003 bolum 8'den.
# NOT: bu blok _delta_semasi'den once tanimlanir, cunku DELTA_SEMALARI hemen
# asagida (dict comprehension ile) _delta_semasi'yi cagirir ve DELTA_HATALARI'na
# o an ihtiyac duyar; dosyanin sonuna eklenseydi NameError olurdu.
HATA_YANITLARI = {401: HataV1Serializer}
DELTA_HATALARI = {401: HataV1Serializer, 400: HataV1Serializer, 429: HataV1Serializer}
REFRESH_HATALARI = {401: HataV1Serializer, 429: HataV1Serializer}


def _delta_semasi(bolum):
    return extend_schema_view(get=extend_schema(
        summary=f"'{bolum}' bolumunu imlecli delta ile okur",
        parameters=ORTAK_PARAMETRELER + EK_PARAMETRELER.get(bolum, []),
        responses={
            200: zarf_serializer(BOLUM_SERIALIZERLARI[bolum], ZARF_ADLARI[bolum]),
            **DELTA_HATALARI,
        },
    ))


DELTA_SEMALARI = {bolum: _delta_semasi(bolum) for bolum in BOLUM_SERIALIZERLARI}


class HealthV1Serializer(serializers.Serializer):
    status = serializers.CharField()
    version = serializers.CharField()


class BolumDurumuV1Serializer(serializers.Serializer):
    """ADR-0006 karar 4: bilincli olarak DAR. Operator alanlari buraya girmez."""
    last_success_at = serializers.DateTimeField(allow_null=True)
    last_status = serializers.CharField(allow_null=True)
    last_fetched_count = serializers.IntegerField(allow_null=True)
    last_saved_count = serializers.IntegerField(allow_null=True)
    pending_translation = serializers.IntegerField()
    total = serializers.IntegerField()


class StatusV1Serializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    sections = serializers.DictField(child=BolumDurumuV1Serializer())


class JobV1Serializer(serializers.Serializer):
    job_id = serializers.CharField()
    section = serializers.CharField()
    status = serializers.ChoiceField(
        choices=['pending', 'started', 'success', 'failure'])
    count = serializers.IntegerField(required=False)
    error = serializers.CharField(required=False)


class RefreshV1Serializer(serializers.Serializer):
    job_id = serializers.CharField(allow_null=True)
    section = serializers.CharField()
    status = serializers.ChoiceField(choices=['started', 'already_running'])
    status_url = serializers.CharField(allow_null=True)


class AtlananBolumV1Serializer(serializers.Serializer):
    section = serializers.CharField()
    retry_after = serializers.IntegerField()


class RefreshAllV1Serializer(serializers.Serializer):
    started = RefreshV1Serializer(many=True)
    already_running = RefreshV1Serializer(many=True)
    skipped = AtlananBolumV1Serializer(many=True)


HEALTH_SEMASI = extend_schema_view(get=extend_schema(
    summary='Servis ayakta mi (tokensiz)',
    description='Kubernetes probe\'lari token tasiyamaz; bu uc bilincli olarak aciktir.',
    responses={200: HealthV1Serializer},
))

STATUS_SEMASI = extend_schema_view(get=extend_schema(
    summary='Bolum basina veri tazeligi',
    responses={200: StatusV1Serializer, **HATA_YANITLARI},
))

JOB_SEMASI = extend_schema_view(get=extend_schema(
    summary='Manuel tetiklenen isin durumu',
    operation_id='v1_job_read',
    responses={200: JobV1Serializer, 404: HataV1Serializer, **HATA_YANITLARI},
))

REFRESH_SEMASI = extend_schema_view(post=extend_schema(
    summary='Tek bolum icin manuel cekim tetikler',
    operation_id='v1_bolum_refresh',
    request=None,
    responses={202: RefreshV1Serializer, 404: HataV1Serializer, **REFRESH_HATALARI},
))

REFRESH_ALL_SEMASI = extend_schema_view(post=extend_schema(
    summary='Alti bolumu birden tetikler',
    operation_id='v1_toplu_refresh',
    request=None,
    responses={202: RefreshAllV1Serializer, **REFRESH_HATALARI},
))
