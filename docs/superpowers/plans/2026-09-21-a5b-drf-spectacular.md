# A5b — drf-spectacular Semasi ve `/api/v1/docs/` Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/api/v1/` icin dogru bir OpenAPI 3 semasi uretmek ve `/api/v1/schema/` + `/api/v1/docs/` uclarindan sunmak.

**Architecture:** Sema metadata'si `news/api_v1/schema.py`'de toplanir ve `urls.py`'de `extend_schema_view` ile uygulanir; `views.py` (docstring notu disinda) degismez. `serializers.py` yalnizca stdlib tip ipuclari alir. Bir preprocessing hook eski `/api/*` uclarini semadan eler.

**Tech Stack:** Django 4.2.7, djangorestframework 3.17.2, drf-spectacular[sidecar] 0.30.0, SQLite, Docker Compose.

**Spec:** [`../specs/2026-09-21-a5b-drf-spectacular-design.md`](../specs/2026-09-21-a5b-drf-spectacular-design.md)

## Global Constraints

- **Kod yorumlari ve docstring'ler aksansiz Turkce.** Mevcut `news/api_v1/` kalibi budur.
- **Testler konteyner icinde calisir:** `docker compose exec -T teknoloji-api python manage.py test news`
- **Python hot-reload yoktur.** Her duzenlemeden sonra: `docker compose restart teknoloji-api`
- **Bagimlilik degistiginde `restart` yetmez:** `docker compose up -d --build teknoloji-api teknoloji-worker teknoloji-scheduler` (ucu birden — paket `INSTALLED_APPS`'e girdigi icin worker ve scheduler de import eder; yalniz api yeniden olusturulursa digerleri **acilmaz**).
- **Mevcut 303 test kirilmamalidir.** Her task sonunda tam paket kosulur.
- **Migration yoktur.** Hicbir task model degistirmez.
- **v1 HTTP testleri `news.tests.base.V1TestCase`'ten turer** (locmem cache, WhiteNoise'suz). Token icin `self.token_basligi()` kullanilir.
- **Hicbir test aga cikmaz, gercek Celery isi kuyruga atmaz, `FLUSHDB` kullanmaz.**
- **Commit mesajlari aksansiz Turkce**, sonunda: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`
- **Dal:** `feat/a5b-drf-spectacular` (main'den).
- **Surum sabitlenir:** `drf-spectacular[sidecar]==0.30.0`.
- **Uyari yakalama API'si** (olculdu, tahmin degil): `from drf_spectacular import drainage` -> `drainage.reset_generator_stats()` uretimden once; `drainage.GENERATOR_STATS._warn_cache` ve `._error_cache` listeleri; `bool(drainage.GENERATOR_STATS)` ikisinden biri doluysa `True`.

---

## Baslangic Durumu (olculdu 2026-09-21)

Dekorasyonsuz uretimde: **41 yol** (11 v1 + 30 eski `/api/*`), `_warn_cache` **26**, `_error_cache` **35**. Uc temizlik birbirinden bagimsizdir ve sirayla dusurulur:

| Kaynak | Adet | Hangi task dusurur |
|---|---|---|
| Eski `/api/*` view'larindan gelen hatalar | `_error_cache`'in cogu | Task 1 (v1 filtresi) |
| Serializer method-field uyarilari | `_warn_cache` 26 | Task 2 (tip ipuclari) |
| v1'in serializer'siz dort ucu | `_error_cache`'in kalani | Task 4 (yanit serializer'lari) |

Bu yuzden **"sifir uyari" assert'i ancak Task 4'te** yazilabilir. Onceki task'lar kendi dilimlerini assert eder.

---

### Task 1: Bagimlilik, ayarlar, v1 filtresi ve `/api/v1/schema/`

**Files:**
- Modify: `requirements.txt`
- Modify: `cybernews/settings.py`
- Create: `news/api_v1/schema.py`
- Modify: `news/api_v1/urls.py`
- Test: `news/tests/test_schema.py` (yeni)

**Interfaces:**
- Produces: `news.api_v1.schema.yalniz_v1(endpoints)` — preprocessing hook, `(path, path_regex, method, callback)` dortlulerinden olusan listeyi alir, ayni bicimde filtrelenmis liste dondurur.
- Produces: `/api/v1/schema/` rotasi, URL adi `v1-schema`.
- Produces (test yardimcisi): `news.tests.test_schema.sema_uret()` — sema sozlugu dondurur, uretim oncesi istatistikleri sifirlar.

- [ ] **Step 1: Dali ac**

```bash
git checkout main
git checkout -b feat/a5b-drf-spectacular
```

- [ ] **Step 2: Bagimliligi ekle**

`requirements.txt` sonuna:

```
drf-spectacular[sidecar]==0.30.0
```

- [ ] **Step 3: Imaji yeniden olustur (restart YETMEZ)**

```bash
docker compose up -d --build teknoloji-api teknoloji-worker teknoloji-scheduler
```

Dogrula — **ucu de ayakta olmali ve servis cevap vermeli**. Paket yalniz api'ye kurulursa worker ve scheduler `INSTALLED_APPS`'teki modulu bulamaz ve **acilmaz**:

```bash
docker compose ps
docker compose exec -T teknoloji-api python -c "
import urllib.request, json
print(json.load(urllib.request.urlopen('http://localhost:8000/api/v1/health/', timeout=10)))
"
```

Beklenen: alti servis `Up`; health ciktisi `{'status': 'ok', 'version': 'v1'}`.

- [ ] **Step 4: Basarisiz testi yaz**

`news/tests/test_schema.py` (yeni dosya):

```python
"""OpenAPI semasi (A5b). Sema dis sozlesmedir; buradaki assert'ler onu korur."""
from drf_spectacular import drainage
from drf_spectacular.generators import SchemaGenerator

from news.tests.base import V1TestCase


def sema_uret():
    """Semayi uretir. Istatistikler uretim oncesi sifirlanir ki onceki
    calismalardan kalan uyarilar sonuca karismasin."""
    drainage.reset_generator_stats()
    return SchemaGenerator().get_schema(request=None, public=True)


class SemaKapsamiTests(V1TestCase):

    def test_sema_yalniz_v1_yollarini_icerir(self):
        yollar = list(sema_uret()['paths'])

        self.assertTrue(yollar, 'sema hic yol uretmedi')
        v1_disi = [y for y in yollar if not y.startswith('/api/v1/')]
        self.assertEqual(v1_disi, [], f'eski uclar semaya sizdi: {v1_disi}')

    def test_sema_ucu_tokensiz_401(self):
        yanit = self.client.get('/api/v1/schema/')

        self.assertEqual(yanit.status_code, 401)

    def test_sema_ucu_token_ile_200(self):
        yanit = self.client.get('/api/v1/schema/', **self.token_basligi())

        self.assertEqual(yanit.status_code, 200)
```

- [ ] **Step 5: Testi kosup dustugunu gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema -v 2
```

Beklenen: `test_sema_yalniz_v1_yollarini_icerir` 30 eski yolu listeleyerek FAIL; iki uc testi 404 aldigi icin FAIL.

- [ ] **Step 6: `settings.py`'yi duzenle**

`INSTALLED_APPS` icinde `'news',` satirindan once:

```python
    'drf_spectacular',
    'drf_spectacular_sidecar',
```

`REST_FRAMEWORK` sozlugune:

```python
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
```

`REST_FRAMEWORK` blogunun hemen ardina:

```python
# Sema yalnizca /api/v1/ icindir. DEFAULT_SCHEMA_CLASS global bir ayardir ve
# teknik olarak eski /api/* view'larini da kapsar, ama davranissal etkisi
# yoktur: sema sinifi yalnizca sema uretiminde kullanilir, istek isleme
# yolunda degil. Eski uclar ayrica asagidaki hook ile semadan tamamen elenir.
SPECTACULAR_SETTINGS = {
    'TITLE': 'CyberNews Entegrasyon API',
    'DESCRIPTION': (
        'Dis tuketiciler icin imlecli delta senkron API. Tuketici tarafi upsert '
        'olmalidir ve birlestirme anahtari `id` DEGILDIR: `cve` bolumunde '
        '`cve_id`, diger bes bolumde `link` kullanilir. Ayrinti icin README '
        'icindeki "Entegrasyon API" bolumune bakiniz.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'PREPROCESSING_HOOKS': ['news.api_v1.schema.yalniz_v1'],
    'SWAGGER_UI_DIST': 'SIDECAR',
    'SWAGGER_UI_FAVICON_HREF': 'SIDECAR',
}
```

- [ ] **Step 7: `news/api_v1/schema.py`'yi olustur**

```python
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
```

- [ ] **Step 8: `urls.py`'ye sema rotasini ekle**

`news/api_v1/urls.py` bastan asagi:

```python
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
```

- [ ] **Step 9: Yeniden baslat ve testi kosup gectigini gor**

```bash
docker compose restart teknoloji-api
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema -v 2
```

Beklenen: uc test de PASS.

- [ ] **Step 10: Tam paketi kos**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 306 tests` (303 + 3), `OK`.

- [ ] **Step 11: Commit**

```bash
git add requirements.txt cybernews/settings.py news/api_v1/schema.py news/api_v1/urls.py news/tests/test_schema.py
git commit -m "feat: drf-spectacular kurulumu ve /api/v1/schema/ ucu

Sema yalnizca /api/v1/ kapsar: preprocessing hook eski 30 /api/* yolunu eler.
ADR-0003 onlara dis sozlesme vermez; semaya girerlerse istemeden sozlesme
olurlardi.

Sema ucu kimlik dogrulamasi ister. TokenAuthentication listede ilk siradadir
cunku DRF WWW-Authenticate basligini ondan turetir; boylece kimliksiz istek
403 degil 401 alir. SessionAuthentication tarayici icin gerekli.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Serializer tip ipuclari — 26 method-field uyarisini sifirla

**Files:**
- Modify: `news/api_v1/serializers.py`
- Test: `news/tests/test_schema.py`

**Interfaces:**
- Consumes: `sema_uret()` (Task 1).
- Produces: `news.api_v1.serializers.DilAlani` ve `SiddetAlani` TypedDict'leri.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_schema.py` sonuna:

```python
class SerializerTipleriTests(V1TestCase):

    def test_method_field_uyarisi_kalmadi(self):
        sema_uret()

        uyarilar = [u for u in drainage.GENERATOR_STATS._warn_cache
                    if 'unable to resolve type hint' in str(u)]
        self.assertEqual(uyarilar, [], f'{len(uyarilar)} method-field uyarisi kaldi')

    def test_title_string_degil_nesne_olarak_belgelenir(self):
        bilesenler = sema_uret()['components']['schemas']

        title = bilesenler['CVEEntryV1']['properties']['title']
        self.assertEqual(title['type'], 'object')
        self.assertEqual(sorted(title['properties']), ['original', 'tr'])

    def test_severity_kod_ve_etiket_olarak_belgelenir(self):
        bilesenler = sema_uret()['components']['schemas']

        severity = bilesenler['CVEEntryV1']['properties']['severity']
        self.assertEqual(severity['type'], 'object')
        self.assertEqual(sorted(severity['properties']), ['code', 'label'])

    def test_translation_provider_nullable(self):
        bilesenler = sema_uret()['components']['schemas']

        alan = bilesenler['CVEEntryV1']['properties']['translation_provider']
        self.assertTrue(alan.get('nullable'), 'translation_provider nullable olmali')
```

- [ ] **Step 2: Testi kosup dustugunu gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema.SerializerTipleriTests -v 2
```

Beklenen: `test_method_field_uyarisi_kalmadi` 26 uyari ile FAIL; `title` ve `severity` testleri `type` degeri `string` oldugu icin FAIL; `nullable` testi FAIL.

- [ ] **Step 3: Tip ipuclarini ekle**

`news/api_v1/serializers.py` — import blogunun hemen ardina:

```python
from typing import Optional, TypedDict


class DilAlani(TypedDict):
    """title / description alanlarinin ic bicimi."""
    original: str
    tr: str


class SiddetAlani(TypedDict):
    """severity alaninin ic bicimi: kod makine, etiket insan icindir."""
    code: str
    label: str
```

`BaseEntrySerializer` icindeki dort metoda donus ipucu ekle (govdeler **degismez**):

```python
    def get_type(self, obj) -> str:
        return self.entry_type_name

    def get_title(self, obj) -> DilAlani:
        return {'original': obj.original_title, 'tr': obj.turkish_title}

    def get_description(self, obj) -> DilAlani:
        return {'original': obj.original_description, 'tr': obj.turkish_description}

    def get_translation_provider(self, obj) -> Optional[str]:
        # 'google', 'libretranslate', 'gemini' veya ceviri yoksa null. Tuketici
        # 'libretranslate' icin "makine cevirisi" etiketi gosterebilir.
        return obj.translation_provider or None
```

`CVEEntryV1Serializer` icindeki metoda:

```python
    def get_severity(self, obj) -> SiddetAlani:
        return {'code': SEVERITY_TR_TO_CODE.get(obj.severity), 'label': obj.severity}
```

- [ ] **Step 4: Yeniden baslat ve testi kosup gectigini gor**

```bash
docker compose restart teknoloji-api
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema -v 2
```

Beklenen: yedi test de PASS.

- [ ] **Step 5: Tam paketi kos**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 310 tests`, `OK`. Serializer davranisi degismedigi icin mevcut testler etkilenmez.

- [ ] **Step 6: Commit**

```bash
git add news/api_v1/serializers.py news/tests/test_schema.py
git commit -m "feat: serializer method field'larina tip ipucu — 26 sema uyarisi sifirlandi

Ipucu olmadan drf-spectacular bes method field'i 'string' olarak belgeliyordu.
title gercekte {original, tr}, severity {code, label} donuyor; sema yanlisti
ve bu semadan istemci ureten biri derlenen ama calismayan kod alirdi.

TypedDict kullanildi, @extend_schema_field degil: boylece serializers.py
stdlib disinda hicbir sey import etmez ve sema kutuphanesi schema.py ile
settings.py'de kalir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Delta uclari — zarf semasi ve dokuz query parametresi

**Files:**
- Modify: `news/api_v1/schema.py`
- Modify: `news/api_v1/urls.py`
- Test: `news/tests/test_schema.py`

**Interfaces:**
- Consumes: `sema_uret()` (Task 1); `DilAlani`, `SiddetAlani` (Task 2).
- Produces: `news.api_v1.schema.zarf_serializer(kayit_serializer, ad)` -> `Serializer` alt sinifi.
- Produces: `news.api_v1.schema.DELTA_SEMALARI` — `{bolum_adi: extend_schema_view dekoratoru}` sozlugu; anahtarlar `news`, `cve`, `kubernetes`, `sre`, `devtools`, `ai`.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_schema.py` sonuna:

```python
DELTA_YOLLARI = {
    'news': '/api/v1/news/',
    'cve': '/api/v1/cve/',
    'kubernetes': '/api/v1/kubernetes/',
    'sre': '/api/v1/sre/',
    'devtools': '/api/v1/devtools/',
    'ai': '/api/v1/ai/',
}

ORTAK_PARAMETRELER = {
    'since_cursor', 'since', 'limit', 'source', 'needs_translation',
}


class DeltaSemasiTests(V1TestCase):

    def _get(self, sema, yol):
        return sema['paths'][yol]['get']

    def test_delta_uclari_zarf_dondurur(self):
        sema = sema_uret()

        for bolum, yol in DELTA_YOLLARI.items():
            with self.subTest(bolum=bolum):
                govde = self._get(sema, yol)['responses']['200']
                ref = govde['content']['application/json']['schema']['$ref']
                ad = ref.rsplit('/', 1)[-1]
                zarf = sema['components']['schemas'][ad]['properties']
                self.assertEqual(
                    sorted(zarf), ['count', 'has_more', 'next_cursor', 'results'])
                self.assertEqual(zarf['results']['type'], 'array')

    def test_ortak_parametreler_her_delta_ucunda(self):
        sema = sema_uret()

        for bolum, yol in DELTA_YOLLARI.items():
            with self.subTest(bolum=bolum):
                adlar = {p['name'] for p in self._get(sema, yol)['parameters']}
                self.assertTrue(ORTAK_PARAMETRELER <= adlar,
                                f'{bolum} eksik: {ORTAK_PARAMETRELER - adlar}')

    def test_bolume_ozgu_parametreler(self):
        sema = sema_uret()

        def adlar(yol):
            return {p['name'] for p in self._get(sema, yol)['parameters']}

        self.assertTrue({'min_severity', 'severity'} <= adlar(DELTA_YOLLARI['cve']))
        self.assertIn('category', adlar(DELTA_YOLLARI['kubernetes']))
        self.assertIn('entry_type', adlar(DELTA_YOLLARI['devtools']))
        # Sizinti olmamali: severity yalniz CVE'nindir
        self.assertNotIn('min_severity', adlar(DELTA_YOLLARI['news']))
        self.assertNotIn('category', adlar(DELTA_YOLLARI['sre']))

    def test_min_severity_gecerli_degerleri_enum_olarak_verir(self):
        sema = sema_uret()

        parametreler = self._get(sema, DELTA_YOLLARI['cve'])['parameters']
        ms = next(p for p in parametreler if p['name'] == 'min_severity')
        self.assertEqual(ms['schema']['enum'],
                         ['low', 'medium', 'high', 'critical'])
```

- [ ] **Step 2: Testi kosup dustugunu gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema.DeltaSemasiTests -v 2
```

Beklenen: dordu de FAIL — 200 semasi ciplak serializer'a isaret ediyor ve `parameters` anahtari yok (`KeyError`).

- [ ] **Step 3: `schema.py`'ye zarf fabrikasini ve parametreleri ekle**

`news/api_v1/schema.py` sonuna:

```python
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
```

- [ ] **Step 4: `urls.py`'de delta view'larina uygula**

`from . import views` satirinin ardina:

```python
from .schema import DELTA_SEMALARI
```

Alti delta satirini degistir:

```python
    path('news/', DELTA_SEMALARI['news'](views.NewsDeltaView).as_view(), name='v1-news'),
    path('cve/', DELTA_SEMALARI['cve'](views.CVEDeltaView).as_view(), name='v1-cve'),
    path('kubernetes/', DELTA_SEMALARI['kubernetes'](views.KubernetesDeltaView).as_view(),
         name='v1-kubernetes'),
    path('sre/', DELTA_SEMALARI['sre'](views.SREDeltaView).as_view(), name='v1-sre'),
    path('devtools/', DELTA_SEMALARI['devtools'](views.DevToolsDeltaView).as_view(),
         name='v1-devtools'),
    path('ai/', DELTA_SEMALARI['ai'](views.AIDeltaView).as_view(), name='v1-ai'),
```

- [ ] **Step 5: Yeniden baslat ve testi kosup gectigini gor**

```bash
docker compose restart teknoloji-api
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema -v 2
```

Beklenen: on bir test de PASS.

- [ ] **Step 6: Tam paketi kos**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 314 tests`, `OK`. Ozellikle `test_cursor.py` ve `test_filters.py` kirilmamalidir — dekorator davranisi degil yalnizca `schema` niteligini ekler.

- [ ] **Step 7: Commit**

```bash
git add news/api_v1/schema.py news/api_v1/urls.py news/tests/test_schema.py
git commit -m "feat: delta uclarinin zarf semasi ve dokuz query parametresi

Dekorasyonsuz uretimde delta uclarinin 200 semasi zarf yerine ciplak
serializer yaziyordu -- tuketici tek nesne donuyor saniyordu -- ve dokuz
parametrenin hicbiri gorunmuyordu.

Zarf alti bolum icin fabrika ile uretiliyor; sekil tek yerde tanimli.
Bolume ozgu parametreler yalniz ait olduklari uca ekleniyor, test sizinti
olmadigini da dogruluyor.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Delta disi uclar, hata kod haritasi, `operationId` ve sifir uyari

**Files:**
- Modify: `news/api_v1/schema.py`
- Modify: `news/api_v1/urls.py`
- Test: `news/tests/test_schema.py`

**Interfaces:**
- Consumes: `zarf_serializer`, `DELTA_SEMALARI`, `ORTAK_PARAMETRELER` (Task 3).
- Produces: `news.api_v1.schema.HATA_YANITLARI` — `{http_kodu: HataV1Serializer}` sozlugu.
- Produces: `news.api_v1.schema.HEALTH_SEMASI`, `STATUS_SEMASI`, `JOB_SEMASI`, `REFRESH_SEMASI`, `REFRESH_ALL_SEMASI` — `extend_schema_view` dekoratorleri.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_schema.py` sonuna:

```python
class DeltaDisiUclarTests(V1TestCase):

    def test_hicbir_uyari_veya_hata_kalmadi(self):
        sema_uret()

        uyarilar = list(drainage.GENERATOR_STATS._warn_cache)
        hatalar = list(drainage.GENERATOR_STATS._error_cache)
        self.assertEqual(uyarilar, [], f'{len(uyarilar)} uyari kaldi')
        self.assertEqual(hatalar, [], f'{len(hatalar)} hata kaldi')

    def test_delta_disi_uclarin_200_semasi_var(self):
        sema = sema_uret()

        for yol, yontem in [('/api/v1/health/', 'get'), ('/api/v1/status/', 'get'),
                            ('/api/v1/jobs/{job_id}/', 'get'),
                            ('/api/v1/refresh/', 'post')]:
            with self.subTest(yol=yol):
                govde = sema['paths'][yol][yontem]['responses']
                self.assertIn('200', govde, f'{yol} icin 200 semasi yok')

    def test_status_semasi_operator_alanlarini_icermez(self):
        sema = sema_uret()

        metin = str(sema['components']['schemas'])
        # ADR-0006 karar 4: bunlar FetchRun'da ve admin'de yasar, /status/'ta degil
        for alan in ('by_provider', 'stopped_reason'):
            self.assertNotIn(alan, metin, f"{alan} dis semaya sizdi")

    def test_operation_id_degerleri_benzersiz(self):
        sema = sema_uret()

        kimlikler = [op['operationId']
                     for yol in sema['paths'].values()
                     for op in yol.values() if isinstance(op, dict) and 'operationId' in op]
        cakisan = {k for k in kimlikler if kimlikler.count(k) > 1}
        self.assertEqual(cakisan, set(), f'cakisan operationId: {cakisan}')

    def test_401_hata_sozlesmesi_belgelenir(self):
        sema = sema_uret()

        yanitlar = sema['paths']['/api/v1/cve/']['get']['responses']
        self.assertIn('401', yanitlar)
```

- [ ] **Step 2: Testi kosup dustugunu gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema.DeltaDisiUclarTests -v 2
```

Beklenen: bes test de FAIL — `_error_cache` dolu, dort ucun 200 semasi yok, iki `refresh` ucu ayni `operationId`'yi uretiyor, `401` belgelenmemis.

- [ ] **Step 3: `schema.py`'ye yanit serializer'larini ekle**

`news/api_v1/schema.py` sonuna:

```python
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
HATA_YANITLARI = {401: HataV1Serializer}
DELTA_HATALARI = {401: HataV1Serializer, 400: HataV1Serializer, 429: HataV1Serializer}
REFRESH_HATALARI = {401: HataV1Serializer, 429: HataV1Serializer}


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
```

- [ ] **Step 4: Delta semalarina hata yanitlarini ekle**

`_delta_semasi` icindeki `responses` satirini degistir:

```python
        responses={
            200: zarf_serializer(BOLUM_SERIALIZERLARI[bolum], ZARF_ADLARI[bolum]),
            **DELTA_HATALARI,
        },
```

- [ ] **Step 5: `urls.py`'de kalan view'lara uygula**

Import satirini genislet:

```python
from .schema import (
    DELTA_SEMALARI, HEALTH_SEMASI, JOB_SEMASI, REFRESH_ALL_SEMASI,
    REFRESH_SEMASI, STATUS_SEMASI,
)
```

Dort satiri degistir:

```python
    path('health/', HEALTH_SEMASI(views.HealthView).as_view(), name='v1-health'),
    path('status/', STATUS_SEMASI(views.StatusView).as_view(), name='v1-status'),
    path('refresh/', REFRESH_ALL_SEMASI(views.RefreshAllView).as_view(),
         name='v1-refresh-all'),
    path('<str:section>/refresh/', REFRESH_SEMASI(views.RefreshView).as_view(),
         name='v1-refresh'),
    path('jobs/<str:job_id>/', JOB_SEMASI(views.JobView).as_view(), name='v1-job'),
```

- [ ] **Step 6: Yeniden baslat ve testi kosup gectigini gor**

```bash
docker compose restart teknoloji-api
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema -v 2
```

Beklenen: on alti test de PASS. **Ozellikle `test_hicbir_uyari_veya_hata_kalmadi` gecmelidir** — bu, Task 1/2/4'un uc temizliginin birlikte tamamlandiginin kanitidir.

- [ ] **Step 7: Tam paketi kos**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 319 tests`, `OK`. `test_status.py`, `test_refresh.py` ve `test_jobs.py` kirilmamalidir.

- [ ] **Step 8: Commit**

```bash
git add news/api_v1/schema.py news/api_v1/urls.py news/tests/test_schema.py
git commit -m "feat: delta disi uclarin semasi, hata kod haritasi ve operationId

Health/status/jobs/refresh uclari 'unable to guess serializer' hatasi
veriyordu ve 200 semalari hic uretilmiyordu. Iki refresh ucu ayni
operationId'yi (v1_refresh_create) uretiyordu; istemci ureteci _2 sonekli
metot adi basardi. Ikisine de acik operation_id verildi.

Sema artik SIFIR uyari ve SIFIR hata ile uretiliyor. Bu uc adimin toplami:
v1 filtresi eski uclarin hatalarini, tip ipuclari method field uyarilarini,
bu task da kalan serializer'siz uclari dusurdu.

/status/ semasi ADR-0006 karar 4'e sadik kalir: by_provider ve stopped_reason
dis semaya girmez, test bunu dogrular.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: `/api/v1/docs/` — Swagger UI, sidecar ve views.py yon gosterme notu

**Files:**
- Modify: `news/api_v1/urls.py`
- Modify: `news/api_v1/views.py` (yalnizca modul docstring'i)
- Test: `news/tests/test_schema.py`

**Interfaces:**
- Consumes: `/api/v1/schema/` rotasi ve `v1-schema` URL adi (Task 1).
- Produces: `/api/v1/docs/` rotasi, URL adi `v1-docs`.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_schema.py` sonuna:

```python
class DocsUcuTests(V1TestCase):

    def test_docs_tokensiz_401(self):
        yanit = self.client.get('/api/v1/docs/')

        self.assertEqual(yanit.status_code, 401)

    def test_docs_token_ile_200(self):
        yanit = self.client.get('/api/v1/docs/', **self.token_basligi())

        self.assertEqual(yanit.status_code, 200)

    def test_docs_varliklari_cdn_den_degil_yerelden_gelir(self):
        yanit = self.client.get('/api/v1/docs/', **self.token_basligi())

        govde = yanit.content.decode()
        # Sidecar varliklari /static/ altindan sunulur; internetsiz k8s
        # ortaminda docs sayfasinin bos acilmamasi buna bagli.
        self.assertNotIn('unpkg.com', govde)
        self.assertNotIn('cdn.jsdelivr.net', govde)
        self.assertIn('/static/drf_spectacular_sidecar/', govde)
```

- [ ] **Step 2: Testi kosup dustugunu gor**

```bash
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema.DocsUcuTests -v 2
```

Beklenen: uc test de FAIL (rota yok, 404).

- [ ] **Step 3: `urls.py`'ye docs rotasini ekle**

Import satirina `SpectacularSwaggerView` ekle:

```python
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
```

`SemaGorunumu` tanimindan sonra:

```python
DocsGorunumu = SpectacularSwaggerView.as_view(
    url_name='v1-schema',
    authentication_classes=[TokenAuthentication, SessionAuthentication],
    permission_classes=[IsAuthenticated],
)
```

`urlpatterns` icinde `schema/` satirinin ardina:

```python
    path('docs/', DocsGorunumu, name='v1-docs'),
```

- [ ] **Step 4: `views.py` modul docstring'ine yon gosterme notu ekle**

Mevcut docstring'in sonuna iki satir (**baska hicbir sey degismez**):

```python
Bu view'larin OpenAPI semasi burada degil news/api_v1/schema.py'de tanimlidir
ve urls.py'de extend_schema_view ile uygulanir (A5b).
"""
```

- [ ] **Step 5: Yeniden baslat ve testi kosup gectigini gor**

```bash
docker compose restart teknoloji-api
docker compose exec -T teknoloji-api python manage.py test news.tests.test_schema -v 2
```

Beklenen: on dokuz test de PASS.

- [ ] **Step 6: Tam paketi kos**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 322 tests`, `OK`.

- [ ] **Step 7: Commit**

```bash
git add news/api_v1/urls.py news/api_v1/views.py news/tests/test_schema.py
git commit -m "feat: /api/v1/docs/ — Swagger UI, varliklar sidecar'dan

Swagger UI varsayilan olarak JS/CSS'i CDN'den ceker; k8s'te internet erisimi
olmayan bir ortamda docs sayfasi bos acilirdi. [sidecar] varliklari imajdan
sunar; test CDN alan adlarinin govdede olmadigini da dogrular.

Docs ucu TokenAuthentication + SessionAuthentication tasir. Yalniz token
olsaydi tarayici Authorization basligi gondermedigi icin arayuz hicbir zaman
acilamazdi; admin oturumu acan kullanici docs'u tarayicida acar.

views.py'ye yalnizca semanin schema.py'de yasadigini soyleyen iki satirlik
docstring notu eklendi -- dekorator sinifi yerinde degistirdigi icin dosyaya
bakan biri bunu goremezdi.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Dokumantasyon, canli dogrulama ve merge

**Files:**
- Modify: `README.md`
- Modify: `docs/ADR-0003-Entegrasyon-API-v1.md`

**Interfaces:**
- Consumes: Task 1-5'in tamami.

- [ ] **Step 1: README'ye sema uclarini ekle**

`## Entegrasyon API (/api/v1/)` bolumundeki uc nokta tablosuna, `health` satirindan once iki satir:

```markdown
| GET | `/api/v1/schema/` | OpenAPI 3 semasi (token gerekir) |
| GET | `/api/v1/docs/` | Swagger UI — tarayicida admin oturumuyla acilir |
```

Ayni bolumun sonuna yeni alt bolum:

```markdown
### Makine tarafindan okunur sozlesme

`/api/v1/schema/` OpenAPI 3 dokumani dondurur ve yalnizca `/api/v1/` uclarini
kapsar; eski `/api/*` uclari bilincli olarak disaridadir.

```bash
curl -H "Authorization: Token $CYBERNEWS_TOKEN" \
  http://localhost:8000/api/v1/schema/ -o cybernews-v1.yaml
```

Semadan istemci uretilebilir (`openapi-generator` vb.). `/api/v1/docs/` ayni
semayi Swagger UI ile gosterir; tarayici `Authorization` basligi gondermedigi
icin bu sayfa **admin'de oturum acmis** bir kullaniciyla acilir.

> **Not:** Sema yayimlandigi andan itibaren dis sozlesmedir. Bir alanin tipi
> degisirse bu artik "dokumantasyon hatasi" degil, tuketicinin istemcisini
> kiran bir degisikliktir.
```

- [ ] **Step 2: ADR-0003'u guncelle**

Status blogundaki A5b cumlesini degistir:

```markdown
**A5 ikiye bolundu (2026-09-21).** **A5a uygulandi:** ornek istemci
(`scripts/ornek_istemci.py`), README entegrasyon bolumu, env degiskenleri ve
upsert kuralinin duzeltilmesi. **A5b uygulandi (2026-09-21):** drf-spectacular
semasi, `/api/v1/schema/` ve `/api/v1/docs/`.
```

"Acik isler" maddesindeki A5b cumlesini degistir:

```markdown
**A5b tamamlandi (2026-09-21):** drf-spectacular semasi, `/api/v1/schema/` ve
`/api/v1/docs/`. **Sema artik dis sozlesmedir:** bugune kadar sozlesmeyi README
tasiyordu ve bir hata dokumantasyon hatasiydi; sema yayimlandiktan sonra ayni
hata tuketicinin istemcisini kirar. Alan tipi degisiklikleri bu gozle
degerlendirilmelidir. Faz B — PostgreSQL ve Helm dogrulamasi ayri karar.
```

- [ ] **Step 3: Tam paketi kos**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 322 tests`, `OK`.

- [ ] **Step 4: Canli dogrulama — sema**

```bash
docker compose exec -T teknoloji-api python -c "
import os, django, json, urllib.request
os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings'); django.setup()
from rest_framework.authtoken.models import Token
tok = Token.objects.first().key
r = urllib.request.Request('http://localhost:8000/api/v1/schema/?format=json',
                           headers={'Authorization': f'Token {tok}'})
sema = json.load(urllib.request.urlopen(r, timeout=30))
yollar = list(sema['paths'])
print('yol sayisi:', len(yollar))
print('v1 disi:', [y for y in yollar if not y.startswith('/api/v1/')])
"
```

Beklenen: `yol sayisi: 13` (11 mevcut + `schema/` + `docs/`; `SERVE_INCLUDE_SCHEMA=False` ise 11), `v1 disi: []`.

**Not:** yol sayisi beklenenden farkli cikarsa `SERVE_INCLUDE_SCHEMA` ayarinin etkisidir; `v1 disi: []` olmasi sart olan kisimdir.

- [ ] **Step 5: Canli dogrulama — uyarisiz uretim**

```bash
docker compose exec -T teknoloji-api python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings'); django.setup()
from drf_spectacular import drainage
from drf_spectacular.generators import SchemaGenerator
drainage.reset_generator_stats()
SchemaGenerator().get_schema(request=None, public=True)
print('uyari:', len(drainage.GENERATOR_STATS._warn_cache))
print('hata :', len(drainage.GENERATOR_STATS._error_cache))
"
```

Beklenen: `uyari: 0`, `hata : 0`.

- [ ] **Step 6: Canli dogrulama — ornek istemci hala calisiyor**

A5a'nin script'i v1 davranisinin degismedigini kanitlar:

```bash
docker compose exec -T teknoloji-api python -c "
import os, django, runpy
os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings'); django.setup()
from rest_framework.authtoken.models import Token
os.environ['CYBERNEWS_TOKEN'] = Token.objects.first().key
os.environ['CYBERNEWS_URL'] = 'http://localhost:8000'
runpy.run_path('scripts/ornek_istemci.py', run_name='__main__')
"
docker compose exec -T teknoloji-api rm -f scripts/ornek_istemci_durum.json
```

Beklenen: alti bolum icin kayit cekilir, hata yok.

- [ ] **Step 7: Canli dogrulama — docs tarayicida**

Tarayicida `http://localhost:8000/admin/` adresinden oturum ac, sonra
`http://localhost:8000/api/v1/docs/` adresini ac.

Beklenen: Swagger UI yuklenir; tarayicinin ag sekmesinde **unpkg.com veya
jsdelivr.net'e giden hicbir istek olmamalidir**. `cve` ucunun 200 orneginde
zarf gorunmeli ve `title` ic ice nesne olmalidir.

- [ ] **Step 8: Commit**

```bash
git add README.md docs/ADR-0003-Entegrasyon-API-v1.md
git commit -m "docs: A5b — README sema bolumu ve ADR-0003 guncellemesi

Sema yayimlandigi andan itibaren dis sozlesmedir; ADR-0003'e bu cumle olarak
islendi. Alan tipi degisiklikleri artik dokumantasyon hatasi degil, kiran
degisiklik olarak degerlendirilir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 9: Main'e merge et**

```bash
git checkout main
git merge --no-ff feat/a5b-drf-spectacular -m "Merge A5b: drf-spectacular semasi ve /api/v1/docs/

A5 tamamlandi; ADR-0003'un kapsami (A1-A5) kapandi. Sema yalniz /api/v1/
kapsar, sifir uyari ile uretilir ve dis sozlesmedir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git branch -d feat/a5b-drf-spectacular
```

- [ ] **Step 10: Merge sonrasi tam paketi kos**

```bash
docker compose exec -T teknoloji-api python manage.py test news
```

Beklenen: `Ran 322 tests`, `OK`.

---

## Kapsam Disi

- **Istemci SDK uretimi** — tuketici ekibin isi.
- **Sema surumleme sureci** — `VERSION = '1.0.0'` ile baslar; nasil ilerleyecegi ayri karar.
- **ReDoc** — yalniz Swagger UI.
- **Snapshot testi** — kullanici karari; spec bolum 10'daki kabul edilen sinir.
- **`NewsArticle.link` benzersizligi** — A5a'da acilan ayri gorev.
- **Faz B** — PostgreSQL ve Helm.
