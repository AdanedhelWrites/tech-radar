# Entegrasyon API v1 — A2 Uygulama Plani (Manuel Tetikleme)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dis tuketicinin 6 saatlik Beat takvimini beklemeden bir bolumu (veya hepsini) yeniden cektirebilmesi ve isin durumunu izleyebilmesi — kaynak sitelere ve ceviri kotasina zarar vermeden.

**Architecture:** Yeni `news/api_v1/refresh.py` modulu Redis uzerinde uc anahtarla calisir: bolum kilidi, bolum sogumasi ve job kaydi. Kilit, is bitince Celery `task_postrun` sinyaliyle birakilir. Uc yeni uc nokta (`POST /api/v1/<bolum>/refresh/`, `POST /api/v1/refresh/`, `GET /api/v1/jobs/<id>/`) A1'deki `V1APIView` tabanindan turer. Once iki altyapi hatasi duzeltilir: Celery uygulamasi Django surecinde hic yuklenmiyor ve view testleri canli Redis'i paylasiyor.

**Tech Stack:** Django 4.2.7, DRF 3.14.0, Celery 5.3.4, redis-py 5.0.1 (Redis sunucusu 7.4.10), django-redis 5.4.0. **Yeni pip bagimliligi eklenmez.**

**Spec:** `docs/superpowers/specs/2026-09-12-entegrasyon-api-v1-design.md` — ozellikle bolum 8. Bu planin spec'ten ayrildigi uc nokta asagida "Spec'e gore netlestirmeler" altinda.

**Onceki plan:** `docs/superpowers/plans/2026-09-12-entegrasyon-api-v1-a1.md` (tamamlandi, canlida dogrulandi).

## Global Constraints

