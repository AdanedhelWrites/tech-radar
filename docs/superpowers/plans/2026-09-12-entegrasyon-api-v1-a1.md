# Entegrasyon API v1 — A1 Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dis tuketici uygulamalarin CyberNews verisini imlec tabanli delta cekme ile, token dogrulamasi arkasindan okuyabilecegi `/api/v1/` katmanini kurmak.

**Architecture:** Mevcut `/api/*` uc noktalarina hic dokunulmaz; yeni bir `news/api_v1/` paketi acilir. Alti bolum ortak bir `DeltaListAPIView` sinifindan turer. Siralama her zaman `(updated_at, id)` artan; sayfalama keyset (imlec) mantigiyla yapilir, offset kullanilmaz. Bu uc noktalar Redis cache'e hic bakmaz.

**Tech Stack:** Django 4.2.7, djangorestframework 3.14.0 (`rest_framework.authtoken` dahil), django-redis 5.4.0, Celery 5.3.4. A1'de **yeni pip bagimliligi eklenmez**.

**Spec:** `docs/superpowers/specs/2026-09-12-entegrasyon-api-v1-design.md`

**Kapsam:** Yalnizca spec'teki **A1** adimi. A2 (refresh/jobs), A3 (ceviri dogrulama + cache), A4 (FetchRun/gorunurluk), A5 (sema/dokuman) kendi planlarini alacak.

## Global Constraints

- **Testler konteyner icinde kosar.** Host'ta bagimliliklar yok. Tum test komutlari: `docker compose exec -T teknoloji-api python manage.py test ...`
- **Mevcut `/api/*` uc noktalari degistirilmez.** `news/views.py`, `news/urls.py`, `news/serializers.py` bu planda **hic dokunulmayan** dosyalardir. Frontend onlara bagli.
- **`REST_FRAMEWORK` icindeki mevcut anahtarlar degistirilmez.** `DEFAULT_PERMISSION_CLASSES: AllowAny` oldugu gibi kalir — degistirmek frontend'i kirar. v1 kendi izin/kimlik/throttle siniflarini view uzerinde tanimlar.
- **Kod yorumlari Turkce, aksansiz** (mevcut kod kaliyla ayni: "Ceviri", "Guncelleme", "islenir"). Kullaniciya donen mesajlar da aksansiz Turkce.
- **`fields = '__all__'` kullanilmaz.** v1 serializer'larinda alanlar tek tek yazilir.
- **`USE_TZ = True`** — tum `datetime` degerleri timezone-aware. `TIME_ZONE = 'Europe/Istanbul'`, veritabaninda UTC saklanir.
- **Siralama sabit:** v1 sorgularinda her zaman `.order_by('updated_at', 'id')`.
- **Limit:** varsayilan 100, tavan 500.
- **Her task kendi commit'ini atar.** Commit mesajlari Turkce, aksansiz, `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` satiriyla biter.
- **Calisma dali:** `feat/entegrasyon-api-v1-a1` (bu plan baslarken `main`'den veya A1 oncesi son durumdan acilir).

## Ortam Notlari (yeni bir context icin)

| Konu | Deger |
|---|---|
| Proje koku | `cybersecurity_news/` (git koku burasi) |
| API konteyneri | `teknoloji-api` |
| Worker / scheduler | `teknoloji-worker`, `teknoloji-scheduler` |
| Veritabani | Canlida SQLite (`/app/db.sqlite3`); `DATABASE_URL` set edilirse PostgreSQL |
| Redis | cache `redis://...:6379/0`, Celery broker `.../1` |
| Konteynerlar kodu bind mount ile okur (`./:/app`) | Dosya degisikligi icin rebuild gerekmez; `runserver` otomatik yeniden yukler |
| Mevcut test sayisi | 12 (hepsi gecmeli) |
| Mevcut migration | `0007_needs_translation` |

## Dosya Yapisi

**Olusturulacak:**

| Dosya | Sorumluluk |
|---|---|
| `news/api_v1/__init__.py` | Bos paket isaretcisi |
| `news/api_v1/cursor.py` | Imlec kodlama/cozme; saf fonksiyonlar, Django modeline bagimli degil |
| `news/api_v1/serializers.py` | Alti bolumun v1 serializer'lari + ortak taban |
| `news/api_v1/filters.py` | Query parametrelerini ayristirma ve queryset'e uygulama |
| `news/api_v1/views.py` | `V1APIView` (kimlik/throttle/hata bicimi), `DeltaListAPIView`, alti alt sinif, `health` |
| `news/api_v1/urls.py` | v1 yol tanimlari |
| `news/tests/__init__.py` | Test paketi |
| `news/tests/test_cursor.py` | Imlec ve delta davranisi |
| `news/tests/test_auth.py` | Token dogrulamasi |
| `news/tests/test_filters.py` | Filtreler ve limit |
| `news/migrations/0008_updated_at.py` | `updated_at` alani + bilesik index |

**Degistirilecek:**

| Dosya | Degisiklik |
|---|---|
| `news/models.py` | Alti modele `updated_at` + `Meta.indexes` |
| `cybernews/settings.py` | `INSTALLED_APPS`'e `rest_framework.authtoken`, `REST_FRAMEWORK`'e `DEFAULT_THROTTLE_RATES` |
| `cybernews/urls.py` | `path('api/v1/', include('news.api_v1.urls'))` |

**Tasinacak:**

| Kaynak | Hedef |
|---|---|
| `news/tests.py` | `news/tests/test_translation.py` |

---

### Task 1: Testleri pakete tasi

Sonraki task'larin hepsi `news/tests/` altina dosya ekleyecek. Mevcut `news/tests.py` tek dosya oldugu icin once pakete cevrilmeli.

**Files:**
- Create: `news/tests/__init__.py`
- Move: `news/tests.py` → `news/tests/test_translation.py`

**Interfaces:**
- Consumes: yok
- Produces: `news.tests` paketi. Sonraki task'lar buraya `test_*.py` ekler. Mevcut yardimci siniflar (`FakeTranslator`, `SequenceTranslator`, `TranslationGateMixin`, sabit `LOCMEM_CACHE`) artik `news.tests.test_translation` altindadir; baska bir test dosyasi bunlara ihtiyac duyarsa oradan import eder.

- [ ] **Step 1: Mevcut testlerin gectigini dogrula (taban cizgisi)**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 12 tests in ...` ve `OK`

- [ ] **Step 2: Paketi olustur ve dosyayi tasi**

```bash
mkdir -p news/tests
git mv news/tests.py news/tests/test_translation.py
printf '"""news uygulamasinin test paketi."""\n' > news/tests/__init__.py
```

- [ ] **Step 3: Testlerin hala gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 12 tests in ...` ve `OK` — sayi degismemeli. Sayi 0 cikarsa `news/tests/__init__.py` olusmamistir.

- [ ] **Step 4: Commit**

```bash
git add news/tests/
git commit -m "$(cat <<'MSG'
refactor: news testlerini pakete tasi

A1 kapsaminda imlec, kimlik dogrulama ve filtre testleri eklenecek.
Tek dosyalik tests.py yerine news/tests/ paketi kullaniliyor; mevcut
ceviri testleri test_translation.py olarak tasindi.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: `updated_at` alani, index ve migration

Imlecin dayandigi alan. Bu olmadan sonraki hicbir task calismaz.

**Files:**
- Modify: `news/models.py` (alti model)
- Create: `news/migrations/0008_updated_at.py` (Django uretir)
- Test: `news/tests/test_cursor.py`

**Interfaces:**
- Consumes: yok
- Produces: Alti modelde `updated_at` alani (`DateTimeField`, `auto_now=True`, timezone-aware) ve `(updated_at, id)` bilesik index'i. Modeller: `NewsArticle`, `CVEEntry`, `KubernetesEntry`, `SREEntry`, `DevToolsEntry`, `AINewsEntry`.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_cursor.py` olustur:

```python
"""Imlec (cursor) tabanli delta cekme testleri."""
from datetime import date

from django.test import TestCase

from news.models import AINewsEntry, CVEEntry


class UpdatedAtFieldTests(TestCase):
    """updated_at her kayitta dolu olmali ve her kayitta ilerlemeli."""

    def test_updated_at_kayit_olusturulunca_dolar(self):
        entry = AINewsEntry.objects.create(
            source='Test', original_title='A', original_description='B',
            link='https://ornek.test/1', published_date=date(2026, 9, 12),
        )
        self.assertIsNotNone(entry.updated_at)

    def test_updated_at_her_kayitta_ilerler(self):
        entry = AINewsEntry.objects.create(
            source='Test', original_title='A', original_description='B',
            link='https://ornek.test/2', published_date=date(2026, 9, 12),
        )
        once = entry.updated_at
        entry.turkish_title = 'A tercume'
        entry.save()
        entry.refresh_from_db()
        self.assertGreater(entry.updated_at, once)

    def test_cve_modelinde_de_var(self):
        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-0001', source='NVD', original_title='A',
            original_description='B', published_date=date(2026, 9, 12),
            link='https://ornek.test/cve/1',
        )
        self.assertIsNotNone(cve.updated_at)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_cursor -v 2 2>&1 | tail -20`
Expected: FAIL — `AttributeError: 'AINewsEntry' object has no attribute 'updated_at'` veya benzeri.

- [ ] **Step 3: Alti modele alani ve index'i ekle**

`news/models.py` icinde **alti modelin her birine**, `needs_translation` satirindan hemen sonra ekle:

```python
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Guncellenme Tarihi')
```

Ve **alti modelin her birinin** `class Meta` blogunun sonuna ekle:

```python
        indexes = [models.Index(fields=['updated_at', 'id'])]
```

Ornek — `AINewsEntry` icin tam hali:

```python
class AINewsEntry(models.Model):
    """Yapay Zeka (AI) haber ve benchmark modeli"""
    source = models.CharField(max_length=100, verbose_name='Kaynak')
    original_title = models.TextField(verbose_name='Orijinal Baslik')
    turkish_title = models.TextField(verbose_name='Turkce Baslik', blank=True)
    original_description = models.TextField(verbose_name='Orijinal Aciklama')
    turkish_description = models.TextField(verbose_name='Turkce Aciklama', blank=True)
    link = models.URLField(verbose_name='Link', max_length=500, unique=True)
    published_date = models.DateField(verbose_name='Yayinlanma Tarihi')
    needs_translation = models.BooleanField(default=False, verbose_name='Ceviri Bekliyor')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Guncellenme Tarihi')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Olusturulma Tarihi')

    class Meta:
        verbose_name = 'AI Haberi'
        verbose_name_plural = 'AI Haberleri'
        ordering = ['-published_date', '-created_at']
        indexes = [models.Index(fields=['updated_at', 'id'])]
```

**Alan uzerinde `db_index=True` KULLANMA.** Bilesik index zaten `updated_at` ile basliyor; tek sutunlu index gereksiz olur ve her yazimda bosuna maliyet ekler.

- [ ] **Step 4: Migration uret ve uygula**

```bash
docker compose exec -T teknoloji-api python manage.py makemigrations news --name updated_at
docker compose exec -T teknoloji-api python manage.py migrate news
```

Expected: `0008_updated_at.py` olusur; icinde alti `AddField` ve alti `AddIndex` bulunur. `migrate` ciktisi `Applying news.0008_updated_at... OK`.

Not: mevcut ~700 satira `updated_at` olarak migration anindaki zaman yazilir. Bu beklenen davranistir (spec S1) — ilk delta cekimi tum kayitlari dondurur.

- [ ] **Step 5: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_cursor -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 3 tests`, `OK`

- [ ] **Step 6: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 15 tests`, `OK`

- [ ] **Step 7: Commit**

```bash
git add news/models.py news/migrations/0008_updated_at.py news/tests/test_cursor.py
git commit -m "$(cat <<'MSG'
feat: alti modele updated_at alani ve bilesik index ekle

Entegrasyon API v1'in imlec tabanli delta cekmesi (updated_at, id)
ikilisine dayaniyor. Alti modele auto_now alani ve (updated_at, id)
bilesik index'i eklendi.

Mevcut satirlara migration anindaki zaman yazilir; ilk delta cekiminde
tum kayitlarin donmesi beklenen davranistir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: Imlec kodlama ve cozme

Saf fonksiyonlar; HTTP veya modelden bagimsiz, bu yuzden ayri ve once test edilir.

**Files:**
- Create: `news/api_v1/__init__.py`, `news/api_v1/cursor.py`
- Test: `news/tests/test_cursor.py` (mevcut dosyaya eklenir)

**Interfaces:**
- Consumes: yok
- Produces:
  - `InvalidCursor(ValueError)` — cozulemeyen imlec icin istisna
  - `encode_cursor(updated_at: datetime, pk: int) -> str`
  - `decode_cursor(value: str) -> tuple[datetime, int]`, hatada `InvalidCursor` firlatir
  - `apply_cursor(queryset, moment: datetime, pk: int) -> QuerySet` — keyset filtresini uygular

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_cursor.py` sonuna ekle:

```python
from django.utils import timezone

from news.api_v1.cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor


class CursorCodecTests(TestCase):
    """Imlec kodlanip cozuldugunde ayni degeri vermeli; bozuk girdi net hata uretmeli."""

    def test_kodla_coz_ayni_degeri_verir(self):
        moment = timezone.now()
        deger = encode_cursor(moment, 42)
        cozulen_moment, cozulen_id = decode_cursor(deger)
        self.assertEqual(cozulen_moment, moment)
        self.assertEqual(cozulen_id, 42)

    def test_imlec_opak_gorunur(self):
        """Imlec duz metin sizdirmamali; tuketici icini acmaya calismamali."""
        deger = encode_cursor(timezone.now(), 42)
        self.assertNotIn('updated_at', deger)
        self.assertNotIn('{', deger)

    def test_bozuk_imlec_hata_firlatir(self):
        for bozuk in ['', 'bu-base64-degil!!', 'YWJj', 'eyJ1IjogImdlY2Vyc2l6IiwgImkiOiAxfQ']:
            with self.subTest(bozuk=bozuk):
                with self.assertRaises(InvalidCursor):
                    decode_cursor(bozuk)


class ApplyCursorTests(TestCase):
    """apply_cursor, imlecten sonraki kayitlari dondurmeli; ayni damgada id ayirt edici olmali."""

    def setUp(self):
        self.moment = timezone.now()
        for i in range(1, 4):
            AINewsEntry.objects.create(
                source='Test', original_title=f'Baslik {i}', original_description='X',
                link=f'https://ornek.test/apply/{i}', published_date=date(2026, 9, 12),
            )
        # auto_now degerlerini elle esitle: ayni damga senaryosunu kurmak icin
        AINewsEntry.objects.all().update(updated_at=self.moment)
        self.kayitlar = list(AINewsEntry.objects.order_by('id'))

    def test_ayni_damgada_id_ayirt_eder(self):
        ilk = self.kayitlar[0]
        sonuc = apply_cursor(AINewsEntry.objects.all(), self.moment, ilk.id).order_by('id')
        self.assertEqual([k.id for k in sonuc], [self.kayitlar[1].id, self.kayitlar[2].id])

    def test_son_kayittan_sonra_bos_doner(self):
        son = self.kayitlar[-1]
        sonuc = apply_cursor(AINewsEntry.objects.all(), self.moment, son.id)
        self.assertEqual(list(sonuc), [])
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_cursor -v 2 2>&1 | tail -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'news.api_v1'`

- [ ] **Step 3: Paketi ve imlec modulunu yaz**

```bash
mkdir -p news/api_v1
printf '"""Dis tuketiciler icin entegrasyon API'"'"'si (v1)."""\n' > news/api_v1/__init__.py
```

`news/api_v1/cursor.py`:

```python
"""Imlec (cursor) kodlama ve cozme.

Imlec, (updated_at, id) ikilisinin base64url ile kodlanmis halidir. Tuketici
acisindan opaktir: icini acmamali, yalnizca saklayip geri gondermelidir. Boylece
ic bicimi ileride degistirebiliriz.

Neden sadece zaman damgasi yetmez: ayni mikrosaniyede yazilmis iki kayit varsa
tek basina updated_at ile sayfalama bunlardan birini atlar. id ikinci anahtar
olarak bu belirsizligi kaldirir.
"""
import base64
import json
from datetime import datetime

from django.db.models import Q
from django.utils.dateparse import parse_datetime


class InvalidCursor(ValueError):
    """Imlec cozulemedi."""


def encode_cursor(updated_at: datetime, pk: int) -> str:
    """(updated_at, id) ikilisini opak bir metne cevirir."""
    yuk = json.dumps({'u': updated_at.isoformat(), 'i': int(pk)}, separators=(',', ':'))
    kodlu = base64.urlsafe_b64encode(yuk.encode('utf-8')).decode('ascii')
    return kodlu.rstrip('=')


def decode_cursor(value: str):
    """Imleci (updated_at, id) ikilisine cevirir. Cozulemezse InvalidCursor firlatir."""
    if not value:
        raise InvalidCursor('Imlec bos olamaz.')
    dolgulu = value + '=' * (-len(value) % 4)
    try:
        yuk = json.loads(base64.urlsafe_b64decode(dolgulu.encode('ascii')))
        moment = parse_datetime(yuk['u'])
        pk = int(yuk['i'])
    except Exception as hata:
        raise InvalidCursor(f'Imlec cozulemedi: {hata}')
    if moment is None:
        raise InvalidCursor('Imlec icindeki tarih cozulemedi.')
    return moment, pk


def apply_cursor(queryset, moment: datetime, pk: int):
    """Imlecten sonraki kayitlari birakir (keyset sayfalama).

    (updated_at, id) > (moment, pk) kosulunun ORM karsiligi. Satir karsilastirmasi
    yerine Q kullaniliyor; bu bicim hem SQLite hem PostgreSQL'de calisir.
    """
    return queryset.filter(Q(updated_at__gt=moment) | Q(updated_at=moment, id__gt=pk))
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_cursor -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 8 tests`, `OK`

- [ ] **Step 5: Commit**

```bash
git add news/api_v1/ news/tests/test_cursor.py
git commit -m "$(cat <<'MSG'
feat: v1 imlec kodlama, cozme ve keyset filtresi

(updated_at, id) ikilisini base64url ile opak bir imlece cevirir. Ayni
zaman damgasina sahip kayitlarda id ikinci anahtar oldugu icin atlama
olmaz. Keyset filtresi Q ile yazildi; SQLite ve PostgreSQL'de calisir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: Token dogrulamasi, health uc noktasi ve URL baglama

Ilk canli uc nokta. Kimlik dogrulama iskeleti burada kurulur; sonraki task'lar uzerine biner.

**Files:**
- Modify: `cybernews/settings.py`, `cybernews/urls.py`
- Create: `news/api_v1/views.py`, `news/api_v1/urls.py`
- Test: `news/tests/test_auth.py`

**Interfaces:**
- Consumes: yok
- Produces:
  - `V1APIView(APIView)` — `authentication_classes = [TokenAuthentication]`, `permission_classes = [IsAuthenticated]`, `throttle_classes = [ScopedRateThrottle]`, `throttle_scope = 'v1_read'`. Sonraki task'lar bundan turer.
  - `HealthView(APIView)` — kimlik dogrulama ve throttle **yok** (probe'lar engellenmemeli)
  - URL onek: `/api/v1/`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_auth.py` olustur:

```python
"""v1 kimlik dogrulama testleri."""
from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token


class HealthEndpointTests(TestCase):
    """health probe'lar icin acik olmali: token istemez, throttle uygulanmaz."""

    def test_tokensiz_erisilebilir(self):
        yanit = self.client.get('/api/v1/health/')
        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.json()['status'], 'ok')


class TokenAuthTests(TestCase):
    """v1 okuma uc noktalari token ister."""

    def setUp(self):
        self.kullanici = User.objects.create_user('entegrasyon', password='parola-yok-test')
        self.token = Token.objects.create(user=self.kullanici)

    def test_tokensiz_401(self):
        yanit = self.client.get('/api/v1/ai/')
        self.assertEqual(yanit.status_code, 401)

    def test_gecersiz_token_401(self):
        yanit = self.client.get('/api/v1/ai/', HTTP_AUTHORIZATION='Token gecersiz-deger')
        self.assertEqual(yanit.status_code, 401)

    def test_gecerli_token_200(self):
        yanit = self.client.get('/api/v1/ai/', HTTP_AUTHORIZATION=f'Token {self.token.key}')
        self.assertEqual(yanit.status_code, 200)
```

Not: `/api/v1/ai/` Task 6'da yazilacak. Bu testin son uc metodu Task 6 bitene kadar 404 verecek — Step 4'te bu beklenen durumdur.

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_auth -v 2 2>&1 | tail -20`
Expected: FAIL — `/api/v1/health/` icin 404.

- [ ] **Step 3: authtoken uygulamasini ve throttle oranlarini ekle**

`cybernews/settings.py` — `INSTALLED_APPS` icinde `'rest_framework',` satirinin hemen ardina:

```python
    'rest_framework.authtoken',
```

`REST_FRAMEWORK` sozlugune **yalnizca yeni anahtar ekle**, mevcutlari degistirme:

```python
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    # v1 entegrasyon katmani throttle oranlari. Siniflar view uzerinde tanimli;
    # buradaki oranlar ScopedRateThrottle tarafindan okunur. Mevcut /api/* uc
    # noktalari etkilenmez.
    'DEFAULT_THROTTLE_RATES': {
        'v1_read': '120/min',
        'v1_refresh': '12/hour',
    },
}
```

- [ ] **Step 4: Migration'i uygula (authtoken tablosu)**

```bash
docker compose exec -T teknoloji-api python manage.py migrate
```

Expected: `Applying authtoken.0001_initial... OK` ve devami.

- [ ] **Step 5: View ve URL'leri yaz**

`news/api_v1/views.py`:

```python
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
```

`news/api_v1/urls.py`:

```python
"""v1 yol tanimlari."""
from django.urls import path