- **Testler hicbir zaman gercek Celery isi kuyruga atmaz.** Canli worker ayni broker'i dinliyor; kuyruga dusen is gercek kazima ve Google cevirisi baslatir. `trigger()` veya refresh view'larina dokunan her test `RefreshTestMixin` kullanir (alti task'in `apply_async`'ini mock'lar).
- **View testleri `V1TestCase`'ten turer** (Task 2). Bu taban locmem cache ve WhiteNoise'suz middleware kullanir. Neden: throttle sayaclari aksi halde canli Redis'e yazilir; test veritabani kullanici id'lerini 1'den baslattigi icin canli kullanicilarla (id 1: `adanedhel`, id 2: `entegrasyon`) cakisir ve onlari kilitleyebilir.
- **Redis kullanan testler benzersiz onek kullanir ve kendi anahtarlarini temizler.** `FLUSHDB`/`FLUSHALL` kesinlikle kullanilmaz — Redis db 0 canli cache'tir.
- **`news/tasks.py` bu planda degistirilmez.** A3 o dosyayi degistirecek.
- **`REST_FRAMEWORK` icindeki mevcut anahtarlar degistirilmez.** `v1_refresh: '12/hour'` A1'de zaten tanimli.
- **Mevcut `/api/*` uc noktalari ve frontend dokunulmaz.**
- **Kod yorumlari ve kullanici mesajlari Turkce, aksansiz.**
- **Testler konteyner icinde kosar:** `docker compose exec -T teknoloji-api python manage.py test ...`
- **Her task kendi commit'ini atar**; mesajlar Turkce, aksansiz, `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` ile biter (uygulayan model neyse o yazilir).
- **Calisma dali:** `feat/entegrasyon-api-v1-a2`. A1 `main`'e merge edildiyse `main`'den, edilmediyse `feat/entegrasyon-api-v1-a1`'den acilir.

## Ortam Notlari (yeni bir context icin)

| Konu | Deger |
|---|---|
| Proje koku / git koku | `cybersecurity_news/` |
| Konteynerlar | `teknoloji-api` (gunicorn, 4 worker), `teknoloji-worker` (celery worker), `teknoloji-scheduler` (celery beat), `teknoloji-redis` |
| **Kod yeniden yukleme** | **Yok.** Kod bind mount ile gorunur (`./:/app`) ama gunicorn ve celery surecleri modulleri bir kez yukler. Canli dogrulamadan once `docker compose restart teknoloji-api teknoloji-worker teknoloji-scheduler` gerekir. |
| Redis | `REDIS_URL=redis://teknoloji-redis:6379/0` (cache + Celery sonuc backend'i), broker `.../1` |
| Mevcut test sayisi | 52 (hepsi gecer; ~50 sn — Task 2 sonrasi belirgin kisalir) |
| Canli kullanicilar | id 1 `adanedhel` (superuser), id 2 `entegrasyon` (parolasiz, API token'li) |

### 2026-09-12 dersi: migration sonrasi worker yeniden baslatilmali

A1'in migration'i 14:20 UTC'de uygulandi ama worker 17:50'ye kadar yeniden baslatilmadi. Bellekte `updated_at` alani olmayan eski model sinifi kaldi; 15:10'daki CVE cekimi yeni kayit eklerken `NOT NULL constraint failed: news_cveentry.updated_at` hatasiyla patladi. Yeniden baslatmadan sonra ayni cekim 177 kaydi sorunsuz ekledi. **Bu planda migration yok, ama Task 1 ayar degistiriyor ve Task 5 yeni bir sinyal ekliyor — ikisi de yeniden baslatma olmadan canliya yansimaz.**

## A1 Sonrasi Tespit Edilen Iki Altyapi Hatasi

**H3 — Celery uygulamasi Django surecinde yuklenmiyor.** `cybernews/__init__.py` bos; `cybernews/celery.py` hicbir yerden import edilmiyor. Gunicorn'un yukledigi yolda (`cybernews.wsgi`) task'lar Celery'nin `default` uygulamasina bagli, sonuc backend'i `DisabledBackend`. Mevcut `.delay()` cagrilari yalnizca Celery'nin broker adresini `CELERY_BROKER_URL` ortam degiskeninden kendiliginden okumasi sayesinde calisiyor. Sonuc: `AsyncResult` API surecinde hicbir zaman durum okuyamaz — spec 8.3'teki "sonuc backend'i hazir, ek altyapi gerektirmez" varsayimi yanlisti. Ayrica `CELERY_TASK_TRACK_STARTED` tanimsiz, yani `started` durumu hic gorunmez.

**H4 — View testleri canli Redis'i kullaniyor ve yavas.** A1 view testleri cache override etmiyor: throttle sayaclari canli Redis'e yaziliyor. Her test ~1.9 sn suruyor; profil sebebin WhiteNoise middleware'inin her test istemcisinde `staticfiles/` altindaki 2019 dosyayi taramasi oldugunu gosterdi (bind mount uzerinden 1.8 sn). Olcum: `FiltreTests` sinifi 23.2 sn → WhiteNoise'suz + locmem ile 1.7 sn, testler yine gecti.

## Spec'e Gore Netlestirmeler

1. **`already_running` govdesi** `section` ve `status_url` alanlarini da icerir (spec 8.2 yalnizca `job_id` ve `status` gosteriyordu). Tuketici calisan isi de izleyebilsin diye.
2. **`POST /api/v1/refresh/` her zaman `202` doner**, govdede `started`, `already_running`, `skipped` listeleri bulunur. Hicbir bolum baslamasa bile 202'dir; tuketici listelere bakar.
3. **Job `failure` iki durumda doner:** Celery isi `FAILURE` ise, **veya** is `SUCCESS` olup `{'success': False, 'error': ...}` dondurduyse. `news/tasks.py`'deki tum task'lar istisnalari yakalayip bu bicimde dondurur; Celery acisindan basarili gorunen bu isler tuketici acisindan basarisizdir. `{'success': False, 'count': 0}` (hata alani yok) ise basari sayilir — "yeni kayit yok" demektir.

## Dosya Yapisi

**Olusturulacak:**

| Dosya | Sorumluluk |
|---|---|
| `news/api_v1/refresh.py` | `RefreshGate` (Redis kilit/soguma/job kaydi), `SECTIONS`, `section_tasks()`, `TriggerResult`, `trigger()`, `get_gate()` |
| `news/api_v1/job_signals.py` | `task_postrun` alicisi: is bitince kilidi birakir |
| `news/apps.py` | `NewsConfig.ready()` sinyal modulunu yukler |
| `news/tests/base.py` | `V1TestCase`, `RefreshTestMixin`, `test_redis_client()` |
| `news/tests/test_altyapi.py` | Celery uygulamasi ve test izolasyonu testleri |
| `news/tests/test_refresh.py` | Gate, trigger, sinyal ve iki refresh uc noktasi |
| `news/tests/test_jobs.py` | Job durum uc noktasi |

**Degistirilecek:**

| Dosya | Degisiklik |
|---|---|
| `cybernews/__init__.py` | Celery uygulamasini yukle |
| `cybernews/settings.py` | `CELERY_TASK_TRACK_STARTED = True` |
| `news/api_v1/views.py` | `RefreshView`, `RefreshAllView`, `JobView` |
| `news/api_v1/urls.py` | Uc yeni yol |
| `news/tests/test_auth.py`, `test_cursor.py`, `test_filters.py` | View test siniflari `V1TestCase`'e gecer |

---

### Task 1: Celery uygulamasini Django surecinde yukle

**Files:**
- Modify: `cybernews/__init__.py`, `cybernews/settings.py`
- Create: `news/tests/test_altyapi.py`

**Interfaces:**
- Consumes: yok
- Produces: `from cybernews.celery import app as celery_app` her Django surecinde gecerli; `news.tasks` icindeki tum task'lar `cybernews` uygulamasina bagli, sonuc backend'i Redis, `task_track_started=True`.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_altyapi.py`:

```python
"""Altyapi testleri: Celery uygulamasinin yuklenmesi ve test izolasyonu."""
from django.test import SimpleTestCase


class CeleryUygulamasiTests(SimpleTestCase):
    """Django sureci proje Celery uygulamasini yuklemeli.

    Aksi halde task'lar Celery'nin 'default' uygulamasina baglanir ve sonuc
    backend'i devre disi kalir: AsyncResult hicbir isin durumunu okuyamaz.
    """

    def test_tasklar_proje_uygulamasina_bagli(self):
        from news.tasks import fetch_cve_task
        self.assertEqual(fetch_cve_task.app.main, 'cybernews')

    def test_sonuc_backendi_redis(self):
        from news.tasks import fetch_cve_task
        self.assertEqual(type(fetch_cve_task.app.backend).__name__, 'RedisBackend')

    def test_started_durumu_izleniyor(self):
        from news.tasks import fetch_cve_task
        self.assertTrue(fetch_cve_task.app.conf.task_track_started)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_altyapi -v 2 2>&1 | tail -20`
Expected: uc test de FAIL — `'default' != 'cybernews'`, `'DisabledBackend' != 'RedisBackend'`, `task_track_started` False.

- [ ] **Step 3: Uygulamayi yukle ve ayari ekle**

`cybernews/__init__.py` tam hali:

```python
# Cybernews Django Project

# Celery uygulamasi Django ile birlikte yuklenmeli; aksi halde task'lar Celery'nin
# 'default' uygulamasina baglanir ve sonuc backend'i devre disi kalir.
from .celery import app as celery_app

__all__ = ('celery_app',)
```

`cybernews/settings.py` — `CELERY_TIMEZONE = 'Europe/Istanbul'` satirinin hemen altina:

```python
# Worker isi aldiginda durum STARTED olur; aksi halde is bitene kadar PENDING gorunur.
# /api/v1/jobs/<id>/ uc noktasinin 'started' durumunu gosterebilmesi icin gerekli.
CELERY_TASK_TRACK_STARTED = True
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_altyapi -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 3 tests`, `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 55 tests`, `OK`

- [ ] **Step 6: Worker'in hala acildigini dogrula**

`cybernews/__init__.py` degisikligi worker'in import zincirini de etkiler. Dongusel import olmadigini kanitla:

Run: `docker compose exec -T teknoloji-worker celery -A cybernews inspect ping 2>&1 | tail -3`
Expected: `pong` iceren bir satir. (Calisan worker eski kodla cevap verir; asil kontrol Step 7.)

- [ ] **Step 7: Yeni kodla bir worker sureci baslatilabildigini dogrula**

Run: `docker compose exec -T teknoloji-worker python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings'); import django; django.setup(); from cybernews import celery_app; print(celery_app.main, type(celery_app.backend).__name__)"`
Expected: `cybernews RedisBackend`

- [ ] **Step 8: Commit**

```bash
git add cybernews/__init__.py cybernews/settings.py news/tests/test_altyapi.py
git commit -m "$(cat <<'MSG'
fix: Celery uygulamasini Django surecinde yukle

cybernews/__init__.py bostu ve cybernews/celery.py hicbir yerden import
edilmiyordu. Gunicorn surecinde task'lar Celery'nin 'default'
uygulamasina bagliydi ve sonuc backend'i DisabledBackend idi; mevcut
.delay() cagrilari yalnizca broker adresinin CELERY_BROKER_URL ortam
degiskeninden okunmasi sayesinde calisiyordu. AsyncResult bu surecte
hicbir isin durumunu okuyamazdi.

Standart Django-Celery kalibi uygulandi ve CELERY_TASK_TRACK_STARTED
acildi; boylece /api/v1/jobs/ uc noktasi 'started' durumunu gorebilecek.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: View testlerini canli Redis'ten ayir ve hizlandir

**Files:**
- Create: `news/tests/base.py`
- Modify: `news/tests/test_altyapi.py`, `news/tests/test_auth.py`, `news/tests/test_cursor.py`, `news/tests/test_filters.py`

**Interfaces:**
- Consumes: yok
- Produces:
  - `LOCMEM_CACHE: dict`, `TEST_MIDDLEWARE: list[str]`
  - `V1TestCase(TestCase)` — locmem cache + WhiteNoise'suz middleware; `setUp` cache'i temizler; `token_basligi() -> dict` yeni kullanici + token olusturup `{'HTTP_AUTHORIZATION': 'Token ...'}` doner. **Alt siniflar `setUp` yazarsa ilk satirda `super().setUp()` cagirmalidir.**
  - `test_redis_client() -> redis.Redis` — `REDIS_URL` ortam degiskeninden dogrudan istemci (locmem override altinda `django_redis` kullanilamaz)

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_altyapi.py` sonuna ekle:

```python
from django.conf import settings
from django.core.cache import caches


class TestIzolasyonuTests(SimpleTestCase):
    """View testleri canli Redis'e yazmamali ve WhiteNoise yuklememeli."""

    def test_v1_test_tabani_canli_redisi_kullanmaz(self):
        from news.tests.base import V1TestCase

        class Ornek(V1TestCase):
            def test_bos(self):
                pass

        ornek = Ornek('test_bos')
        ornek._pre_setup()
        try:
            self.assertEqual(type(caches['default']).__name__, 'LocMemCache')
            self.assertFalse(any('whitenoise' in m.lower() for m in settings.MIDDLEWARE))
        finally:
            ornek._post_teardown()
```

Not: `_pre_setup` / `_post_teardown` burada `override_settings`'in sinif uzerinde gercekten etkinlestigini dogrulamak icin kullaniliyor; `TestCase` icinde veritabani islemi baslatir, bu yuzden `SimpleTestCase` icinden cagrilmasina `databases` izni gerekir. Step 2'de `DatabaseOperationForbidden` gorursen `TestIzolasyonuTests`'e `databases = {'default'}` ekle.

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_altyapi.TestIzolasyonuTests -v 2 2>&1 | tail -15`
Expected: FAIL — `ModuleNotFoundError: No module named 'news.tests.base'`

- [ ] **Step 3: Test tabanini yaz**

`news/tests/base.py`:

```python
"""v1 view testleri icin ortak taban ve yardimcilar.

V1TestCase iki sorunu cozer:

1. Throttle sayaclari canli Redis'e yazilmaz. Test veritabani kullanici
   id'lerini 1'den baslatir; sayaclar canli Redis'e yazilsaydi gercek
   kullanicilarla (id 1 adanedhel, id 2 entegrasyon) cakisir ve onlari
   hiz sinirina takabilirdi.
2. WhiteNoise yuklenmez. Her test istemcisi middleware'i yeniden kurar ve
   WhiteNoise kurulurken staticfiles/ altindaki ~2000 dosyayi tarar; bind
   mount uzerinden bu test basina ~2 sn ekliyordu. v1 statik dosya sunmaz.
"""
import os
import uuid

import redis
from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token

LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
TEST_MIDDLEWARE = [m for m in settings.MIDDLEWARE if 'whitenoise' not in m.lower()]


def test_redis_client():
    """Canli Redis sunucusuna dogrudan istemci.

    Locmem cache override altinda django_redis.get_redis_connection kullanilamaz.
    Bu istemciyle yazilan her anahtar benzersiz bir onek tasimali ve test
    sonunda silinmelidir; FLUSHDB kesinlikle kullanilmaz (db 0 canli cache'tir).
    """
    return redis.Redis.from_url(os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'))


@override_settings(CACHES=LOCMEM_CACHE, MIDDLEWARE=TEST_MIDDLEWARE)
class V1TestCase(TestCase):
    """v1 HTTP testlerinin tabani."""

    def setUp(self):
        super().setUp()
        # Locmem cache surec boyunca yasar; throttle sayaclari testten teste tasinmasin
        cache.clear()

    def token_basligi(self):
        """Yeni bir kullanici ve token olusturup istek basligini dondurur."""
        kullanici = User.objects.create_user(f'test-{uuid.uuid4().hex[:10]}')
        token = Token.objects.create(user=kullanici)
        return {'HTTP_AUTHORIZATION': f'Token {token.key}'}
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_altyapi -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 4 tests`, `OK`

- [ ] **Step 5: A1 view testlerini yeni tabana gecir**

Asagidaki **bes sinifin** tabanini `TestCase`'ten `V1TestCase`'e cevir. `setUp` tanimlayan dordunde `setUp` govdesinin **ilk satirina** `super().setUp()` ekle. Baska hicbir satiri degistirme.

| Dosya | Sinif | `setUp` var mi |
|---|---|---|
| `news/tests/test_auth.py` | `HealthEndpointTests` | hayir |
| `news/tests/test_auth.py` | `TokenAuthTests` | evet |
| `news/tests/test_auth.py` | `HataBicimiTests` | evet |
| `news/tests/test_cursor.py` | `DeltaAkisiTests` | evet |
| `news/tests/test_filters.py` | `FiltreTests` | evet |

Her uc dosyanin import bloguna ekle:

```python
from news.tests.base import V1TestCase
```

Ornek — `TokenAuthTests` degisiklikten sonra:

```python
class TokenAuthTests(V1TestCase):
    """v1 okuma uc noktalari token ister."""

    def setUp(self):
        super().setUp()
        self.kullanici = User.objects.create_user('entegrasyon', password='parola-yok-test')
        self.token = Token.objects.create(user=self.kullanici)
```

`HTTP` istemcisi kullanmayan siniflar (`UpdatedAtFieldTests`, `CursorCodecTests`, `ApplyCursorTests`, `SerializerBicimTests`) `TestCase` olarak kalir.

- [ ] **Step 6: Tum testleri kos ve sureyi olc**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 56 tests in ...` ve `OK`. Sure, onceki ~50 sn'den **belirgin sekilde kisa** olmali (olcum: tek bir sinif 23.2 sn → 1.7 sn). Kisalmadiysa bir siniftan `V1TestCase` gecisi atlanmistir.

- [ ] **Step 7: Commit**

```bash
git add news/tests/
git commit -m "$(cat <<'MSG'
test: v1 view testlerini canli Redis'ten ayir ve hizlandir

View testleri cache override etmiyordu; throttle sayaclari canli Redis'e
yaziliyordu. Test veritabani kullanici id'lerini 1'den baslattigi icin
sayaclar gercek kullanicilarla cakisabilir ve onlari hiz sinirina
takabilirdi — A2'deki saatte 12'lik refresh sinirinda bu bir saatlik
kilitlenme demekti.

Ayrica WhiteNoise her test istemcisinde staticfiles/ altindaki ~2000
dosyayi tariyordu (bind mount uzerinden ~2 sn/test). Yeni V1TestCase
tabani locmem cache ve WhiteNoise'suz middleware kullaniyor; olcumde tek
bir test sinifi 23.2 sn'den 1.7 sn'ye indi.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: `RefreshGate` — Redis kilit, soguma ve job kaydi

**Files:**
- Create: `news/api_v1/refresh.py`
- Create: `news/tests/test_refresh.py`

**Interfaces:**
- Consumes: `test_redis_client()` (Task 2)
- Produces (`news/api_v1/refresh.py`):
  - Sabitler: `REFRESH_COOLDOWN: int` (env, varsayilan 900), `REFRESH_LOCK_TTL: int` (env, varsayilan 3600), `JOB_RECORD_TTL = 86400`
  - `RefreshGate(client, prefix='refresh')`, nitelik `prefix`
    - `running_job(section: str) -> Optional[str]`
    - `cooldown_remaining(section: str) -> int` — saniye, yukari yuvarlanmis; soguma yoksa 0
    - `acquire(section: str, job_id: str, lock_ttl: int) -> bool` — `SET NX EX`
    - `start_cooldown(section: str, seconds: int) -> None` — `seconds <= 0` ise hicbir sey yapmaz
    - `record_job(job_id: str, section: str, ttl: int = JOB_RECORD_TTL) -> None`
    - `job_section(job_id: str) -> Optional[str]`
    - `release(section: str, job_id: str) -> bool` — yalnizca kilit bu job'a aitse siler (Lua compare-and-delete)
    - `release_job(job_id: str) -> bool` — job kaydindan bolumu bulup `release` cagirir; kayit yoksa False
    - `rollback(section: str, job_id: str) -> None` — kilidi, sogumayi ve job kaydini siler

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_refresh.py`:

```python
"""Manuel tetikleme testleri: gate, trigger, sinyal ve refresh uc noktalari.

Redis gercek kullanilir (benzersiz onekle). Celery task'lari hicbir zaman
gercekten kuyruga atilmaz: canli worker ayni broker'i dinliyor.
"""
import uuid

from django.test import SimpleTestCase

from news.api_v1.refresh import RefreshGate
from news.tests.base import test_redis_client


class RedisOnekliTestMixin:
    """Benzersiz onekli RefreshGate kurar ve test sonunda kendi anahtarlarini siler."""

    def setUp(self):
        super().setUp()
        self.redis = test_redis_client()
        self.gate = RefreshGate(self.redis, prefix=f'test-refresh-{uuid.uuid4().hex}')
        self.addCleanup(self._anahtarlari_sil)

    def _anahtarlari_sil(self):
        for anahtar in self.redis.scan_iter(f'{self.gate.prefix}:*'):
            self.redis.delete(anahtar)


class RefreshGateTests(RedisOnekliTestMixin, SimpleTestCase):

    def test_ilk_kilit_alinir_ikincisi_alinamaz(self):
        self.assertTrue(self.gate.acquire('cve', 'is-1', 60))
        self.assertFalse(self.gate.acquire('cve', 'is-2', 60))
        self.assertEqual(self.gate.running_job('cve'), 'is-1')

    def test_bolumler_birbirini_kilitlemez(self):
        self.assertTrue(self.gate.acquire('cve', 'is-1', 60))
        self.assertTrue(self.gate.acquire('ai', 'is-2', 60))

    def test_kilit_yoksa_calisan_is_none(self):
        self.assertIsNone(self.gate.running_job('cve'))

    def test_soguma_yoksa_kalan_sifir(self):
        self.assertEqual(self.gate.cooldown_remaining('cve'), 0)

    def test_soguma_kalan_sureyi_saniye_olarak_verir(self):
        self.gate.start_cooldown('cve', 900)
        kalan = self.gate.cooldown_remaining('cve')
        self.assertGreater(kalan, 890)
        self.assertLessEqual(kalan, 900)

    def test_sifir_soguma_anahtar_yazmaz(self):
        self.gate.start_cooldown('cve', 0)
        self.assertEqual(self.gate.cooldown_remaining('cve'), 0)

    def test_baska_isin_kilidi_birakilamaz(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.assertFalse(self.gate.release('cve', 'baska-is'))
        self.assertEqual(self.gate.running_job('cve'), 'is-1')

    def test_kendi_kilidini_birakir(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.assertTrue(self.gate.release('cve', 'is-1'))
        self.assertIsNone(self.gate.running_job('cve'))

    def test_job_kaydi_uzerinden_birakir(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.gate.record_job('is-1', 'cve')
        self.assertEqual(self.gate.job_section('is-1'), 'cve')
        self.assertTrue(self.gate.release_job('is-1'))
        self.assertIsNone(self.gate.running_job('cve'))

    def test_kaydi_olmayan_job_hicbir_seyi_birakmaz(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.assertFalse(self.gate.release_job('beat-isi'))
        self.assertEqual(self.gate.running_job('cve'), 'is-1')

    def test_rollback_her_seyi_siler(self):
        self.gate.acquire('cve', 'is-1', 60)
        self.gate.record_job('is-1', 'cve')
        self.gate.start_cooldown('cve', 900)
        self.gate.rollback('cve', 'is-1')
        self.assertIsNone(self.gate.running_job('cve'))
        self.assertEqual(self.gate.cooldown_remaining('cve'), 0)
        self.assertIsNone(self.gate.job_section('is-1'))
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh -v 2 2>&1 | tail -15`
Expected: FAIL — `ModuleNotFoundError: No module named 'news.api_v1.refresh'`

- [ ] **Step 3: `RefreshGate`'i yaz**

`news/api_v1/refresh.py`:

```python
"""Manuel tetikleme: bolum kilidi, soguma ve job kaydi (spec bolum 8).

Uc Redis anahtari kullanilir (onek varsayilan 'refresh'):

  refresh:running:{bolum}  Calisan isin job_id'si. Is bitince task_postrun
                           sinyali siler (job_signals.py). Worker olurse
                           REFRESH_LOCK_TTL sonunda kendiliginden duser.
  refresh:cooldown:{bolum} Son manuel tetiklemeden sonra REFRESH_COOLDOWN saniye.
  refresh:job:{job_id}     job_id -> bolum. Celery bilinmeyen bir id icin de
                           PENDING dondurur; jobs uc noktasi bilinmeyen
                           kimligi bu kayitla ayirt eder.

Bilinen sinir: Beat'in baslattigi isler kilit almaz. Manuel tetikleme bir Beat
calismasiyla cakisabilir; task'lar update_or_create ve skip_existing ile
idempotent oldugu icin veri bozulmaz, yalnizca kaynak sitelere cift istek gider.
"""
import os
from typing import Optional

REFRESH_COOLDOWN = int(os.environ.get('REFRESH_COOLDOWN', '900'))
# En uzun gozlenen cekim 751 sn (CVE, 2026-09-12). Kilit bundan belirgin uzun olmali.
REFRESH_LOCK_TTL = int(os.environ.get('REFRESH_LOCK_TTL', '3600'))
# Celery sonuc backend'inin varsayilan saklama suresiyle ayni (1 gun)
JOB_RECORD_TTL = 86400

# Anahtar degeri beklenen job_id ise siler; baska bir isin kilidini silmez.
_COMPARE_AND_DELETE = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


def _metin(deger) -> Optional[str]:
    return deger.decode('utf-8') if deger is not None else None


class RefreshGate:
    """Bolum basina kilit, soguma ve job kaydi. Tum surecler Redis uzerinden paylasir."""

    def __init__(self, client, prefix: str = 'refresh'):
        self.client = client
        self.prefix = prefix

    def _anahtar(self, tur: str, ad: str) -> str:
        return f'{self.prefix}:{tur}:{ad}'

    def running_job(self, section: str) -> Optional[str]:
        return _metin(self.client.get(self._anahtar('running', section)))

    def cooldown_remaining(self, section: str) -> int:
        kalan_ms = self.client.pttl(self._anahtar('cooldown', section))
        if kalan_ms is None or kalan_ms <= 0:  # -2: anahtar yok, -1: suresiz
            return 0
        return -(-kalan_ms // 1000)  # yukari yuvarla: 0.4 sn kaldiysa 1 de

    def acquire(self, section: str, job_id: str, lock_ttl: int) -> bool:
        return bool(self.client.set(self._anahtar('running', section), job_id,
                                    nx=True, ex=lock_ttl))

    def start_cooldown(self, section: str, seconds: int) -> None:
        if seconds > 0:
            self.client.set(self._anahtar('cooldown', section), 1, ex=seconds)

    def record_job(self, job_id: str, section: str, ttl: int = JOB_RECORD_TTL) -> None:
        self.client.set(self._anahtar('job', job_id), section, ex=ttl)

    def job_section(self, job_id: str) -> Optional[str]:
        return _metin(self.client.get(self._anahtar('job', job_id)))

    def release(self, section: str, job_id: str) -> bool:
        return bool(self.client.eval(_COMPARE_AND_DELETE, 1,
                                     self._anahtar('running', section), job_id))

    def release_job(self, job_id: str) -> bool:
        section = self.job_section(job_id)
        return self.release(section, job_id) if section else False

    def rollback(self, section: str, job_id: str) -> None:
        """Kuyruga atma basarisiz olursa tetiklemenin tum izlerini siler."""
        self.release(section, job_id)
        self.client.delete(self._anahtar('cooldown', section), self._anahtar('job', job_id))
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 11 tests`, `OK`

- [ ] **Step 5: Test anahtarlarinin canli Redis'te kalmadigini dogrula**

Run: `docker compose exec -T teknoloji-redis redis-cli --scan --pattern 'test-refresh-*' | wc -l`
Expected: `0`

- [ ] **Step 6: Commit**

```bash
git add news/api_v1/refresh.py news/tests/test_refresh.py
git commit -m "$(cat <<'MSG'
feat: refresh icin Redis bolum kilidi, soguma ve job kaydi

RefreshGate uc anahtarla calisiyor: bolum basina kilit (SET NX EX),
bolum basina soguma ve job_id -> bolum kaydi. Kilit Lua ile
compare-and-delete yapilarak birakiliyor; bir is baska bir isin kilidini
silemiyor. Job kaydi, Celery'nin bilinmeyen id'ler icin de PENDING
dondurmesine karsi jobs uc noktasinin kimligi ayirt edebilmesi icin.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: `trigger()` — tetikleme akisi

**Files:**
- Modify: `news/api_v1/refresh.py` (sonuna ekleme)
- Modify: `news/tests/base.py` (`RefreshTestMixin`)
- Modify: `news/tests/test_refresh.py`

**Interfaces:**
- Consumes: `RefreshGate` (Task 3), `news.tasks` icindeki alti task
- Produces:
  - `SECTIONS: tuple[str, ...] = ('news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai')` — URL yollariyla birebir ayni
  - `section_tasks() -> dict[str, Task]`
  - `TriggerResult(section: str, status: str, job_id: Optional[str] = None, retry_after: int = 0)` — `status` ∈ `'started' | 'already_running' | 'cooldown'`
  - `get_gate() -> RefreshGate` — canli Redis'e bagli gate; testler bunu patch'ler
  - `trigger(section, gate=None, cooldown=None, lock_ttl=None) -> TriggerResult` — bilinmeyen bolumde `ValueError`; kuyruga atma istisnasinda rollback yapip istisnayi yeniden firlatir
  - `RefreshTestMixin` (`news/tests/base.py`) — `self.redis`, `self.gate` (benzersiz onekli, `news.api_v1.refresh.get_gate` bunu dondurecek sekilde patch'li), `self.gorevler: dict[str, MagicMock]` (bolum adi → o task'in mock'lanmis `apply_async`'i); test sonunda anahtarlari siler

- [ ] **Step 1: `RefreshTestMixin`'i yaz**

Bu mixin test altyapisidir; kendisinin RED asamasi yoktur. `news/tests/base.py` sonuna ekle:

```python
from unittest import mock


class RefreshTestMixin:
    """Tetikleme testleri icin guvenli ortam.

    - get_gate() benzersiz onekli bir gate dondurur; test sonunda anahtarlari silinir.
    - Alti task'in apply_async'i mock'lanir: hicbir test gercek bir cekim isini
      canli worker'in kuyruguna atamaz.
    """

    GOREV_ADLARI = {
        'news': 'fetch_news_task',
        'cve': 'fetch_cve_task',
        'kubernetes': 'fetch_k8s_task',
        'sre': 'fetch_sre_task',
        'devtools': 'fetch_devtools_task',
        'ai': 'fetch_ai_news_task',
    }

    def setUp(self):
        super().setUp()
        from news import tasks
        from news.api_v1.refresh import RefreshGate

        self.redis = test_redis_client()
        self.gate = RefreshGate(self.redis, prefix=f'test-refresh-{uuid.uuid4().hex}')
        self.addCleanup(self._refresh_anahtarlarini_sil)

        yama = mock.patch('news.api_v1.refresh.get_gate', return_value=self.gate)
        yama.start()
        self.addCleanup(yama.stop)

        self.gorevler = {}
        for bolum, ad in self.GOREV_ADLARI.items():
            yama = mock.patch.object(getattr(tasks, ad), 'apply_async')
            self.gorevler[bolum] = yama.start()
            self.addCleanup(yama.stop)

    def _refresh_anahtarlarini_sil(self):
        for anahtar in self.redis.scan_iter(f'{self.gate.prefix}:*'):
            self.redis.delete(anahtar)
```

- [ ] **Step 2: Basarisiz testi yaz**

`news/tests/test_refresh.py` — import blogunu genislet:

```python
import uuid
from unittest import mock

from django.test import SimpleTestCase

from news.api_v1 import refresh
from news.api_v1.refresh import RefreshGate
from news.tests.base import RefreshTestMixin, test_redis_client
```

Dosyanin sonuna ekle:

```python
class TriggerTests(RefreshTestMixin, SimpleTestCase):
    """Kontrol sirasi: once kilit, sonra soguma, sonra kuyruga atma."""

    def test_ilk_tetikleme_baslar(self):
        sonuc = refresh.trigger('cve')
        self.assertEqual(sonuc.status, 'started')
        self.assertEqual(sonuc.section, 'cve')
        uuid.UUID(sonuc.job_id)  # gecerli bir uuid olmali
        self.gorevler['cve'].assert_called_once_with(
            kwargs={'skip_existing': True}, task_id=sonuc.job_id)
        self.assertEqual(self.gate.running_job('cve'), sonuc.job_id)
        self.assertEqual(self.gate.job_section(sonuc.job_id), 'cve')
        self.assertGreater(self.gate.cooldown_remaining('cve'), 0)

    def test_varsayilan_soguma_15_dakika(self):
        refresh.trigger('cve')
        self.assertGreater(self.gate.cooldown_remaining('cve'), 890)
        self.assertLessEqual(self.gate.cooldown_remaining('cve'), refresh.REFRESH_COOLDOWN)

    def test_calisirken_ikinci_tetikleme_ayni_isi_doner(self):
        ilk = refresh.trigger('cve')
        ikinci = refresh.trigger('cve')
        self.assertEqual(ikinci.status, 'already_running')
        self.assertEqual(ikinci.job_id, ilk.job_id)
        self.gorevler['cve'].assert_called_once()

    def test_is_bittikten_sonra_soguma_devam_eder(self):
        ilk = refresh.trigger('cve')
        self.gate.release('cve', ilk.job_id)
        sonuc = refresh.trigger('cve')
        self.assertEqual(sonuc.status, 'cooldown')
        self.assertGreater(sonuc.retry_after, 0)
        self.assertIsNone(sonuc.job_id)
        self.gorevler['cve'].assert_called_once()

    def test_soguma_bitince_yeniden_baslar(self):
        ilk = refresh.trigger('cve', cooldown=0)
        self.gate.release('cve', ilk.job_id)
        ikinci = refresh.trigger('cve', cooldown=0)
        self.assertEqual(ikinci.status, 'started')
        self.assertNotEqual(ikinci.job_id, ilk.job_id)
        self.assertEqual(self.gorevler['cve'].call_count, 2)

    def test_bir_bolumun_sogumasi_digerini_etkilemez(self):
        refresh.trigger('cve')
        self.assertEqual(refresh.trigger('ai').status, 'started')

    def test_kuyruga_atma_basarisizsa_iz_birakmaz(self):
        self.gorevler['cve'].side_effect = ConnectionError('broker yok')
        with self.assertRaises(ConnectionError):
            refresh.trigger('cve')
        self.assertIsNone(self.gate.running_job('cve'))
        self.assertEqual(self.gate.cooldown_remaining('cve'), 0)

    def test_yarisi_kaybeden_kazananin_isini_doner(self):
        """Iki istek ayni anda kilidin bos oldugunu gorurse yalnizca biri kuyruga atar."""
        self.gate.acquire('cve', 'kazanan-is', 60)
        with mock.patch.object(self.gate, 'running_job', side_effect=[None, 'kazanan-is']):
            sonuc = refresh.trigger('cve')
        self.assertEqual(sonuc.status, 'already_running')
        self.assertEqual(sonuc.job_id, 'kazanan-is')
        self.gorevler['cve'].assert_not_called()

    def test_bilinmeyen_bolum_reddedilir(self):
        with self.assertRaises(ValueError):
            refresh.trigger('olmayan-bolum')

    def test_bolum_listesi_url_yollariyla_ayni(self):
        self.assertEqual(refresh.SECTIONS, ('news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai'))
        self.assertEqual(set(refresh.section_tasks()), set(refresh.SECTIONS))
```

- [ ] **Step 3: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh.TriggerTests -v 2 2>&1 | tail -15`
Expected: FAIL / ERROR — `module 'news.api_v1.refresh' has no attribute 'get_gate'` (mixin patch'i) veya `trigger`.

- [ ] **Step 4: `trigger()`'i yaz**

`news/api_v1/refresh.py` — import blogunu su hale getir:

```python
import os
import uuid
from dataclasses import dataclass
from typing import Optional
```

Dosyanin sonuna ekle:

```python
SECTIONS = ('news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai')


def section_tasks():
    """Bolum adi -> Celery task'i. Dongusel import olmasin diye gec import edilir."""
    from news import tasks
    return {
        'news': tasks.fetch_news_task,
        'cve': tasks.fetch_cve_task,
        'kubernetes': tasks.fetch_k8s_task,
        'sre': tasks.fetch_sre_task,
        'devtools': tasks.fetch_devtools_task,
        'ai': tasks.fetch_ai_news_task,
    }


@dataclass
class TriggerResult:
    section: str
    status: str  # 'started' | 'already_running' | 'cooldown'
    job_id: Optional[str] = None
    retry_after: int = 0


def get_gate() -> RefreshGate:
    """Canli Redis'e bagli gate. Testler bu fonksiyonu patch'ler."""
    from django_redis import get_redis_connection
    return RefreshGate(get_redis_connection('default'))


def trigger(section: str, gate: Optional[RefreshGate] = None,
            cooldown: Optional[int] = None, lock_ttl: Optional[int] = None) -> TriggerResult:
    """Bir bolum icin manuel cekimi baslatir.

    Kontrol sirasi onemlidir: once kilit, sonra soguma. Soguma tetikleme aninda
    baslar; sira ters olsaydi calisan her is icin 'already_running' yerine
    'cooldown' donerdi ve tuketici isi izleyemezdi.
    """
    if section not in SECTIONS:
        raise ValueError(f'Bilinmeyen bolum: {section}')
    gate = gate or get_gate()
    cooldown = REFRESH_COOLDOWN if cooldown is None else cooldown
    lock_ttl = REFRESH_LOCK_TTL if lock_ttl is None else lock_ttl

    calisan = gate.running_job(section)
    if calisan:
        return TriggerResult(section, 'already_running', job_id=calisan)

    kalan = gate.cooldown_remaining(section)
    if kalan > 0:
        return TriggerResult(section, 'cooldown', retry_after=kalan)

    job_id = str(uuid.uuid4())
    if not gate.acquire(section, job_id, lock_ttl):
        # Yaris: baska bir istek kilidi bizden once aldi; onun isini dondur
        return TriggerResult(section, 'already_running', job_id=gate.running_job(section))

    gate.record_job(job_id, section)
    gate.start_cooldown(section, cooldown)
    try:
        section_tasks()[section].apply_async(kwargs={'skip_existing': True}, task_id=job_id)
    except Exception:
        gate.rollback(section, job_id)
        raise
    return TriggerResult(section, 'started', job_id=job_id)
```

- [ ] **Step 5: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 21 tests`, `OK`

- [ ] **Step 6: Hicbir isin gercekten kuyruga atilmadigini dogrula**

Testler bittikten sonra worker loglarinda son iki dakikada yeni bir `received` satiri olmamali:

Run: `docker compose logs --since 2m teknoloji-worker 2>&1 | grep -c "received" || true`
Expected: `0`

- [ ] **Step 7: Commit**

```bash
git add news/api_v1/refresh.py news/tests/base.py news/tests/test_refresh.py
git commit -m "$(cat <<'MSG'
feat: refresh tetikleme akisi — kilit, soguma, kuyruga atma

trigger() once bolum kilidine, sonra sogumaya bakiyor; ikisi de bossa
kilidi SET NX ile alip job kaydini ve sogumayi yaziyor, sonra isi
job_id ile kuyruga atiyor. Yarisi kaybeden istek kazananin isini
donduruyor. Kuyruga atma basarisiz olursa kilit, soguma ve kayit geri
aliniyor.

RefreshTestMixin alti task'in apply_async'ini mock'luyor; hicbir test
canli worker'a gercek cekim isi gonderemiyor.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: Is bitince kilidi birak (`task_postrun` sinyali)

**Files:**
- Create: `news/api_v1/job_signals.py`, `news/apps.py`
- Modify: `news/tests/test_refresh.py`

**Interfaces:**
- Consumes: `refresh.get_gate()`, `RefreshGate.release_job()` (Task 3-4)
- Produces: `refresh_kilidini_birak(sender=None, task_id=None, **kwargs)` alicisi `celery.signals.task_postrun`'a bagli; `NewsConfig.ready()` modulu yukler. Beat'in baslattigi (job kaydi olmayan) islerde hicbir sey yapmaz.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_refresh.py` sonuna ekle:

```python
from celery.signals import task_postrun


class KilitBirakmaSinyaliTests(RefreshTestMixin, SimpleTestCase):
    """Worker isi bitirince kilit birakilmali; soguma ise devam etmeli."""

    def _is_bitti(self, task_id):
        task_postrun.send(sender=None, task_id=task_id, task=None, args=(), kwargs={},
                          retval=None, state='SUCCESS')

    def test_is_bitince_kilit_birakilir(self):
        sonuc = refresh.trigger('cve')
        self._is_bitti(sonuc.job_id)
        self.assertIsNone(self.gate.running_job('cve'))

    def test_is_bitince_soguma_devam_eder(self):
        sonuc = refresh.trigger('cve')
        self._is_bitti(sonuc.job_id)
        self.assertGreater(self.gate.cooldown_remaining('cve'), 0)

    def test_beat_isi_manuel_kilide_dokunmaz(self):
        sonuc = refresh.trigger('cve')
        self._is_bitti('beat-tarafindan-baslatilmis-is')
        self.assertEqual(self.gate.running_job('cve'), sonuc.job_id)

    def test_news_uygulama_yapilandirmasi_yuklu(self):
        from django.apps import apps
        self.assertEqual(type(apps.get_app_config('news')).__name__, 'NewsConfig')
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh.KilitBirakmaSinyaliTests -v 2 2>&1 | tail -15`
Expected: FAIL — `test_is_bitince_kilit_birakilir` (kilit hala duruyor) ve `test_news_uygulama_yapilandirmasi_yuklu` (`'AppConfig' != 'NewsConfig'`). Diger ikisi zaten gecebilir; bu beklenir.

- [ ] **Step 3: Sinyal alicisini ve uygulama yapilandirmasini yaz**

`news/api_v1/job_signals.py`:

```python
"""Celery sinyalleri: manuel tetiklenen is bitince bolum kilidini birakir.

Worker surecinde news uygulamasi yuklenirken (NewsConfig.ready) import edilir.
Kilit birakilamazsa is basarisiz sayilmaz; REFRESH_LOCK_TTL emniyet agidir.
"""
from celery.signals import task_postrun


@task_postrun.connect
def refresh_kilidini_birak(sender=None, task_id=None, **kwargs):
    # get_gate burada, cagri aninda import edilir; testler onu patch'leyebilsin
    from .refresh import get_gate
    try:
        get_gate().release_job(task_id)
    except Exception as hata:
        print(f'  [Refresh] Kilit birakilamadi ({task_id}): {hata}')
```

`news/apps.py`:

```python
from django.apps import AppConfig


class NewsConfig(AppConfig):
    name = 'news'
    verbose_name = 'Teknoloji Haberleri'

    def ready(self):
        # Manuel tetiklenen is bitince bolum kilidini birakan Celery sinyali
        from .api_v1 import job_signals  # noqa: F401
```

`default_auto_field` **eklenmez**: `settings.DEFAULT_AUTO_FIELD = BigAutoField` zaten tanimli; burada farkli bir deger migration uretir.

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 25 tests`, `OK`

- [ ] **Step 5: Migration uretmedigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py makemigrations --check --dry-run 2>&1 | tail -2`
Expected: `No changes detected`

- [ ] **Step 6: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add news/api_v1/job_signals.py news/apps.py news/tests/test_refresh.py
git commit -m "$(cat <<'MSG'
feat: manuel tetiklenen is bitince bolum kilidini birak

task_postrun sinyali job kaydindan bolumu bulup kilidi compare-and-delete
ile birakiyor; soguma devam ediyor. Beat'in baslattigi islerin job kaydi
olmadigi icin manuel kilide dokunulmuyor. Sinyal NewsConfig.ready()
icinde yukleniyor, boylece worker sureci de bagliyor.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: `POST /api/v1/<bolum>/refresh/`

**Files:**
- Modify: `news/api_v1/views.py`, `news/api_v1/urls.py`
- Modify: `news/tests/test_refresh.py`

**Interfaces:**
- Consumes: `refresh.trigger`, `refresh.SECTIONS` (Task 4); `V1APIView`, `_hata` (A1)
- Produces:
  - `_is_govdesi(sonuc: TriggerResult) -> dict` — `{'job_id', 'section', 'status', 'status_url'}`; `job_id` yoksa `status_url` `None`
  - `RefreshView(V1APIView)`, `throttle_scope = 'v1_refresh'`, `post(request, section)`
  - Yanitlar: `202` started/already_running; `429` + `Retry-After` + hata kodu `cooldown`; `404` hata kodu `not_found`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_refresh.py` — import blogunu genislet:

```python
from rest_framework.throttling import ScopedRateThrottle

from news.tests.base import RefreshTestMixin, V1TestCase, test_redis_client
```

Dosyanin sonuna ekle:

```python
class RefreshUcNoktasiTests(RefreshTestMixin, V1TestCase):

    def setUp(self):
        super().setUp()
        self.baslik = self.token_basligi()

    def _tetikle(self, bolum='cve'):
        return self.client.post(f'/api/v1/{bolum}/refresh/', **self.baslik)

    def test_tokensiz_401(self):
        yanit = self.client.post('/api/v1/cve/refresh/')
        self.assertEqual(yanit.status_code, 401)
        self.assertEqual(yanit.json()['error']['code'], 'unauthorized')
        self.gorevler['cve'].assert_not_called()

    def test_baslatir_202(self):
        yanit = self._tetikle()
        self.assertEqual(yanit.status_code, 202)
        govde = yanit.json()
        self.assertEqual(govde['status'], 'started')
        self.assertEqual(govde['section'], 'cve')
        self.assertEqual(govde['status_url'], f"/api/v1/jobs/{govde['job_id']}/")
        self.gorevler['cve'].assert_called_once()

    def test_calisirken_ayni_isi_doner_202(self):
        ilk = self._tetikle().json()
        yanit = self._tetikle()
        self.assertEqual(yanit.status_code, 202)
        self.assertEqual(yanit.json()['status'], 'already_running')
        self.assertEqual(yanit.json()['job_id'], ilk['job_id'])
        self.assertEqual(yanit.json()['status_url'], ilk['status_url'])

    def test_sogumada_429_ve_retry_after(self):
        ilk = self._tetikle().json()
        self.gate.release('cve', ilk['job_id'])
        yanit = self._tetikle()
        self.assertEqual(yanit.status_code, 429)
        self.assertEqual(yanit.json()['error']['code'], 'cooldown')
        self.assertGreater(int(yanit['Retry-After']), 0)

    def test_bilinmeyen_bolum_404(self):
        yanit = self._tetikle('olmayan')
        self.assertEqual(yanit.status_code, 404)
        self.assertEqual(yanit.json()['error']['code'], 'not_found')

    def test_get_405(self):
        yanit = self.client.get('/api/v1/cve/refresh/', **self.baslik)
        self.assertEqual(yanit.status_code, 405)

    def test_alti_bolum_de_tetiklenebilir(self):
        for bolum in ('news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai'):
            with self.subTest(bolum=bolum):
                self.assertEqual(self._tetikle(bolum).status_code, 202)
                self.gorevler[bolum].assert_called_once()

    def test_token_basina_hiz_siniri_ayri_scope(self):
        """Refresh, okuma sinirindan bagimsiz ve cok daha siki sinirlanir."""
        oranlar = {'v1_read': '120/min', 'v1_refresh': '2/hour'}
        with mock.patch.object(ScopedRateThrottle, 'THROTTLE_RATES', oranlar):
            self.assertEqual(self._tetikle('cve').status_code, 202)
            self.assertEqual(self._tetikle('sre').status_code, 202)
            ucuncu = self._tetikle('ai')
            okuma = self.client.get('/api/v1/ai/', **self.baslik)
        self.assertEqual(ucuncu.status_code, 429)
        self.assertEqual(ucuncu.json()['error']['code'], 'throttled')
        self.gorevler['ai'].assert_not_called()
        self.assertEqual(okuma.status_code, 200)
```

Not: `ScopedRateThrottle.THROTTLE_RATES` sinif niteligi import aninda ayarlardan kopyalanir; `override_settings(REST_FRAMEWORK=...)` bu yuzden etkisizdir. Testte sinif niteligi dogrudan patch'lenir.

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh.RefreshUcNoktasiTests -v 2 2>&1 | tail -15`
Expected: FAIL — `/api/v1/cve/refresh/` icin 404 (URL yok).

- [ ] **Step 3: View'i yaz**

`news/api_v1/views.py` — import bloguna ekle:

```python
from . import refresh
```

`AIDeltaView` sinifindan sonra, dosyanin sonuna ekle:

```python
def _is_govdesi(sonuc):
    """Baslatilan veya zaten calisan bir is icin tuketiciye donen govde."""
    return {
        'job_id': sonuc.job_id,
        'section': sonuc.section,
        'status': sonuc.status,
        'status_url': f'/api/v1/jobs/{sonuc.job_id}/' if sonuc.job_id else None,
    }


class RefreshView(V1APIView):
    """Tek bir bolum icin manuel cekim tetikler (spec bolum 8).

    Uc katman korur: bolum kilidi (cift kazima olmaz), 15 dk bolum sogumasi
    (kaynak sitelere yuk binmez) ve token basina v1_refresh hiz siniri.
    """

    throttle_scope = 'v1_refresh'

    def post(self, request, section):
        if section not in refresh.SECTIONS:
            return _hata('not_found', f"Bilinmeyen bolum: '{section}'.",
                         status.HTTP_404_NOT_FOUND)

        sonuc = refresh.trigger(section)
        if sonuc.status == 'cooldown':
            yanit = _hata('cooldown',
                          f"'{section}' bolumu yakin zamanda yenilendi; "
                          f"{sonuc.retry_after} sn sonra tekrar deneyin.",
                          status.HTTP_429_TOO_MANY_REQUESTS)
            yanit['Retry-After'] = str(sonuc.retry_after)
            return yanit

        return Response(_is_govdesi(sonuc), status=status.HTTP_202_ACCEPTED)
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
    path('<str:section>/refresh/', views.RefreshView.as_view(), name='v1-refresh'),
]
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 33 tests`, `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add news/api_v1/views.py news/api_v1/urls.py news/tests/test_refresh.py
git commit -m "$(cat <<'MSG'
feat: POST /api/v1/<bolum>/refresh/ uc noktasi

Isi baslatinca 202 ve job_id + status_url donuyor; ayni bolum zaten
calisiyorsa yine 202 ile calisan isin kimligini donuyor; sogumadaysa 429,
Retry-After basligi ve cooldown hata kodu donuyor. Token basina
v1_refresh scope'u okuma sinirindan bagimsiz uygulaniyor.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 7: `POST /api/v1/refresh/` — alti bolumu birden tetikle

**Files:**
- Modify: `news/api_v1/views.py`, `news/api_v1/urls.py`
- Modify: `news/tests/test_refresh.py`

**Interfaces:**
- Consumes: `refresh.trigger`, `refresh.get_gate`, `refresh.SECTIONS`, `_is_govdesi` (Task 6)
- Produces: `RefreshAllView(V1APIView)`, `throttle_scope = 'v1_refresh'`. Her zaman `202`; govde `{'started': [is_govdesi...], 'already_running': [is_govdesi...], 'skipped': [{'section', 'retry_after'}...]}`. Listeler `SECTIONS` sirasindadir. Toplu cagri hiz sinirindan **tek istek** olarak duser.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_refresh.py` sonuna ekle:

```python
class TopluRefreshTests(RefreshTestMixin, V1TestCase):

    def setUp(self):
        super().setUp()
        self.baslik = self.token_basligi()

    def _toplu(self):
        return self.client.post('/api/v1/refresh/', **self.baslik)

    @staticmethod
    def _bolumler(liste):
        return [oge['section'] for oge in liste]

    def test_ilk_cagri_alti_bolumu_baslatir(self):
        yanit = self._toplu()
        self.assertEqual(yanit.status_code, 202)
        govde = yanit.json()
        self.assertEqual(self._bolumler(govde['started']),
                         ['news', 'cve', 'kubernetes', 'sre', 'devtools', 'ai'])
        self.assertEqual(govde['already_running'], [])
        self.assertEqual(govde['skipped'], [])
        for sahte in self.gorevler.values():
            sahte.assert_called_once()

    def test_ikinci_cagri_calisan_isleri_doner(self):
        self._toplu()
        govde = self._toplu().json()
        self.assertEqual(govde['started'], [])
        self.assertEqual(len(govde['already_running']), 6)
        for sahte in self.gorevler.values():
            sahte.assert_called_once()

    def test_karisik_durum_dogru_ayrilir(self):
        refresh.trigger('ai')                        # calisiyor
        cve = refresh.trigger('cve')
        self.gate.release('cve', cve.job_id)         # bitti, sogumada
        self.gorevler['ai'].reset_mock()
        self.gorevler['cve'].reset_mock()

        govde = self._toplu().json()
        self.assertEqual(self._bolumler(govde['started']),
                         ['news', 'kubernetes', 'sre', 'devtools'])
        self.assertEqual(self._bolumler(govde['already_running']), ['ai'])
        self.assertEqual(self._bolumler(govde['skipped']), ['cve'])
        self.assertGreater(govde['skipped'][0]['retry_after'], 0)
        self.gorevler['ai'].assert_not_called()
        self.gorevler['cve'].assert_not_called()

    def test_hic_baslamasa_da_202(self):
        for bolum in refresh.SECTIONS:
            sonuc = refresh.trigger(bolum)
            self.gate.release(bolum, sonuc.job_id)
        yanit = self._toplu()
        self.assertEqual(yanit.status_code, 202)
        self.assertEqual(len(yanit.json()['skipped']), 6)

    def test_tokensiz_401(self):
        self.assertEqual(self.client.post('/api/v1/refresh/').status_code, 401)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh.TopluRefreshTests -v 2 2>&1 | tail -15`
Expected: FAIL — `/api/v1/refresh/` icin 404.

- [ ] **Step 3: View'i yaz**

`news/api_v1/views.py` sonuna ekle:

```python
class RefreshAllView(V1APIView):
    """Alti bolumu birden tetikler. Her bolum kendi kilidine ve sogumasina tabidir.

    Her zaman 202 doner; tuketici hangi bolumlerin baslatildigini, zaten
    calistigini veya sogumada oldugu icin atlandigini listelerden okur.
    """

    throttle_scope = 'v1_refresh'

    def post(self, request):
        gate = refresh.get_gate()
        govde = {'started': [], 'already_running': [], 'skipped': []}
        for section in refresh.SECTIONS:
            sonuc = refresh.trigger(section, gate=gate)
            if sonuc.status == 'cooldown':
                govde['skipped'].append({'section': section, 'retry_after': sonuc.retry_after})
            else:
                govde[sonuc.status].append(_is_govdesi(sonuc))
        return Response(govde, status=status.HTTP_202_ACCEPTED)
```

`news/api_v1/urls.py` — `health/` satirinin hemen altina ekle:

```python
    path('refresh/', views.RefreshAllView.as_view(), name='v1-refresh-all'),
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_refresh -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 38 tests`, `OK`

- [ ] **Step 5: Commit**

```bash
git add news/api_v1/views.py news/api_v1/urls.py news/tests/test_refresh.py
git commit -m "$(cat <<'MSG'
feat: POST /api/v1/refresh/ ile alti bolumu birden tetikle

Her bolum kendi kilidi ve sogumasiyla ayri degerlendiriliyor. Yanit her
zaman 202; started, already_running ve skipped listeleri hangi bolumun ne
durumda oldugunu soyluyor. Toplu cagri hiz sinirindan tek istek dusuyor.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 8: `GET /api/v1/jobs/<job_id>/`

**Files:**
- Modify: `news/api_v1/views.py`, `news/api_v1/urls.py`
- Create: `news/tests/test_jobs.py`

**Interfaces:**
- Consumes: `refresh.get_gate`, `RefreshGate.job_section` (Task 3-4); `cybernews.celery.app` (Task 1)
- Produces: `JobView(V1APIView)` (`throttle_scope = 'v1_read'`, taban degeri). Govde `{'job_id', 'section', 'status'}` + duruma gore `count` veya `error`. `status` ∈ `pending | started | success | failure`. Kaydi olmayan job → `404 not_found`.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_jobs.py`:

```python
"""Job durum uc noktasi testleri.

Celery sonuc backend'i mock'lanir: AsyncResult canli Redis'teki gercek
sonuclari okumasin ve durumlar deterministik olsun.
"""
from unittest import mock

from django.test import SimpleTestCase

from news.api_v1 import refresh
from news.tests.base import RefreshTestMixin, V1TestCase


class SahteSonuc:
    def __init__(self, state, result=None):
        self.state = state
        self.result = result


class JobUcNoktasiTests(RefreshTestMixin, V1TestCase):

    def setUp(self):
        super().setUp()
        self.baslik = self.token_basligi()
        self.job_id = refresh.trigger('cve').job_id

    def _durum(self, sahte_sonuc, job_id=None):
        with mock.patch('news.api_v1.views.AsyncResult', return_value=sahte_sonuc) as sahte:
            yanit = self.client.get(f'/api/v1/jobs/{job_id or self.job_id}/', **self.baslik)
        return yanit, sahte

    def test_kuyrukta_pending(self):
        yanit, _ = self._durum(SahteSonuc('PENDING'))
        self.assertEqual(yanit.status_code, 200)
        self.assertEqual(yanit.json(), {'job_id': self.job_id, 'section': 'cve', 'status': 'pending'})

    def test_calisiyor_started(self):
        yanit, _ = self._durum(SahteSonuc('STARTED'))
        self.assertEqual(yanit.json()['status'], 'started')

    def test_basarili_is_kayit_sayisini_verir(self):
        yanit, _ = self._durum(SahteSonuc('SUCCESS', {'success': True, 'count': 17}))
        govde = yanit.json()
        self.assertEqual(govde['status'], 'success')
        self.assertEqual(govde['count'], 17)
        self.assertNotIn('error', govde)

    def test_yeni_kayit_yoksa_yine_basarili(self):
        """Task'lar yeni kayit bulamayinca success=False ama hata alani olmadan doner."""
        yanit, _ = self._durum(SahteSonuc('SUCCESS', {'success': False, 'count': 0}))
        self.assertEqual(yanit.json()['status'], 'success')
        self.assertEqual(yanit.json()['count'], 0)

    def test_task_icinde_yakalanan_hata_failure_olur(self):
        """news/tasks.py istisnalari yakalayip {'success': False, 'error': ...} doner;
        Celery bunu SUCCESS sayar ama tuketici icin is basarisizdir."""
        hata = 'NOT NULL constraint failed: news_cveentry.updated_at'
        yanit, _ = self._durum(SahteSonuc('SUCCESS', {'success': False, 'error': hata}))
        govde = yanit.json()
        self.assertEqual(govde['status'], 'failure')
        self.assertEqual(govde['error'], hata)
        self.assertNotIn('count', govde)

    def test_celery_failure(self):
        yanit, _ = self._durum(SahteSonuc('FAILURE', RuntimeError('worker coktu')))
        self.assertEqual(yanit.json()['status'], 'failure')
        self.assertIn('worker coktu', yanit.json()['error'])

    def test_bilinmeyen_job_404(self):
        yanit, sahte = self._durum(SahteSonuc('PENDING'), job_id='hic-verilmemis-bir-kimlik')
        self.assertEqual(yanit.status_code, 404)
        self.assertEqual(yanit.json()['error']['code'], 'not_found')
        sahte.assert_not_called()

    def test_proje_celery_uygulamasiyla_sorgular(self):
        from cybernews.celery import app
        _, sahte = self._durum(SahteSonuc('PENDING'))
        sahte.assert_called_once_with(self.job_id, app=app)

    def test_tokensiz_401(self):
        self.assertEqual(self.client.get(f'/api/v1/jobs/{self.job_id}/').status_code, 401)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_jobs -v 2 2>&1 | tail -15`
Expected: FAIL / ERROR — `news.api_v1.views` icinde `AsyncResult` yok (patch hedefi bulunamaz) veya URL 404.

- [ ] **Step 3: View'i yaz**

`news/api_v1/views.py` — import bloguna ekle:

```python
from celery.result import AsyncResult

from cybernews.celery import app as celery_app
```

Dosyanin sonuna ekle:

```python
# Celery durumlari -> sozlesmedeki durumlar
CELERY_DURUMLARI = {
    'PENDING': 'pending',
    'RECEIVED': 'pending',
    'STARTED': 'started',
    'RETRY': 'started',
    'SUCCESS': 'success',
    'FAILURE': 'failure',
    'REVOKED': 'failure',
}


class JobView(V1APIView):
    """Manuel tetiklenen bir isin durumunu dondurur.

    Celery bilinmeyen bir id icin de PENDING dondurdugu icin once job kaydina
    bakilir; kaydi olmayan (hic verilmemis veya 1 gunden eski) kimlik 404'tur.
    """

    def get(self, request, job_id):
        section = refresh.get_gate().job_section(job_id)
        if section is None:
            return _hata('not_found', 'Bilinmeyen veya suresi dolmus is kimligi.',
                         status.HTTP_404_NOT_FOUND)

        sonuc = AsyncResult(job_id, app=celery_app)
        govde = {'job_id': job_id, 'section': section,
                 'status': CELERY_DURUMLARI.get(sonuc.state, 'pending')}

        if govde['status'] == 'success':
            deger = sonuc.result if isinstance(sonuc.result, dict) else {}
            if deger.get('success') is False and deger.get('error'):
                # Task istisnayi yakalayip dondurdu: Celery icin basarili, tuketici icin degil
                govde['status'] = 'failure'
                govde['error'] = str(deger['error'])
            else:
                govde['count'] = deger.get('count', 0)
        elif govde['status'] == 'failure':
            govde['error'] = str(sonuc.result)

        return Response(govde)
```

`news/api_v1/urls.py` — `refresh/` satirinin hemen altina ekle:

```python
    path('jobs/<str:job_id>/', views.JobView.as_view(), name='v1-job'),
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_jobs -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 9 tests`, `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 6: Test anahtarlarinin canli Redis'te kalmadigini dogrula**

Run: `docker compose exec -T teknoloji-redis redis-cli --scan --pattern 'test-refresh-*' | wc -l`
Expected: `0`

- [ ] **Step 7: Commit**

```bash
git add news/api_v1/views.py news/api_v1/urls.py news/tests/test_jobs.py
git commit -m "$(cat <<'MSG'
feat: GET /api/v1/jobs/<id>/ is durumu uc noktasi

Celery durumlarini pending/started/success/failure'a esliyor. Celery
bilinmeyen id icin de PENDING dondurdugu icin once job kaydina bakiliyor;
kaydi olmayan kimlik 404.

news/tasks.py istisnalari yakalayip {'success': False, 'error': ...}
dondurdugu icin bu isler Celery acisindan SUCCESS gorunuyor; uc nokta
bunlari failure olarak raporluyor. Hata alani olmayan success=False
("yeni kayit yok") basari sayiliyor.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 9: Canli dogrulama ve A2 kapanisi

Bu task kod yazmaz; kanit toplar. **Canli sistemde gercek bir cekim baslatir** — uygulamanin normal kullanimidir, ama bolum bilincli olarak en hafifi (DevTools, gozlenen sure 11–33 sn) secilmistir.

**Files:** degistirilmez

**Interfaces:**
- Consumes: Task 1–8
- Produces: A2'nin canlida calistigini gosteren cikti

- [ ] **Step 1: Calisan is olmadigini dogrula**

Yeniden baslatma devam eden bir cekimi yarida keser.

Run: `docker compose exec -T teknoloji-worker celery -A cybernews inspect active 2>&1 | tail -5`
Expected: `- empty -`. Bos degilse is bitene kadar bekle ve tekrar kontrol et.

- [ ] **Step 2: Surecleri yeni kodla yeniden baslat**

```bash
docker compose restart teknoloji-api teknoloji-worker teknoloji-scheduler
```

Sonra worker'in hazir oldugunu bekle:

Run: `docker compose logs --since 1m teknoloji-worker 2>&1 | grep -E "ready|ERROR" | tail -3`
Expected: `celery@... ready.` satiri; `ERROR` yok.

- [ ] **Step 3: Token'i al**

```bash
TOKEN=$(docker compose exec -T teknoloji-api python -c "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings');django.setup();from rest_framework.authtoken.models import Token;print(Token.objects.get(user__username='entegrasyon').key)" | tr -d '\r')
echo "${TOKEN:0:6}..."
```

- [ ] **Step 4: DevTools'u tetikle ve isi sonuna kadar izle**

```bash
docker compose exec -T -e TOKEN="$TOKEN" teknoloji-api python - <<'PY'
import json, os, time, urllib.error, urllib.request

TOKEN = os.environ['TOKEN']
BASE = 'http://localhost:8000'

def istek(yol, method='GET'):
    r = urllib.request.Request(BASE + yol, method=method,
                               headers={'Authorization': 'Token ' + TOKEN})
    try:
        yanit = urllib.request.urlopen(r)
        return yanit.status, dict(yanit.headers), json.load(yanit)
    except urllib.error.HTTPError as hata:
        return hata.code, dict(hata.headers), json.load(hata)

kod, _, govde = istek('/api/v1/devtools/refresh/', 'POST')
print('tetikleme :', kod, govde)
assert kod == 202 and govde['status'] in ('started', 'already_running'), 'tetikleme basarisiz'

gorulen = []
for _ in range(120):
    _, _, durum = istek(govde['status_url'])
    if not gorulen or gorulen[-1] != durum['status']:
        gorulen.append(durum['status'])
    if durum['status'] in ('success', 'failure'):
        break
    time.sleep(2)
print('durum gecisleri:', ' -> '.join(gorulen))
print('son durum      :', durum)

kod, basliklar, ikinci = istek('/api/v1/devtools/refresh/', 'POST')
print('tekrar tetikle :', kod, '| Retry-After:', basliklar.get('Retry-After'), '|', ikinci['error']['code'])

kod, _, bilinmeyen = istek('/api/v1/jobs/olmayan-kimlik/')
print('bilinmeyen job :', kod, bilinmeyen['error']['code'])
PY
```

Expected:
- `tetikleme : 202 {... 'status': 'started' ...}`
- `durum gecisleri:` en az `started -> success` (ilk sorguda `pending` de gorulebilir). **Yalnizca `pending` gorunup zaman asimina ugrarsa Task 1 canliya yansimamistir** — Step 2'deki yeniden baslatmayi kontrol et.
- `son durum` icinde `'status': 'success'` ve bir `count`
- `tekrar tetikle : 429 | Retry-After: <900'e yakin> | cooldown`
- `bilinmeyen job : 404 not_found`

- [ ] **Step 5: Kilidin birakildigini, sogumanin surdugunu dogrula**

```bash
docker compose exec -T teknoloji-redis redis-cli exists refresh:running:devtools
docker compose exec -T teknoloji-redis redis-cli ttl refresh:cooldown:devtools
```

Expected: ilk komut `0` (kilit sinyal tarafindan birakildi); ikinci komut 0'dan buyuk ve 900'den kucuk bir sayi.

- [ ] **Step 6: Worker logunda isin kimligini gor**

Run: `docker compose logs --since 5m teknoloji-worker 2>&1 | grep "fetch_devtools_task" | tail -2`
Expected: Step 4'teki `job_id` ile ayni kimlikte bir `received` ve bir `succeeded` satiri.

- [ ] **Step 7: Eski uc noktalarin ve frontend'in bozulmadigini dogrula**

```bash
curl -s -o /dev/null -w "eski /api/devtools/ -> %{http_code}\n" http://localhost:8000/api/devtools/
curl -s -o /dev/null -w "v1 okuma           -> %{http_code}\n" -H "Authorization: Token $TOKEN" http://localhost:8000/api/v1/devtools/
curl -s -o /dev/null -w "frontend           -> %{http_code}\n" http://localhost:3000/
```

Expected: uc satir da `200`.

- [ ] **Step 8: Tum test paketini son kez kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 9: Dali push et**

```bash
git push -u origin feat/entegrasyon-api-v1-a2
```

---

## A2 Bitis Kriterleri

- [ ] Django surecinde Celery uygulamasi yuklu; `jobs` uc noktasi gercek durumlari goruyor (Task 9 Step 4'te `started -> success` gecisi)
- [ ] Ayni bolum iki kez tetiklenince tek is calisiyor; is bitince kilit kalkiyor, soguma 15 dk suruyor
- [ ] Sogumadaki tetikleme `429` + `Retry-After` donuyor
- [ ] Task icinde yakalanmis hata `failure` olarak raporlaniyor
- [ ] View testleri canli Redis'e yazmiyor; hicbir test gercek is kuyruga atmiyor; test anahtari canli Redis'te kalmiyor
- [ ] Mevcut `/api/*` uc noktalari ve frontend calisiyor
- [ ] Test paketi yesil

## A2 Sonrasi

- **A3:** Ceviri dogrulama (yanki/kirpilma/kalinti), `retranslate_pending_task`, cache duzeltmeleri C1–C5. Spec bolum 9–10. `news/tasks.py` bu adimda degisecek.
- **A5'e not:** README ve Helm `configmap`'ine `REFRESH_COOLDOWN`, `REFRESH_LOCK_TTL` eklenecek; spec 8.2 ve 8.3 bu plandaki netlestirmelere gore guncellenecek.