from . import views

urlpatterns = [
    path('health/', views.HealthView.as_view(), name='v1-health'),
]
```

`cybernews/urls.py` — `urlpatterns` icine, `path('', include('news.urls'))` satirindan **once** ekle:

```python
    path('api/v1/', include('news.api_v1.urls')),
```

Tam hali:

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('news.api_v1.urls')),
    path('', include('news.urls')),
]
```

- [ ] **Step 6: Testin kismen gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_auth -v 2 2>&1 | tail -25`
Expected: `HealthEndpointTests` gecer. `TokenAuthTests` icindeki uc test **404 aldigi icin duser** — `/api/v1/ai/` henuz yok. Bu bu asamada beklenen durumdur; Task 6'da gececekler.

- [ ] **Step 7: Health'i canlida dogrula**

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/health/`
Expected: `200`

- [ ] **Step 8: Commit**

```bash
git add cybernews/settings.py cybernews/urls.py news/api_v1/views.py news/api_v1/urls.py news/tests/test_auth.py
git commit -m "$(cat <<'MSG'
feat: v1 token dogrulamasi ve health uc noktasi

rest_framework.authtoken eklendi; v1 uc noktalari icin ortak V1APIView
tabani (TokenAuthentication + IsAuthenticated + ScopedRateThrottle)
yazildi. Mevcut REST_FRAMEWORK anahtarlari degistirilmedi, yalnizca
DEFAULT_THROTTLE_RATES eklendi; /api/* uc noktalari etkilenmiyor.

health uc noktasi bilincli olarak kimlik dogrulamasiz ve throttle'siz:
Kubernetes probe'lari token tasiyamaz.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: Serializer'lar

**Files:**
- Create: `news/api_v1/serializers.py`
- Test: `news/tests/test_filters.py` (serializer bicim testleri burada baslar)

**Interfaces:**
- Consumes: yok
- Produces:
  - `SEVERITY_TR_TO_CODE`, `SEVERITY_CODE_TO_TR`, `SEVERITY_ORDER` — CVE siddet esleme tablolari
  - `BaseEntrySerializer` — `id`, `type`, `source`, `title`, `description`, `link`, `published_date`, `needs_translation`, `updated_at`
  - `NewsArticleV1Serializer`, `CVEEntryV1Serializer`, `KubernetesEntryV1Serializer`, `SREEntryV1Serializer`, `DevToolsEntryV1Serializer`, `AINewsEntryV1Serializer`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_filters.py` olustur:

```python
"""v1 serializer bicimi ve filtre testleri."""
from datetime import date

from django.test import TestCase

from news.api_v1.serializers import AINewsEntryV1Serializer, CVEEntryV1Serializer
from news.models import AINewsEntry, CVEEntry


class SerializerBicimTests(TestCase):
    """Yanit bicimi sozlesmedir: alan adlari ve ic ice dil yapisi korunmali."""

    def test_ortak_alanlar_ve_ic_ice_dil(self):
        entry = AINewsEntry.objects.create(
            source='MIT Tech Review AI', original_title='Model released',
            turkish_title='Model yayinlandi', original_description='Long text',
            turkish_description='Uzun metin', link='https://ornek.test/ai/1',
            published_date=date(2026, 9, 12),
        )
        veri = AINewsEntryV1Serializer(entry).data
        self.assertEqual(set(veri.keys()), {
            'id', 'type', 'source', 'title', 'description', 'link',
            'published_date', 'needs_translation', 'updated_at',
        })
        self.assertEqual(veri['type'], 'ai')
        self.assertEqual(veri['title'], {'original': 'Model released', 'tr': 'Model yayinlandi'})
        self.assertEqual(veri['description'], {'original': 'Long text', 'tr': 'Uzun metin'})

    def test_ceviri_bekleyende_tr_bos_gelir(self):
        """Tuketici title.tr || title.original ile Ingilizceye dusebilmeli."""
        entry = AINewsEntry.objects.create(
            source='Test', original_title='Only english', original_description='Body',
            link='https://ornek.test/ai/2', published_date=date(2026, 9, 12),
            needs_translation=True,
        )
        veri = AINewsEntryV1Serializer(entry).data
        self.assertEqual(veri['title']['tr'], '')
        self.assertEqual(veri['title']['original'], 'Only english')
        self.assertTrue(veri['needs_translation'])

    def test_cve_siddeti_normalize_edilir(self):
        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-1000', source='NVD', original_title='RCE',
            original_description='Body', severity='Yüksek', cvss_score=8.8,
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/1000',
        )
        veri = CVEEntryV1Serializer(cve).data
        self.assertEqual(veri['severity'], {'code': 'high', 'label': 'Yüksek'})
        self.assertEqual(veri['cve_id'], 'CVE-2026-1000')
        self.assertEqual(veri['type'], 'cve')

    def test_bilinmeyen_siddet_kodu_none_olur(self):
        """Task'lar siddeti bulamayinca 'Bilinmiyor' yaziyor; sozlesmede kod None olur."""
        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-1001', source='NVD', original_title='X',
            original_description='Body', severity='Bilinmiyor',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/1001',
        )
        veri = CVEEntryV1Serializer(cve).data
        self.assertEqual(veri['severity'], {'code': None, 'label': 'Bilinmiyor'})
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_filters -v 2 2>&1 | tail -20`
Expected: FAIL — `ModuleNotFoundError: No module named 'news.api_v1.serializers'`

- [ ] **Step 3: Serializer'lari yaz**

`news/api_v1/serializers.py`:

```python
"""v1 serializer'lari.

Alanlar tek tek yazilir; fields = '__all__' kullanilmaz. Boylece modele alan
eklendiginde dis sozlesme kendiliginden degismez.

Dil varyantlari ic ice verilir (title.original / title.tr). Tuketici
`title.tr || title.original` yazarak ceviri bekleyen kayitlarda otomatik
olarak Ingilizceye duser.
"""
from rest_framework import serializers

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

# Veritabani siddeti Turkce saklar; dis sozlesme makine dostu kod kullanir.
SEVERITY_TR_TO_CODE = {
    'Kritik': 'critical',
    'Yüksek': 'high',
    'Orta': 'medium',
    'Düşük': 'low',
}
SEVERITY_CODE_TO_TR = {kod: tr for tr, kod in SEVERITY_TR_TO_CODE.items()}

# Dusukten yuksege; min_severity filtresi bu siralamayi kullanir.
SEVERITY_ORDER = ['low', 'medium', 'high', 'critical']


class BaseEntrySerializer(serializers.ModelSerializer):
    """Alti bolumun ortak alanlari."""

    entry_type_name = None  # alt siniflar doldurur

    type = serializers.SerializerMethodField()
    title = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()

    ORTAK_ALANLAR = [
        'id', 'type', 'source', 'title', 'description', 'link',
        'published_date', 'needs_translation', 'updated_at',
    ]

    def get_type(self, obj):
        return self.entry_type_name

    def get_title(self, obj):
        return {'original': obj.original_title, 'tr': obj.turkish_title}

    def get_description(self, obj):
        return {'original': obj.original_description, 'tr': obj.turkish_description}


class NewsArticleV1Serializer(BaseEntrySerializer):
    entry_type_name = 'news'
    # NewsArticle tarih alanini `date` olarak tutar; sozlesmede published_date olur.
    published_date = serializers.DateField(source='date', read_only=True)
    summary_tr = serializers.CharField(source='turkish_summary', read_only=True)

    class Meta:
        model = NewsArticle
        fields = BaseEntrySerializer.ORTAK_ALANLAR + ['summary_tr', 'original_date']


class CVEEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'cve'
    severity = serializers.SerializerMethodField()

    class Meta:
        model = CVEEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR + [
            'cve_id', 'severity', 'cvss_score', 'cwe_ids', 'references',
            'affected_products', 'modified_date',
        ]

    def get_severity(self, obj):
        return {'code': SEVERITY_TR_TO_CODE.get(obj.severity), 'label': obj.severity}


class KubernetesEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'kubernetes'

    class Meta:
        model = KubernetesEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR + ['category', 'version']


class SREEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'sre'

    class Meta:
        model = SREEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR


class DevToolsEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'devtools'

    class Meta:
        model = DevToolsEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR + ['entry_type', 'version']


class AINewsEntryV1Serializer(BaseEntrySerializer):
    entry_type_name = 'ai'

    class Meta:
        model = AINewsEntry
        fields = BaseEntrySerializer.ORTAK_ALANLAR
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_filters -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 4 tests`, `OK`

- [ ] **Step 5: Commit**

```bash
git add news/api_v1/serializers.py news/tests/test_filters.py
git commit -m "$(cat <<'MSG'
feat: v1 serializer'lari — acik alan listesi ve normalize siddet

Alti bolum icin ortak BaseEntrySerializer ve alt siniflari. Alanlar tek
tek yaziliyor; fields='__all__' kullanilmiyor, boylece modele alan
eklemek dis sozlesmeyi kirmiyor.

Dil varyantlari ic ice veriliyor (title.original / title.tr); tuketici
title.tr || title.original ile Ingilizceye dusebiliyor. CVE siddeti
Turkce etiketten makine dostu koda (critical/high/medium/low)
cevriliyor; bilinmeyen siddette kod None doner.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: `DeltaListAPIView` ve alti koleksiyon

**Files:**
- Modify: `news/api_v1/views.py`, `news/api_v1/urls.py`
- Test: `news/tests/test_cursor.py` (delta davranisi eklenir)

**Interfaces:**
- Consumes: `V1APIView` (Task 4), `cursor.encode_cursor/decode_cursor/apply_cursor` (Task 3), serializer'lar (Task 5)
- Produces:
  - `DeltaListAPIView(V1APIView)` — sinif nitelikleri `model`, `serializer_class`, `default_limit = 100`, `max_limit = 500`; genisletme noktasi `apply_filters(self, queryset, params) -> QuerySet` (Task 8 doldurur)
  - Alti alt sinif: `NewsDeltaView`, `CVEDeltaView`, `KubernetesDeltaView`, `SREDeltaView`, `DevToolsDeltaView`, `AIDeltaView`
  - Zarf: `{"results": [...], "next_cursor": str|None, "has_more": bool, "count": int}`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_cursor.py` sonuna ekle:

```python
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


class DeltaAkisiTests(TestCase):
    """Delta akisi hicbir kaydi atlamamali ve tekrar etmemeli."""

    def setUp(self):
        kullanici = User.objects.create_user('delta-test', password='parola-yok-test')
        self.baslik = {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=kullanici).key}'}
        for i in range(1, 8):
            AINewsEntry.objects.create(
                source='Test', original_title=f'Baslik {i}', original_description='X',
                link=f'https://ornek.test/delta/{i}', published_date=date(2026, 9, 12),
            )

    def _sayfala(self, limit):
        """Imleci takip ederek tum sayfalari gezer, gorulen id listesini dondurur."""
        gorulen, imlec = [], None
        for _ in range(20):  # sonsuz donguye karsi emniyet
            yol = f'/api/v1/ai/?limit={limit}'
            if imlec:
                yol += f'&since_cursor={imlec}'
            govde = self.client.get(yol, **self.baslik).json()
            gorulen += [k['id'] for k in govde['results']]
            imlec = govde['next_cursor']
            if not govde['has_more']:
                return gorulen
        self.fail('Sayfalama bitmedi')

    def test_tum_kayitlar_tam_bir_kez_gelir(self):
        gorulen = self._sayfala(limit=3)
        beklenen = list(AINewsEntry.objects.order_by('updated_at', 'id').values_list('id', flat=True))
        self.assertEqual(gorulen, beklenen)
        self.assertEqual(len(gorulen), len(set(gorulen)), 'Ayni kayit birden fazla geldi')

    def test_sayfalama_sirasinda_eklenen_kayit_atlanmaz(self):
        """Beat sayfalama ortasinda yazarsa yeni kayit akisin sonuna eklenir."""
        ilk = self.client.get('/api/v1/ai/?limit=3', **self.baslik).json()
        AINewsEntry.objects.create(
            source='Test', original_title='Sonradan', original_description='X',
            link='https://ornek.test/delta/sonradan', published_date=date(2026, 9, 12),
        )
        gorulen = [k['id'] for k in ilk['results']]
        imlec = ilk['next_cursor']
        while True:
            govde = self.client.get(f'/api/v1/ai/?limit=3&since_cursor={imlec}', **self.baslik).json()
            gorulen += [k['id'] for k in govde['results']]
            imlec = govde['next_cursor']
            if not govde['has_more']:
                break
        self.assertEqual(len(gorulen), 8)
        self.assertEqual(len(gorulen), len(set(gorulen)))

    def test_bos_sayfada_imlec_geri_doner(self):
        """Sonuc bos olsa bile tuketicinin saklayacak bir degeri olmali."""
        tumu = self.client.get('/api/v1/ai/?limit=100', **self.baslik).json()
        imlec = tumu['next_cursor']
        bos = self.client.get(f'/api/v1/ai/?since_cursor={imlec}', **self.baslik).json()
        self.assertEqual(bos['results'], [])
        self.assertFalse(bos['has_more'])
        self.assertEqual(bos['next_cursor'], imlec)

    def test_count_sayfadaki_kayit_sayisidir(self):
        govde = self.client.get('/api/v1/ai/?limit=3', **self.baslik).json()
        self.assertEqual(govde['count'], 3)
        self.assertEqual(len(govde['results']), 3)

    def test_bozuk_imlec_400_doner(self):
        yanit = self.client.get('/api/v1/ai/?since_cursor=bozuk!!', **self.baslik)
        self.assertEqual(yanit.status_code, 400)

    def test_since_ile_baslangic(self):
        from datetime import timedelta

        from django.utils import timezone
        yarin = (timezone.now() + timedelta(days=1)).date().isoformat()
        govde = self.client.get(f'/api/v1/ai/?since={yarin}', **self.baslik).json()
        self.assertEqual(govde['results'], [])

    def test_since_cursor_since_parametresini_ezer(self):
        """Ikisi birden verilirse since_cursor kazanir (spec 4.1)."""
        from datetime import timedelta

        from django.utils import timezone
        tumu = self.client.get('/api/v1/ai/?limit=100', **self.baslik).json()
        imlec = tumu['next_cursor']
        dun = (timezone.now() - timedelta(days=1)).date().isoformat()
        govde = self.client.get(
            f'/api/v1/ai/?since_cursor={imlec}&since={dun}', **self.baslik).json()
        self.assertEqual(govde['results'], [],
                         'since_cursor yok sayilip since uygulanmis')

    def test_alti_bolum_de_yanit_verir(self):
        for bolum in ['news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai']:
            with self.subTest(bolum=bolum):
                yanit = self.client.get(f'/api/v1/{bolum}/', **self.baslik)
                self.assertEqual(yanit.status_code, 200)
                self.assertIn('next_cursor', yanit.json())
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_cursor -v 2 2>&1 | tail -20`
Expected: FAIL — `/api/v1/ai/` icin 404.

- [ ] **Step 3: `DeltaListAPIView` ve alt siniflari yaz**

`news/api_v1/views.py` — mevcut import satirlarini su sekilde genislet ve dosyanin sonuna yeni siniflari ekle:

```python
"""v1 entegrasyon uc noktalari.

Mevcut /api/* uc noktalari frontend'e hizmet eder ve degistirilmez. Buradaki
uc noktalar dis tuketici uygulamalar icindir: token ister, cache'e bakmaz,
her zaman (updated_at, id) sirasinda doner.
"""
from django.utils.dateparse import parse_date
from rest_framework import status
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

from .cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
from .serializers import (
    AINewsEntryV1Serializer, CVEEntryV1Serializer, DevToolsEntryV1Serializer,
    KubernetesEntryV1Serializer, NewsArticleV1Serializer, SREEntryV1Serializer,
)


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


def _hata(kod: str, mesaj: str, http_durum: int):
    """Tek bicim hata yaniti uretir."""
    return Response({'error': {'code': kod, 'message': mesaj}}, status=http_durum)


class DeltaListAPIView(V1APIView):
    """Imlec tabanli delta okuma uc noktalarinin ortak tabani.

    Siralama her zaman (updated_at, id) artan; bu, imlecin dogrulugu icin
    zorunludur. Bu, akis sirasidir — ekrana basma sirasi degildir.

    Bu uc noktalar Redis cache'e bakmaz: cache dolu iken parametreleri yok
    saymak filtreleri bozardi.
    """

    model = None
    serializer_class = None
    default_limit = 100
    max_limit = 500

    def get_queryset(self):
        return self.model.objects.all()

    def apply_filters(self, queryset, params):
        """Bolume ozel filtreler. Task 7'de doldurulacak; simdilik degistirmez."""
        return queryset

    def _limit_coz(self, ham):
        if ham is None:
            return self.default_limit
        try:
            deger = int(ham)
        except (TypeError, ValueError):
            raise ValueError('limit bir tam sayi olmali.')
        if deger < 1:
            raise ValueError('limit en az 1 olmali.')
        return min(deger, self.max_limit)

    def get(self, request):
        params = request.query_params

        try:
            limit = self._limit_coz(params.get('limit'))
        except ValueError as hata:
            return _hata('invalid_parameter', str(hata), status.HTTP_400_BAD_REQUEST)

        sorgu = self.get_queryset().order_by('updated_at', 'id')

        imlec = params.get('since_cursor')
        if imlec:
            try:
                moment, pk = decode_cursor(imlec)
            except InvalidCursor as hata:
                return _hata('invalid_cursor', str(hata), status.HTTP_400_BAD_REQUEST)
            sorgu = apply_cursor(sorgu, moment, pk)
        elif params.get('since'):
            gun = parse_date(params['since'])
            if gun is None:
                return _hata('invalid_parameter',
                             'since YYYY-MM-DD biciminde olmali.',
                             status.HTTP_400_BAD_REQUEST)
            sorgu = sorgu.filter(updated_at__date__gte=gun)

        try:
            sorgu = self.apply_filters(sorgu, params)
        except ValueError as hata:
            return _hata('invalid_parameter', str(hata), status.HTTP_400_BAD_REQUEST)

        # limit + 1 cekilir: fazladan gelen satir "daha var mi" sorusunu yanitlar
        satirlar = list(sorgu[:limit + 1])
        has_more = len(satirlar) > limit
        satirlar = satirlar[:limit]

        if satirlar:
            son = satirlar[-1]
            next_cursor = encode_cursor(son.updated_at, son.id)
        else:
            # Sonuc bos: gelen imlec aynen geri verilir ki tuketicinin
            # saklayacak bir degeri hep olsun. Imlec hic verilmemisse None doner.
            next_cursor = imlec or None

        return Response({
            'results': self.serializer_class(satirlar, many=True).data,
            'next_cursor': next_cursor,
            'has_more': has_more,
            'count': len(satirlar),
        })


class NewsDeltaView(DeltaListAPIView):
    model = NewsArticle
    serializer_class = NewsArticleV1Serializer


class CVEDeltaView(DeltaListAPIView):
    model = CVEEntry
    serializer_class = CVEEntryV1Serializer


class KubernetesDeltaView(DeltaListAPIView):
    model = KubernetesEntry
    serializer_class = KubernetesEntryV1Serializer


class SREDeltaView(DeltaListAPIView):
    model = SREEntry
    serializer_class = SREEntryV1Serializer


class DevToolsDeltaView(DeltaListAPIView):
    model = DevToolsEntry
    serializer_class = DevToolsEntryV1Serializer


class AIDeltaView(DeltaListAPIView):
    model = AINewsEntry
    serializer_class = AINewsEntryV1Serializer
```

`news/api_v1/urls.py` tam hali:

```python
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
```

- [ ] **Step 4: Testlerin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_cursor news.tests.test_auth -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`. Task 4'te duşen `TokenAuthTests` testleri artik gecer.

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add news/api_v1/views.py news/api_v1/urls.py news/tests/test_cursor.py
git commit -m "$(cat <<'MSG'
feat: DeltaListAPIView ve alti v1 okuma uc noktasi

Ortak taban sinifi, imleci cozup keyset filtresini uyguluyor ve
{results, next_cursor, has_more, count} zarfini donduruyor. limit+1
cekilerek has_more hesaplaniyor; sonuc bos ise gelen imlec aynen geri
veriliyor.

Alti bolum (news, cve, kubernetes, sre, devtools, ai) ayni tabandan
turuyor. Bu uc noktalar Redis cache'e bakmiyor.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 7: Filtreler

**Files:**
- Create: `news/api_v1/filters.py`
- Modify: `news/api_v1/views.py` (alt siniflarda `apply_filters`)
- Test: `news/tests/test_filters.py`

**Interfaces:**
- Consumes: `SEVERITY_TR_TO_CODE`, `SEVERITY_CODE_TO_TR`, `SEVERITY_ORDER` (Task 5); `DeltaListAPIView.apply_filters` genisletme noktasi (Task 6)
- Produces:
  - `parse_bool(ham: str|None) -> bool|None` — `'true'/'1'/'yes'` → True, `'false'/'0'/'no'` → False, tanimsiz → `ValueError`
  - `parse_csv(ham: str|None) -> list[str]` — virgulle ayrilmis liste, bos ogeler atilir
  - `ortak_filtreler(queryset, params) -> QuerySet` — `source` ve `needs_translation`
  - `min_severity_tr_listesi(kod: str) -> list[str]` — `'high'` → `['Yüksek', 'Kritik']`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_filters.py` sonuna ekle:

```python
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token

from news.models import DevToolsEntry, KubernetesEntry


class FiltreTests(TestCase):
    """Filtreler tuketicinin gereksiz veri cekmesini onler."""

    def setUp(self):
        kullanici = User.objects.create_user('filtre-test', password='parola-yok-test')
        self.baslik = {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=kullanici).key}'}
        for i, (siddet, kaynak) in enumerate([
            ('Kritik', 'NVD'), ('Yüksek', 'NVD'), ('Orta', 'CISA'),
            ('Düşük', 'CISA'), ('Bilinmiyor', 'NVD'),
        ], start=1):
            CVEEntry.objects.create(
                cve_id=f'CVE-2026-20{i:02d}', source=kaynak, original_title='X',
                original_description='Body', severity=siddet,
                published_date=date(2026, 9, 12), link=f'https://ornek.test/cve/20{i:02d}',
            )

    def _kodlar(self, sorgu):
        govde = self.client.get(f'/api/v1/cve/?{sorgu}', **self.baslik).json()
        return sorted(k['severity']['code'] or 'none' for k in govde['results'])

    def test_min_severity_high_kritik_ve_yuksek_getirir(self):
        self.assertEqual(self._kodlar('min_severity=high'), ['critical', 'high'])

    def test_min_severity_low_bilinmeyeni_disarida_birakir(self):
        """Bilinmeyen siddet siralamaya girmez; sessizce dahil edilmemeli."""
        self.assertEqual(self._kodlar('min_severity=low'), ['critical', 'high', 'low', 'medium'])

    def test_severity_tam_liste(self):
        self.assertEqual(self._kodlar('severity=critical,low'), ['critical', 'low'])

    def test_gecersiz_severity_400(self):
        yanit = self.client.get('/api/v1/cve/?min_severity=cok-kotu', **self.baslik)
        self.assertEqual(yanit.status_code, 400)
        self.assertEqual(yanit.json()['error']['code'], 'invalid_parameter')

    def test_source_filtresi(self):
        govde = self.client.get('/api/v1/cve/?source=CISA', **self.baslik).json()
        self.assertEqual({k['source'] for k in govde['results']}, {'CISA'})

    def test_needs_translation_filtresi(self):
        CVEEntry.objects.filter(cve_id='CVE-2026-2001').update(needs_translation=True)
        govde = self.client.get('/api/v1/cve/?needs_translation=true', **self.baslik).json()
        self.assertEqual([k['cve_id'] for k in govde['results']], ['CVE-2026-2001'])

    def test_limit_tavani_uygulanir(self):
        govde = self.client.get('/api/v1/cve/?limit=9999', **self.baslik).json()
        self.assertLessEqual(govde['count'], 500)

    def test_gecersiz_limit_400(self):
        yanit = self.client.get('/api/v1/cve/?limit=sifir', **self.baslik)
        self.assertEqual(yanit.status_code, 400)

    def test_kubernetes_kategori_filtresi(self):
        for i, kategori in enumerate(['security', 'release', 'blog'], start=1):
            KubernetesEntry.objects.create(
                source='Kubernetes Blog', original_title='X', original_description='B',
                link=f'https://ornek.test/k8s/{i}', published_date=date(2026, 9, 12),
                category=kategori,
            )
        govde = self.client.get('/api/v1/kubernetes/?category=security', **self.baslik).json()
        self.assertEqual([k['category'] for k in govde['results']], ['security'])

    def test_devtools_entry_type_filtresi(self):
        for i, tur in enumerate(['release', 'blog'], start=1):
            DevToolsEntry.objects.create(
                source='Terraform', original_title='X', original_description='B',
                link=f'https://ornek.test/dt/{i}', published_date=date(2026, 9, 12),
                entry_type=tur,
            )
        govde = self.client.get('/api/v1/devtools/?entry_type=release', **self.baslik).json()
        self.assertEqual([k['entry_type'] for k in govde['results']], ['release'])
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_filters -v 2 2>&1 | tail -20`
Expected: FAIL — filtreler yok sayildigi icin `min_severity=high` bes kaydi da donduruyor.

- [ ] **Step 3: `filters.py` yaz**

`news/api_v1/filters.py`:

```python
"""v1 query parametrelerini ayristirma ve queryset'e uygulama.

Gecersiz parametre sessizce yok sayilmaz; ValueError firlatilir ve view bunu
400 invalid_parameter yanitina cevirir. Sessiz yok sayma, tuketicinin yanlis
veri aldigini fark etmemesine yol acar.
"""
from .serializers import SEVERITY_CODE_TO_TR, SEVERITY_ORDER

DOGRU_DEGERLER = {'true', '1', 'yes'}
YANLIS_DEGERLER = {'false', '0', 'no'}


def parse_bool(ham):
    """'true'/'false' benzeri degerleri bool'a cevirir. Verilmemisse None doner."""
    if ham is None:
        return None
    kucuk = ham.strip().lower()
    if kucuk in DOGRU_DEGERLER:
        return True
    if kucuk in YANLIS_DEGERLER:
        return False
    raise ValueError(f"Beklenen true/false degeri, alinan: '{ham}'")


def parse_csv(ham):
    """Virgulle ayrilmis listeyi ayristirir; bos ogeler atilir."""
    if not ham:
        return []
    return [parca.strip() for parca in ham.split(',') if parca.strip()]


def min_severity_tr_listesi(kod: str):
    """'high' -> ['Yüksek', 'Kritik'] (veritabanindaki Turkce etiketler).

    Bilinmeyen siddet ('Bilinmiyor') siralamada yer almadigi icin sonuca
    dahil edilmez; siddeti belirsiz bir kaydi 'yuksek ve uzeri' saymak yanlis
    olur.
    """
    kucuk = kod.strip().lower()
    if kucuk not in SEVERITY_ORDER:
        gecerli = ', '.join(SEVERITY_ORDER)
        raise ValueError(f"min_severity su degerlerden biri olmali: {gecerli}")
    esik = SEVERITY_ORDER.index(kucuk)
    return [SEVERITY_CODE_TO_TR[k] for k in SEVERITY_ORDER[esik:]]


def severity_tr_listesi(ham: str):
    """'critical,low' -> ['Kritik', 'Düşük']."""
    kodlar = parse_csv(ham)
    bilinmeyen = [k for k in kodlar if k.lower() not in SEVERITY_ORDER]
    if bilinmeyen:
        gecerli = ', '.join(SEVERITY_ORDER)
        raise ValueError(f"Bilinmeyen severity degeri: {', '.join(bilinmeyen)}. "
                         f"Gecerli degerler: {gecerli}")
    return [SEVERITY_CODE_TO_TR[k.lower()] for k in kodlar]


def ortak_filtreler(queryset, params):
    """Alti bolumde de gecerli olan filtreler."""
    kaynaklar = parse_csv(params.get('source'))
    if kaynaklar:
        queryset = queryset.filter(source__in=kaynaklar)

    bekleyen = parse_bool(params.get('needs_translation'))
    if bekleyen is not None:
        queryset = queryset.filter(needs_translation=bekleyen)

    return queryset
```

- [ ] **Step 4: View'lara filtreleri bagla**

`news/api_v1/views.py` — import blokuna ekle:

```python
from .filters import (
    min_severity_tr_listesi, ortak_filtreler, parse_csv, severity_tr_listesi,
)
```

`DeltaListAPIView.apply_filters` govdesini degistir:

```python
    def apply_filters(self, queryset, params):
        """Alti bolumde ortak filtreler. Alt siniflar super() cagirip genisletir."""
        return ortak_filtreler(queryset, params)
```

Uc alt sinifi genislet:

```python
class CVEDeltaView(DeltaListAPIView):
    model = CVEEntry
    serializer_class = CVEEntryV1Serializer

    def apply_filters(self, queryset, params):
        queryset = super().apply_filters(queryset, params)
        if params.get('min_severity'):
            queryset = queryset.filter(severity__in=min_severity_tr_listesi(params['min_severity']))
        if params.get('severity'):
            queryset = queryset.filter(severity__in=severity_tr_listesi(params['severity']))
        return queryset


class KubernetesDeltaView(DeltaListAPIView):
    model = KubernetesEntry
    serializer_class = KubernetesEntryV1Serializer

    def apply_filters(self, queryset, params):
        queryset = super().apply_filters(queryset, params)
        kategoriler = parse_csv(params.get('category'))
        if kategoriler:
            queryset = queryset.filter(category__in=kategoriler)
        return queryset


class DevToolsDeltaView(DeltaListAPIView):
    model = DevToolsEntry
    serializer_class = DevToolsEntryV1Serializer

    def apply_filters(self, queryset, params):
        queryset = super().apply_filters(queryset, params)
        turler = parse_csv(params.get('entry_type'))
        if turler:
            queryset = queryset.filter(entry_type__in=turler)
        return queryset
```

- [ ] **Step 5: Testlerin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_filters -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 14 tests`, `OK`

- [ ] **Step 6: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add news/api_v1/filters.py news/api_v1/views.py news/tests/test_filters.py
git commit -m "$(cat <<'MSG'
feat: v1 filtreleri — source, needs_translation, severity, category, entry_type

Ortak filtreler taban sinifta; CVE, Kubernetes ve DevTools kendi
filtrelerini super() uzerine ekliyor. min_severity siralamaya gore
genisletiliyor (high -> Yuksek + Kritik); siddeti bilinmeyen kayitlar
esik filtresine dahil edilmiyor.

Gecersiz parametre sessizce yok sayilmiyor, 400 invalid_parameter
donuyor.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 8: Hata sozlesmesi ve throttle dogrulamasi

Onceki task'lar hata govdesini `_hata()` ile uretti; DRF'in kendi urettigi hatalar (401, 429, 405) hala DRF bicimindedir. Bu task hepsini tek bicime getirir.

**Files:**
- Modify: `news/api_v1/views.py` (`V1APIView.handle_exception`)
- Test: `news/tests/test_auth.py`

**Interfaces:**
- Consumes: `V1APIView` (Task 4), `_hata` (Task 6)
- Produces: Tum v1 hata yanitlari `{"error": {"code": ..., "message": ...}}` bicimindedir. Kodlar: `unauthorized` (401), `forbidden` (403), `invalid_cursor` (400), `invalid_parameter` (400), `throttled` (429, `Retry-After` basligiyla), `not_found` (404), `method_not_allowed` (405), `internal` (500).

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_auth.py` sonuna ekle:

```python
from unittest import mock


class HataBicimiTests(TestCase):
    """Tum v1 hatalari tek bicimde donmeli; tuketici tek bir ayristirici yazsin."""

    def setUp(self):
        kullanici = User.objects.create_user('hata-test', password='parola-yok-test')
        self.baslik = {'HTTP_AUTHORIZATION': f'Token {Token.objects.create(user=kullanici).key}'}

    def test_401_tek_bicimde_doner(self):
        govde = self.client.get('/api/v1/ai/').json()
        self.assertEqual(govde['error']['code'], 'unauthorized')
        self.assertIn('message', govde['error'])

    def test_405_tek_bicimde_doner(self):
        yanit = self.client.post('/api/v1/ai/', **self.baslik)
        self.assertEqual(yanit.status_code, 405)
        self.assertEqual(yanit.json()['error']['code'], 'method_not_allowed')

    def test_429_retry_after_basligi_tasir(self):
        """Hiz siniri asildiginda tuketici ne kadar bekleyecegini bilmeli."""
        with mock.patch('rest_framework.throttling.ScopedRateThrottle.allow_request',
                        return_value=False), \
             mock.patch('rest_framework.throttling.ScopedRateThrottle.wait',
                        return_value=42):
            yanit = self.client.get('/api/v1/ai/', **self.baslik)
        self.assertEqual(yanit.status_code, 429)
        self.assertEqual(yanit.json()['error']['code'], 'throttled')
        self.assertEqual(yanit['Retry-After'], '42')

    def test_health_hata_bicimine_karismaz(self):
        yanit = self.client.get('/api/v1/health/')
        self.assertEqual(yanit.status_code, 200)
        self.assertNotIn('error', yanit.json())
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_auth -v 2 2>&1 | tail -25`
Expected: FAIL — 401 yaniti `{"detail": "..."}` bicimindedir, `error` anahtari yoktur.

- [ ] **Step 3: `handle_exception` ekle**

`news/api_v1/views.py` — `_hata` fonksiyonunu `V1APIView`'dan **once** tasi (siniflar ona basvuruyor), sonra `V1APIView`'i su hale getir:

```python
def _hata(kod: str, mesaj: str, http_durum: int):
    """Tek bicim hata yaniti uretir."""
    return Response({'error': {'code': kod, 'message': mesaj}}, status=http_durum)


# DRF istisnalarini sozlesmedeki hata kodlarina esler.
DRF_DURUM_KODLARI = {
    400: 'invalid_parameter',
    401: 'unauthorized',
    403: 'forbidden',
    404: 'not_found',
    405: 'method_not_allowed',
    429: 'throttled',
}


class V1APIView(APIView):
    """v1 uc noktalarinin ortak tabani: token dogrulamasi, hiz siniri, hata bicimi."""

    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'v1_read'

    def handle_exception(self, exc):
        """DRF'in kendi hata bicimini sozlesmedeki tek bicime cevirir.

        Bu yalnizca v1 view'larini etkiler; mevcut /api/* uc noktalari kendi
        bicimlerini korur.
        """
        yanit = super().handle_exception(exc)
        kod = DRF_DURUM_KODLARI.get(yanit.status_code, 'internal')

        ayrinti = yanit.data
        if isinstance(ayrinti, dict):
            mesaj = str(ayrinti.get('detail', ayrinti))
        elif isinstance(ayrinti, list):
            mesaj = '; '.join(str(oge) for oge in ayrinti)
        else:
            mesaj = str(ayrinti)

        yanit.data = {'error': {'code': kod, 'message': mesaj}}
        return yanit
```

`Retry-After` basligini DRF `Throttled` istisnasi icin kendisi ekler; ek kod gerekmez.

- [ ] **Step 4: Testlerin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_auth -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add news/api_v1/views.py news/tests/test_auth.py
git commit -m "$(cat <<'MSG'
feat: v1 hatalarini tek bicime getir

DRF'in {"detail": ...} bicimi yerine sozlesmedeki
{"error": {"code": ..., "message": ...}} bicimi donuyor. Esleme
V1APIView.handle_exception icinde; yalnizca v1 view'larini etkiliyor,
mevcut /api/* uc noktalari kendi bicimlerini koruyor.

429 yanitlari DRF'in ekledigi Retry-After basligini tasiyor.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 9: Canli dogrulama ve A1 kapanisi

Testler gecti; simdi gercek veriyle calistigini gorelim. Bu task kod yazmaz, kanit toplar.

**Files:**
- Degistirilmez; yalnizca dogrulama

**Interfaces:**
- Consumes: Task 1-8
- Produces: A1'in canlida calistigini gosteren cikti. A2 planinin baslangic noktasi.

- [ ] **Step 1: Entegrasyon token'i uret**

```bash
docker compose exec -T teknoloji-api python - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybernews.settings')
django.setup()
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
kullanici, yeni_kullanici = User.objects.get_or_create(username='entegrasyon',
                                                      defaults={'is_active': True})
if yeni_kullanici:
    kullanici.set_unusable_password()   # yalnizca API token'i tasir, giris yapamaz
    kullanici.save()
token, olusturuldu = Token.objects.get_or_create(user=kullanici)
print('token:', token.key, '| yeni:' if olusturuldu else '| mevcut:', kullanici.username)
PY
```

Not: bu kullanici parolasizdir ve yalnizca API token'i tasir; Django admin'e giris yapamaz. Token'i bir yere kaydet, sonraki adimlarda `$TOKEN` olarak kullanilacak.

- [ ] **Step 2: Health'i dogrula**

```bash
curl -s http://localhost:8000/api/v1/health/
```
Expected: `{"status":"ok","version":"v1"}`

- [ ] **Step 3: Tokensiz erisimin reddedildigini dogrula**

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/v1/cve/
```
Expected: `401`

- [ ] **Step 4: Gercek CVE verisiyle filtreli delta cek**

```bash
TOKEN=<Step 1'deki token>
curl -s -H "Authorization: Token $TOKEN" \
  "http://localhost:8000/api/v1/cve/?min_severity=high&limit=3" \
  | python -m json.tool | head -40
```
Expected: `results` icinde en fazla 3 kayit, hepsinin `severity.code` degeri `critical` veya `high`; `next_cursor` dolu; `has_more` muhtemelen `true` (veritabaninda 71 Kritik + 214 Yuksek var).

- [ ] **Step 5: Imlecin ilerledigini ve tekrar etmedigini dogrula**

```bash
TOKEN=<Step 1'deki token>
docker compose exec -T teknoloji-api python - <<PY
import json, urllib.request
TOKEN = "$TOKEN"

def cek(yol):
    istek = urllib.request.Request('http://localhost:8000' + yol,
                                   headers={'Authorization': 'Token ' + TOKEN})
    return json.load(urllib.request.urlopen(istek))

gorulen, imlec, tur = [], None, 0
while tur < 50:
    yol = '/api/v1/cve/?limit=100' + (f'&since_cursor={imlec}' if imlec else '')
    govde = cek(yol)
    gorulen += [k['id'] for k in govde['results']]
    imlec = govde['next_cursor']
    tur += 1
    if not govde['has_more']:
        break

print('tur sayisi      :', tur)
print('gelen kayit     :', len(gorulen))
print('benzersiz kayit :', len(set(gorulen)))
print('tekrar var mi   :', 'HAYIR' if len(gorulen) == len(set(gorulen)) else 'EVET — HATA')
PY
```
Expected: `gelen kayit` ile `benzersiz kayit` esit, `tekrar var mi: HAYIR`. Toplam sayi `CVEEntry.objects.count()` ile ayni olmali.

- [ ] **Step 6: Frontend'in bozulmadigini dogrula**

```bash
curl -s -o /dev/null -w "eski /api/cve/ -> %{http_code}\n" http://localhost:8000/api/cve/
curl -s -o /dev/null -w "frontend      -> %{http_code}\n" http://localhost:3000/
```
Expected: ikisi de `200`. Eski uc nokta hala tokensiz calisiyor olmali — kirilmadigi bu demek.

- [ ] **Step 7: Tum test paketini son kez kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 8: Dali push et**

```bash
git push -u origin feat/entegrasyon-api-v1-a1
```

---

## A1 Bitis Kriterleri

- [ ] Alti bolumun tamami `/api/v1/<bolum>/` altinda token ile okunabiliyor
- [ ] Imlec takip edilerek tum kayitlar tam bir kez geliyor (Task 9 Step 5 kaniti)
- [ ] Tokensiz istek 401, bozuk imlec 400, gecersiz parametre 400 donuyor ve hepsi tek bicimde
- [ ] `health` tokensiz 200 donuyor
- [ ] Mevcut `/api/*` uc noktalari ve frontend calisiyor
- [ ] Test paketi yesil

## A1 Sonrasi

Sonraki plan **A2**: `POST /api/v1/{bolum}/refresh/`, `POST /api/v1/refresh/`, `GET /api/v1/jobs/{id}/`, Redis bolum kilidi ve 15 dakikalik soguma. Spec bolum 8.

A2 planina baslarken bu planin `DeltaListAPIView` ve `V1APIView` arayuzleri hazir kabul edilir.
