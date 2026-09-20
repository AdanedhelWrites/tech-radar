# A4 — `FetchRun` Gorunurlugu ve `GET /api/v1/status/` — Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cekim ve ceviri hattindaki her calistirmayi `FetchRun` satiri olarak kalici hale getirmek, tuketiciye dar bir tazelik ucu (`GET /api/v1/status/`) sunmak ve operator teshisini Django admin'de gorunur kilmak.

**Architecture:** Celery sinyalleri (`task_prerun` / `task_postrun` / `task_failure`) `FetchRun` satirini acip kapatir; task govdeleri degismez, yalnizca donus sozlesmeleri zenginlesir. Proje bu kalibi `news/api_v1/job_signals.py`'de zaten kullaniyor. `/api/v1/status/` yalnizca tuketicinin tazelik sorusunu yanitlar; operator verisi (Gemini butcesi, `by_provider`, `stopped_reason`, `trigger`, `error`) `FetchRun`'da ve admin'de yasar.

**Tech Stack:** Django 4.2.7, DRF 3.17.2, Celery 5.3.4. **Yeni pip/npm bagimliligi yok. Migration VAR (`0011_fetchrun`).**

**Spec:** `docs/superpowers/specs/2026-09-20-a4-fetchrun-ve-status-design.md` — once onu oku. Selefi: `2026-09-12-entegrasyon-api-v1-design.md` bolum 11 (bu spec onun yerine gecer).

**Iliskili kararlar:** [ADR-0003](../../ADR-0003-Entegrasyon-API-v1.md) (v1 sozlesmesi), [ADR-0004](../../ADR-0004-Ceviri-Saglayici-Zinciri.md) (`by_provider`), [ADR-0005](../../ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md) (saklama, `stopped_reason`).

## Global Constraints

- **Migration VAR.** Task 1 `0011_fetchrun` uretir. **Dagitim sirasi (Task 7) zorunludur:** worker ve scheduler durdurulur → `migrate` → api/worker/scheduler yeniden baslatilir. ADR-0003: 2026-09-12'de atlanan yeniden baslatma bir CVE cekimini `NOT NULL` hatasiyla dusurmustu.
- **Durum semantigi (spec 3.2), butun plan boyunca gecerli:** `failure` **yalnizca** istisna veya donuste `error` anahtari oldugunda. `fetched_count > 0, saved_count = 0` → `success` ("yeni kayit yok"). `saved_count = 0` tek basina asla basarisizlik degildir.
- **Sinyal hicbir kosulda task'i dusurmez.** `news/fetch_runs.py`'deki her sinyal govdesi bastan sona `try/except Exception` icindedir; hata yalnizca `print` ile loglanir (`job_signals.py` ile ayni kalip).
- **`FetchRun` v1 delta akisina girmez:** `updated_at` alani yoktur, hicbir delta ucu onu dondurmez.
- **`/api/v1/status/` dar kalir.** Gemini butcesi, rezerve, devre kesici, `by_provider`, `stopped_reason`, `trigger`, `error` bu uca **girmez**. `retranslate` bolumu yanitta **yer almaz**.
- **Mevcut `success` alani korunur.** Alti `fetch_*` task'i `{'success': ..., 'count': ...}` dondurmeye devam eder (frontend ve `api_v1/refresh.py` okuyor); yeni alanlar bunlara **eklenir**.
- Hicbir test gercek aga, gercek Gemini'ye, gercek LibreTranslate'e gitmez; hicbir test gercek Celery isi kuyruga atmaz; `FLUSHDB`/`FLUSHALL` yasak.
- Kod yorumlari **aksansiz Turkce**; kullaniciya gorunen admin metinleri Turkce karakterli olabilir.
- Testler konteyner icinde: `docker compose exec -T teknoloji-api python manage.py test news`
- Her task kendi commit'ini atar; mesaj Turkce, aksansiz, sonu `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` (uygulayan model neyse o).
- **Calisma dali:** `feat/a4-fetchrun-ve-status`, `docs/a4-fetchrun-ve-status` (`953ede8`) uzerinden acilir.
- **Task 7 canli sisteme dokunur** (migration + konteyner yeniden baslatma). Task 7'ye baslamadan kullaniciya haber ver.

## Ortam Notlari

| Konu | Deger |
|---|---|
| Proje / git koku | `cybersecurity_news/` |
| Konteynerlar | `teknoloji-api`, `teknoloji-worker`, `teknoloji-scheduler`, `teknoloji-redis`, `teknoloji-translate`, `teknoloji-frontend` |
| Kod yeniden yukleme | Yok. Python degisikligi → `docker compose restart teknoloji-api teknoloji-worker` |
| Mevcut test sayisi | **268** |
| Son migration | `0010_translation_provider_gemini` |
| Beat takvimi | fetch 00/06/12/18 (10'ar dk arayla), `retranslate_pending_task` tek saatlerde (`minute=5, hour='1-23/2'`) |
| Durum (2026-09-20 19:03) | cve 1015 (%74 gemini), ai 338 (%96), news 97 (%95), kubernetes 57 (%26), devtools 37 (%40), sre 35 (%74) |

## Spec'e Gore Netlestirmeler

Bu bolum spec ile celistiginde gecerlidir.

1. **`trigger` icin cagri bicimi degisir.** `.delay()` Celery header'i kabul etmez; `views.py`'deki alti dagitim satiri `.apply_async(kwargs={...}, headers={...})` bicimine gecer. Gorev imzalari, URL'ler ve HTTP yanitlari degismez.
2. **`retranslate` satirinda `fetched_count = 0` ve `total_after = 0`** (spec 3.4). Bu bolumde `fetched_count = 0` kaynak arizasi anlamina gelmez.
3. **`task_id` → `FetchRun.id` eslemesi surec ici bir sozluktedir**; `FetchRun`'a `task_id` alani eklenmez (spec 3.3).
4. **`error` metni ilk 2000 karaktere kisaltilir** (spec 5).

## Dosya Yapisi

| Dosya | Sorumluluk | Task |
|---|---|---|
| `news/models.py` | `FetchRun` modeli | 1 |
| `news/migrations/0011_fetchrun.py` | Migration | 1 |
| `news/fetch_runs.py` (yeni) | Sinyal iskeleti, bolum haritasi, saklama temizligi | 2 |
| `news/apps.py` | Sinyal modulunun `ready()` icinde import'u | 2 |
| `news/tasks.py` | Zengin donus sozlesmesi + saklama temizligi cagrisi | 3 |
| `news/views.py`, `news/api_v1/refresh.py` | `trigger` header'i | 4 |
| `news/api_v1/views.py`, `news/api_v1/urls.py` | `StatusView` | 5 |
| `news/admin.py` | `FetchRun` kaydi, iki yeni model, filtreler, karsilastirma | 6 |
| `docker-compose.yml` | Degismez (Task 7 yalnizca dagitim) | 7 |

---

### Task 1: `FetchRun` modeli ve migration

**Files:**
- Modify: `news/models.py` (dosya sonuna ekleme; su an 189 satir)
- Create: `news/migrations/0011_fetchrun.py` (`makemigrations` uretir)
- Test: `news/tests/test_fetchrun.py` (yeni)

**Interfaces:**
- Consumes: yok (ilk task)
- Produces: `news.models.FetchRun` — alanlar: `section`, `trigger`, `started_at`, `finished_at`, `status`, `fetched_count`, `saved_count`, `translation_failures`, `total_after`, `by_provider`, `stopped_reason`, `error`

- [ ] **Step 1: Testi yaz**

`news/tests/test_fetchrun.py`:

```python
"""FetchRun modeli ve sinyal iskeleti (spec 2026-09-20-a4, bolum 3.1-3.3)."""
from django.test import TestCase
from django.utils import timezone

from news.models import FetchRun


class FetchRunModelTests(TestCase):

    def test_varsayilanlar(self):
        kayit = FetchRun.objects.create(section='cve', trigger='beat', status='running')

        self.assertEqual(kayit.fetched_count, 0)
        self.assertEqual(kayit.saved_count, 0)
        self.assertEqual(kayit.translation_failures, 0)
        self.assertEqual(kayit.total_after, 0)
        self.assertEqual(kayit.by_provider, {})
        self.assertEqual(kayit.stopped_reason, '')
        self.assertEqual(kayit.error, '')
        self.assertIsNone(kayit.finished_at)
        self.assertIsNotNone(kayit.started_at)

    def test_by_provider_sozluk_saklar(self):
        kayit = FetchRun.objects.create(section='retranslate', trigger='beat', status='success',
                                        by_provider={'gemini': 12, 'libretranslate': 3})
        kayit.refresh_from_db()

        self.assertEqual(kayit.by_provider['gemini'], 12)

    def test_siralama_en_yeni_once(self):
        eski = FetchRun.objects.create(section='cve', trigger='beat', status='success')
        FetchRun.objects.filter(pk=eski.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=1))
        yeni = FetchRun.objects.create(section='cve', trigger='beat', status='success')

        self.assertEqual(list(FetchRun.objects.all())[0].pk, yeni.pk)

    def test_updated_at_alani_yok(self):
        """FetchRun v1 delta akisina girmez; updated_at tasimaz (spec 3.1)."""
        alanlar = {f.name for f in FetchRun._meta.get_fields()}

        self.assertNotIn('updated_at', alanlar)
```

- [ ] **Step 2: Testi calistir, basarisiz oldugunu gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_fetchrun -v 2`
Expected: FAIL — `ImportError: cannot import name 'FetchRun' from 'news.models'`

- [ ] **Step 3: Modeli yaz**

`news/models.py` dosyasinin **sonuna** ekle:

```python
class FetchRun(models.Model):
    """Her cekim ve retranslate calistirmasinin birakti kalici iz (spec 2026-09-20-a4).

    Bu model v1 delta akisina GIRMEZ: `updated_at` alani yoktur ve hicbir
    delta uc noktasi onu dondurmez. Operator teshisi icindir.
    """
    BOLUMLER = [
        ('cve', 'CVE'), ('news', 'Haber'), ('kubernetes', 'Kubernetes'),
        ('sre', 'SRE'), ('devtools', 'DevTools'), ('ai', 'Yapay Zeka'),
        ('retranslate', 'Yeniden Ceviri'),
    ]
    TETIKLEYICILER = [('beat', 'Zamanlayici'), ('api', 'API'), ('admin', 'Arayuz')]
    DURUMLAR = [('running', 'Calisiyor'), ('success', 'Basarili'), ('failure', 'Basarisiz')]

    section = models.CharField(max_length=20, choices=BOLUMLER, db_index=True, verbose_name='Bolum')
    trigger = models.CharField(max_length=10, choices=TETIKLEYICILER, default='beat', verbose_name='Tetikleyici')
    started_at = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name='Baslangic')
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name='Bitis')
    status = models.CharField(max_length=10, choices=DURUMLAR, default='running', verbose_name='Durum')
    fetched_count = models.IntegerField(default=0, verbose_name='Kaynaktan Gelen')
    saved_count = models.IntegerField(default=0, verbose_name='Yazilan')
    translation_failures = models.IntegerField(default=0, verbose_name='Ceviri Hatasi')
    total_after = models.IntegerField(default=0, verbose_name='Tur Sonu Toplam')
    by_provider = models.JSONField(default=dict, blank=True, verbose_name='Saglayici Dagilimi')
    stopped_reason = models.CharField(max_length=30, blank=True, default='', verbose_name='Durma Sebebi')
    error = models.TextField(blank=True, default='', verbose_name='Hata')

    class Meta:
        verbose_name = 'Cekim Kaydi'
        verbose_name_plural = 'Cekim Kayitlari'
        ordering = ['-started_at']
        indexes = [models.Index(fields=['section', '-started_at'])]

    def __str__(self):
        return f'{self.section} {self.started_at:%Y-%m-%d %H:%M} ({self.status})'
```

- [ ] **Step 4: Migration uret**

Run: `docker compose exec -T teknoloji-api python manage.py makemigrations news --name fetchrun`
Expected: `0011_fetchrun.py` olusur ve yalnizca `CreateModel` icerir. **Baska bir modelde degisiklik cikarsa DUR ve bildir** — bu plan yalnizca yeni tablo ekler.

- [ ] **Step 5: Migration'i uygula ve testleri calistir**

Run: `docker compose exec -T teknoloji-api python manage.py migrate news`
Sonra: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_fetchrun -v 2`
Expected: PASS (4 test).

- [ ] **Step 6: Tum paketi calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news`
Expected: `OK`, 272 test (268 + 4).

- [ ] **Step 7: Commit**

```bash
git add news/models.py news/migrations/0011_fetchrun.py news/tests/test_fetchrun.py
git commit -m "feat: FetchRun modeli — her cekim ve retranslate turu kalici iz birakir

Operator teshisi icin: bolum, tetikleyici, sure, durum, sayaclar,
saglayici dagilimi, durma sebebi ve hata. v1 delta akisina girmez
(updated_at alani yok).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: Sinyal iskeleti

**Files:**
- Create: `news/fetch_runs.py`
- Modify: `news/apps.py` (`ready()` icine import)
- Test: `news/tests/test_fetchrun.py` (genisler)

**Interfaces:**
- Consumes: `news.models.FetchRun` (Task 1)
- Produces:
  - `news.fetch_runs.TASK_BOLUMLERI: Dict[str, str]`
  - `news.fetch_runs.BOLUM_MODELLERI: Dict[str, Model]`
  - `news.fetch_runs.eski_kayitlari_temizle(gun: int = 30) -> int`
  - Sinyal islevleri: `tur_basladi`, `tur_bitti`, `tur_coktu`

- [ ] **Step 1: Testi yaz**

`news/tests/test_fetchrun.py` sonuna ekle:

```python
class SinyalTests(TestCase):
    """Sinyal iskeleti (spec 3.3). Gercek Celery isi kuyruga atilmaz;
    sinyal islevleri dogrudan cagrilir."""

    def _sender(self, ad):
        """Celery sender nesnesinin sinyal icin gereken yuzu."""
        class SahteSender:
            name = ad
            request = {}
        return SahteSender()

    def test_prerun_running_satiri_acar(self):
        from news import fetch_runs
        fetch_runs.tur_basladi(sender=self._sender('news.tasks.fetch_cve_task'), task_id='t1')

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.section, 'cve')
        self.assertEqual(kayit.status, 'running')
        self.assertEqual(kayit.trigger, 'beat')
        self.assertIsNone(kayit.finished_at)

    def test_haritada_olmayan_task_satir_acmaz(self):
        from news import fetch_runs
        fetch_runs.tur_basladi(sender=self._sender('celery.backend_cleanup'), task_id='t2')

        self.assertEqual(FetchRun.objects.count(), 0)

    def test_postrun_sayaclari_yazar_ve_kapatir(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t3')

        fetch_runs.tur_bitti(sender=sender, task_id='t3',
                             retval={'success': True, 'count': 7, 'fetched_count': 42,
                                     'translation_failures': 2})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'success')
        self.assertEqual(kayit.saved_count, 7)
        self.assertEqual(kayit.fetched_count, 42)
        self.assertEqual(kayit.translation_failures, 2)
        self.assertIsNotNone(kayit.finished_at)

    def test_yeni_kayit_yoksa_yine_basarili(self):
        """SPEC 1.3 REGRESYONU: fetched>0, saved=0 saglikli bir durumdur."""
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_sre_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t4')

        fetch_runs.tur_bitti(sender=sender, task_id='t4',
                             retval={'success': False, 'count': 0, 'fetched_count': 14,
                                     'translation_failures': 0})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'success',
                         'success=False ama hata yok: yeni kayit yok demektir, basarisizlik degil')
        self.assertEqual(kayit.fetched_count, 14)
        self.assertEqual(kayit.saved_count, 0)

    def test_donuste_error_anahtari_varsa_basarisiz(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t5')

        fetch_runs.tur_bitti(sender=sender, task_id='t5',
                             retval={'success': False, 'error': 'disk I/O error'})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertIn('disk I/O error', kayit.error)

    def test_task_failure_satiri_basarisiz_kapatir(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.retranslate_pending_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t6')

        fetch_runs.tur_coktu(sender=sender, task_id='t6',
                             exception=ValueError('beklenmedik'))

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertIn('beklenmedik', kayit.error)
        self.assertIsNotNone(kayit.finished_at)

    def test_bozuk_retval_sinyali_dusurmez(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t7')

        fetch_runs.tur_bitti(sender=sender, task_id='t7', retval='sozluk degil')

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'success')
        self.assertEqual(kayit.saved_count, 0)

    def test_total_after_bolum_modelinden_sayilir(self):
        from datetime import date
        from news.models import CVEEntry
        from news import fetch_runs
        CVEEntry.objects.create(cve_id='CVE-2026-1', source='NVD', original_title='T',
                                original_description='D', published_date=date(2026, 9, 12),
                                link='https://ornek.test/1')
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t8')

        fetch_runs.tur_bitti(sender=sender, task_id='t8',
                             retval={'success': True, 'count': 1, 'fetched_count': 1})

        self.assertEqual(FetchRun.objects.get().total_after, 1)

    def test_retranslate_alan_eslemesi(self):
        """retranslate donusu farkli anahtarlar tasir (spec 3.4)."""
        from news import fetch_runs
        sender = self._sender('news.tasks.retranslate_pending_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t9')

        fetch_runs.tur_bitti(sender=sender, task_id='t9',
                             retval={'translated': 12, 'upgraded': 40, 'failed': 3,
                                     'stopped_reason': 'gemini_budget',
                                     'by_provider': {'gemini': 52, 'libretranslate': 0}})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.saved_count, 52, 'translated + upgraded')
        self.assertEqual(kayit.translation_failures, 3)
        self.assertEqual(kayit.fetched_count, 0, 'retranslate hicbir kaynaga gitmez')
        self.assertEqual(kayit.total_after, 0, 'retranslate tek bir bolume ait degil')
        self.assertEqual(kayit.stopped_reason, 'gemini_budget')
        self.assertEqual(kayit.by_provider['gemini'], 52)

    def test_trigger_header_dan_okunur(self):
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        sender.request = {'fetchrun_trigger': 'admin'}

        fetch_runs.tur_basladi(sender=sender, task_id='t10')

        self.assertEqual(FetchRun.objects.get().trigger, 'admin')

    def test_uzun_hata_kisaltilir(self):
        """spec bolum 5: error metni ilk 2000 karaktere kisaltilir."""
        from news import fetch_runs
        sender = self._sender('news.tasks.fetch_cve_task')
        fetch_runs.tur_basladi(sender=sender, task_id='t11')

        fetch_runs.tur_bitti(sender=sender, task_id='t11',
                             retval={'success': False, 'error': 'x' * 5000})

        kayit = FetchRun.objects.get()
        self.assertEqual(kayit.status, 'failure')
        self.assertEqual(len(kayit.error), 2000)

    def test_eski_kayitlar_temizlenir(self):
        from news import fetch_runs
        eski = FetchRun.objects.create(section='cve', trigger='beat', status='success')
        FetchRun.objects.filter(pk=eski.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=31))
        yeni = FetchRun.objects.create(section='cve', trigger='beat', status='success')

        silinen = fetch_runs.eski_kayitlari_temizle(gun=30)

        self.assertEqual(silinen, 1)
        self.assertTrue(FetchRun.objects.filter(pk=yeni.pk).exists())
        self.assertFalse(FetchRun.objects.filter(pk=eski.pk).exists())
```

- [ ] **Step 2: Testleri calistir, basarisiz olduklarini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_fetchrun.SinyalTests -v 2`
Expected: FAIL — `ModuleNotFoundError: No module named 'news.fetch_runs'`

- [ ] **Step 3: Sinyal modulunu yaz**

`news/fetch_runs.py` olustur:

```python
"""Celery sinyalleriyle FetchRun satiri acma/kapatma (spec 2026-09-20-a4, bolum 3.3).

Task govdeleri degismez; zengin sayaclar donus sozlesmesinden okunur.
Sinyal hicbir kosulda task'i dusurmez: her govde try/except icindedir ve
hata yalnizca loglanir (news/api_v1/job_signals.py ile ayni kalip).
"""
from datetime import timedelta

from celery.signals import task_failure, task_postrun, task_prerun
from django.utils import timezone

from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, FetchRun, KubernetesEntry, NewsArticle, SREEntry,
)

TASK_BOLUMLERI = {
    'news.tasks.fetch_news_task': 'news',
    'news.tasks.fetch_cve_task': 'cve',
    'news.tasks.fetch_k8s_task': 'kubernetes',
    'news.tasks.fetch_sre_task': 'sre',
    'news.tasks.fetch_devtools_task': 'devtools',
    'news.tasks.fetch_ai_news_task': 'ai',
    'news.tasks.retranslate_pending_task': 'retranslate',
}

BOLUM_MODELLERI = {
    'news': NewsArticle, 'cve': CVEEntry, 'kubernetes': KubernetesEntry,
    'sre': SREEntry, 'devtools': DevToolsEntry, 'ai': AINewsEntry,
}

HATA_TAVANI = 2000

# task_id -> FetchRun.id. Surec icidir: prerun ve postrun ayni worker alt
# surecinde calisir. Surec arada olurse satir 'running' kalir; aranan sinyal budur.
_acik_turlar = {}


def _bolum(sender):
    return TASK_BOLUMLERI.get(getattr(sender, 'name', None))


def _tetikleyici(sender):
    istek = getattr(sender, 'request', None) or {}
    try:
        deger = istek.get('fetchrun_trigger')
    except AttributeError:
        deger = getattr(istek, 'fetchrun_trigger', None)
    return deger if deger in ('beat', 'api', 'admin') else 'beat'


def eski_kayitlari_temizle(gun: int = 30) -> int:
    """Saklama penceresi disindaki FetchRun satirlarini siler. Donus: silinen sayisi."""
    sinir = timezone.now() - timedelta(days=gun)
    silinen, _ = FetchRun.objects.filter(started_at__lt=sinir).delete()
    return silinen


@task_prerun.connect
def tur_basladi(sender=None, task_id=None, **kwargs):
    try:
        bolum = _bolum(sender)
        if not bolum:
            return
        kayit = FetchRun.objects.create(section=bolum, trigger=_tetikleyici(sender), status='running')
        _acik_turlar[task_id] = kayit.id
    except Exception as hata:
        print(f'  [FetchRun] Satir acilamadi ({task_id}): {hata}')


def _kapat(task_id, **alanlar):
    kayit_id = _acik_turlar.pop(task_id, None)
    if kayit_id is None:
        return
    alanlar['finished_at'] = timezone.now()
    FetchRun.objects.filter(pk=kayit_id).update(**alanlar)


@task_postrun.connect
def tur_bitti(sender=None, task_id=None, retval=None, **kwargs):
    try:
        if not _bolum(sender):
            return
        if not isinstance(retval, dict):
            _kapat(task_id, status='success')
            return

        hata = str(retval.get('error') or '')[:HATA_TAVANI]
        bolum = _bolum(sender)
        if bolum == 'retranslate':
            sayaclar = {
                'saved_count': retval.get('translated', 0) + retval.get('upgraded', 0),
                'translation_failures': retval.get('failed', 0),
                'fetched_count': 0,
                'total_after': 0,
                'by_provider': retval.get('by_provider') or {},
                'stopped_reason': retval.get('stopped_reason') or '',
            }
        else:
            model = BOLUM_MODELLERI[bolum]
            sayaclar = {
                'saved_count': retval.get('count', 0),
                'fetched_count': retval.get('fetched_count', 0),
                'translation_failures': retval.get('translation_failures', 0),
                'total_after': model.objects.count(),
            }
        _kapat(task_id, status='failure' if hata else 'success', error=hata, **sayaclar)
    except Exception as hata:
        print(f'  [FetchRun] Satir kapatilamadi ({task_id}): {hata}')


@task_failure.connect
def tur_coktu(sender=None, task_id=None, exception=None, **kwargs):
    try:
        if not _bolum(sender):
            return
        _kapat(task_id, status='failure', error=f'{type(exception).__name__}: {exception}'[:HATA_TAVANI])
    except Exception as hata:
        print(f'  [FetchRun] Cokme yazilamadi ({task_id}): {hata}')
```

- [ ] **Step 4: Sinyali bagla**

`news/apps.py`, `ready()` icine ekle:

```python
    def ready(self):
        # Manuel tetiklenen is bitince bolum kilidini birakan Celery sinyali
        from .api_v1 import job_signals  # noqa: F401
        # Her cekim ve retranslate turunu FetchRun satiri olarak kaydeden sinyaller
        from . import fetch_runs  # noqa: F401
```

- [ ] **Step 5: Testleri calistir, gectiklerini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_fetchrun -v 2`
Expected: PASS (16 test: 4 model + 12 sinyal).

- [ ] **Step 6: Tum paketi calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news`
Expected: `OK`, 284 test (272 + 12). **Mevcut testlerde beklenmedik `FetchRun` satirlari olusabilir** — sinyaller artik her Celery task'inda tetiklenir. Testler gercek Celery isi kuyruga atmadigi icin bunun olmamasi beklenir; bir test kirilirsa DUR ve sebebini bildir.

- [ ] **Step 7: Commit**

```bash
git add news/fetch_runs.py news/apps.py news/tests/test_fetchrun.py
git commit -m "feat: Celery sinyalleriyle FetchRun satiri acma/kapatma

task_prerun satiri acar, task_postrun donus sozlesmesinden sayaclari
okuyup kapatir, task_failure comen turu yakalar. Task govdeleri degismez.

Durum semantigi: failure yalniz istisna veya donuste error anahtari
oldugunda. fetched>0 saved=0 basarilidir (yeni kayit yok) — SRE ve
DevTools bolumleri bugun tam bu durumda.

Sinyal hicbir kosulda task'i dusurmez; hatalar yalnizca loglanir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: Zengin donus sozlesmesi ve saklama temizligi

**Files:**
- Modify: `news/tasks.py` — alti task'in `return` satirlari (`94-95, 139-140, 179-180, 217-218, 257-258, 295-296`) ve `retranslate_pending_task` (satir ~302)
- Test: `news/tests/test_fetchrun.py` (genisler)

**Interfaces:**
- Consumes: `news.fetch_runs.eski_kayitlari_temizle(gun=30)` (Task 2)
- Produces: alti `fetch_*` task'i `{'success', 'count', 'fetched_count', 'translation_failures'}` dondurur

- [ ] **Step 1: Testi yaz**

`news/tests/test_fetchrun.py` sonuna ekle:

```python
class DonusSozlesmesiTests(TestCase):
    """Alti fetch task'i sinyalin ihtiyac duydugu sayaclari dondurmeli."""

    def test_cve_task_fetched_count_dondurur(self):
        from unittest import mock
        from news import tasks
        yama = mock.patch('news.tasks.MultiCVEScraper')
        scraper = yama.start()
        self.addCleanup(yama.stop)
        scraper.return_value.fetch_all_cves.return_value = []

        sonuc = tasks.fetch_cve_task(days=7)

        self.assertIn('fetched_count', sonuc)
        self.assertIn('translation_failures', sonuc)
        self.assertEqual(sonuc['fetched_count'], 0)
        self.assertIn('success', sonuc, 'mevcut alan korunmali')
        self.assertIn('count', sonuc, 'mevcut alan korunmali')

    def test_retranslate_task_eski_kayitlari_temizler(self):
        from unittest import mock
        from news import tasks
        eski = FetchRun.objects.create(section='cve', trigger='beat', status='success')
        FetchRun.objects.filter(pk=eski.pk).update(
            started_at=timezone.now() - timezone.timedelta(days=31))
        with mock.patch('news.retranslate.retranslate_pending', return_value={'translated': 0}):
            tasks.retranslate_pending_task()

        self.assertFalse(FetchRun.objects.filter(pk=eski.pk).exists())
```

- [ ] **Step 2: Testleri calistir, basarisiz olduklarini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_fetchrun.DonusSozlesmesiTests -v 2`
Expected: FAIL — `KeyError`/`AssertionError`: `fetched_count` donuste yok; eski `FetchRun` silinmemis.

- [ ] **Step 3: Donus sozlesmesini zenginlestir**

Alti `fetch_*` task'inda ayni kalip. Ornek (`fetch_cve_task`, satir 88-97 civari) — **alti task icin de ayni sekilde uygula**, degisen yalnizca degisken adlaridir:

```python
        if cves:
            saved_count = 0
            consume_translation_failures()
            consume_translation_providers()
            ceviri_hatalari = 0
            for cve in scraper.process_cves(cves):
                CVEEntry.objects.update_or_create(
                    ...
                )
                saved_count += 1
                ...
            cache_yenile('cve')
            return {'success': True, 'count': saved_count,
                    'fetched_count': len(cves), 'translation_failures': ceviri_hatalari}
        return {'success': False, 'count': 0,
                'fetched_count': 0, 'translation_failures': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

**Onemli iki nokta:**

1. `fetched_count` **`_drop_existing` filtresinden ONCE** sayilmalidir — "kaynaktan kac kayit geldi" sorusunun cevabi odur. Su anki kod `cves`i filtreledikten sonra kullaniyor; filtrelenmemis uzunlugu ayri bir degiskende sakla:

```python
        cves = scraper.fetch_all_cves(days=days, selected_sources=selected_sources)
        kaynaktan_gelen = len(cves)          # <-- _drop_existing'den ONCE
        if skip_existing:
            cves = _drop_existing(cves, CVEEntry, 'cve_id', key='cve_id')
```

ve her iki `return` satirinda `'fetched_count': kaynaktan_gelen` kullan. Bu, spec 1.3'un ayirt etmek istedigi durumun ta kendisidir: `fetched_count > 0, saved_count = 0` = "kaynak calisiyor, yeni kayit yok".

2. `translation_failures`: dongu icinde `consume_translation_failures()` zaten her kayitta cagriliyor ve sayaci sifirliyor. Donguden once `ceviri_hatalari = 0` tanimla ve `needs_translation` hesaplanirken biriktir:

```python
                basarisizlik = consume_translation_failures()
                ceviri_hatalari += basarisizlik
                CVEEntry.objects.update_or_create(
                    cve_id=cve['cve_id'],
                    defaults={
                        ...
                        'needs_translation': basarisizlik > 0,
                        ...
                    }
                )
```

`except` dalindaki `return {'success': False, 'error': str(e)}` **degismez** — sinyal `error` anahtarini gorup `failure` yazar.

- [ ] **Step 4: Saklama temizligini bagla**

`news/tasks.py`, `retranslate_pending_task`:

```python
@shared_task
def retranslate_pending_task():
    """Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir (bkz. news/retranslate.py)."""
    from .fetch_runs import eski_kayitlari_temizle
    from .retranslate import retranslate_pending
    sonuc = retranslate_pending()
    eski_kayitlari_temizle()      # 30 gunden eski FetchRun satirlari (spec 3.4)
    return sonuc
```

- [ ] **Step 5: Testleri calistir, gectiklerini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_fetchrun -v 2`
Expected: PASS (18 test).

- [ ] **Step 6: Tum paketi calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news`
Expected: `OK`, 286 test (284 + 2). `test_saklama.py` ve `test_retranslate.py` bu degisiklikten etkilenmemeli; etkilenirse DUR ve bildir.

- [ ] **Step 7: Commit**

```bash
git add news/tasks.py news/tests/test_fetchrun.py
git commit -m "feat: fetch task'lari fetched_count ve translation_failures dondursun

fetched_count _drop_existing filtresinden ONCE sayilir: 'kaynaktan kac
kayit geldi' sorusunun cevabi odur. Boylece 'kaynak bozuk' (fetched=0)
ile 'yeni kayit yok' (fetched>0, saved=0) ayirt edilebilir hale gelir.

Mevcut success ve count alanlari korunur; frontend ve api_v1/refresh.py
onlari okuyor.

retranslate turu sonunda 30 gunden eski FetchRun satirlari temizlenir.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: `trigger` header'lari

**Files:**
- Modify: `news/views.py` satir `73, 200, 336, 467, 591, 720`
- Modify: `news/api_v1/refresh.py` satir `148`
- Test: `news/tests/test_fetchrun.py` (genisler)

**Interfaces:**
- Consumes: `news.fetch_runs._tetikleyici` header'i `fetchrun_trigger` adiyla okur (Task 2)
- Produces: yok

- [ ] **Step 1: Testi yaz**

`news/tests/test_fetchrun.py` sonuna ekle:

```python
class TetikleyiciTests(TestCase):
    """Manuel tetiklenen isler FetchRun'da beat'ten ayirt edilebilmeli."""

    def test_v1_refresh_api_header_i_gecer(self):
        """news/api_v1/refresh.py::trigger(section, gate=None, ...) -> TriggerResult"""
        import uuid
        from unittest import mock
        from news.api_v1 import refresh
        sahte_gorev = mock.Mock()
        kapi = refresh.RefreshGate(redis_client=None, prefix=f'test-{uuid.uuid4().hex}')
        with mock.patch.object(refresh, 'section_tasks', return_value={'cve': sahte_gorev}):
            refresh.trigger('cve', gate=kapi)

        self.assertTrue(sahte_gorev.apply_async.called)
        self.assertEqual(sahte_gorev.apply_async.call_args.kwargs.get('headers'),
                         {'fetchrun_trigger': 'api'})

    def test_views_admin_header_i_gecer(self):
        """news/views.py::fetch_cves(request) — satir 200'deki dagitim."""
        from unittest import mock
        from rest_framework.test import APIRequestFactory
        from news import views
        istek = APIRequestFactory().post('/api/cve/fetch/', {}, format='json')
        with mock.patch.object(views, 'fetch_cve_task') as gorev:
            views.fetch_cves(istek)

        self.assertTrue(gorev.apply_async.called, 'views artik apply_async kullanmali')
        self.assertEqual(gorev.apply_async.call_args.kwargs.get('headers'),
                         {'fetchrun_trigger': 'admin'})
```

> **`RefreshGate` yapicisinin gercek imzasi** `news/api_v1/refresh.py:41`'dedir; yukaridaki cagri ona uymuyorsa testi imzaya gore duzelt, **beklentiyi degil**: `apply_async` `headers={'fetchrun_trigger': 'api'}` ile cagrilmali. Gerekirse `refresh.get_gate()` yerine mock bir kapi kullan.

- [ ] **Step 2: Testleri calistir, basarisiz olduklarini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_fetchrun.TetikleyiciTests -v 2`
Expected: FAIL — `views` hala `.delay()` kullaniyor, `apply_async.called` False.

- [ ] **Step 3: `views.py`'deki alti dagitimi degistir**

Her biri ayni kalip. Ornek (satir 200):

```python
# ONCE
        fetch_cve_task.delay(days=days, selected_sources=selected_sources)
# SONRA
        fetch_cve_task.apply_async(
            kwargs={'days': days, 'selected_sources': selected_sources},
            headers={'fetchrun_trigger': 'admin'})
```

Alti satirin tamami (`73, 200, 336, 467, 591, 720`). Satir 73 ek parametre tasir:

```python
        fetch_news_task.apply_async(
            kwargs={'days': days, 'selected_sources': selected_sources, 'clear_existing': False},
            headers={'fetchrun_trigger': 'admin'})
```

**Gorev imzalari, URL'ler ve HTTP yanitlari degismez.**

- [ ] **Step 4: `refresh.py`'ye header ekle**

`news/api_v1/refresh.py:148`:

```python
        section_tasks()[section].apply_async(
            kwargs={'skip_existing': True}, task_id=job_id,
            headers={'fetchrun_trigger': 'api'})
```

- [ ] **Step 5: Testleri calistir, gectiklerini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_fetchrun -v 2`
Expected: PASS.

- [ ] **Step 6: Tum paketi calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news`
Expected: `OK`, 288 test. **`test_refresh.py` ve `test_jobs.py` `apply_async` cagrisini mock'luyor olabilir** — kirilirsa mock beklentisini `headers` alacak sekilde guncelle, test govdesini degil.

- [ ] **Step 7: Commit**

```bash
git add news/views.py news/api_v1/refresh.py news/tests/test_fetchrun.py
git commit -m "feat: manuel tetiklenen cekimler FetchRun'da trigger ile isaretlensin

views.py alti dagitim satiri .delay yerine .apply_async kullanir
(.delay header kabul etmiyor); v1 refresh yolu api, arayuz yolu admin
olarak isaretlenir, Beat varsayilan beat kalir.

Gorev imzalari, URL'ler ve HTTP yanitlari degismedi.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: `GET /api/v1/status/`

**Files:**
- Modify: `news/api_v1/views.py` (dosya sonuna `StatusView`), `news/api_v1/urls.py`
- Test: `news/tests/test_status.py` (yeni)

**Interfaces:**
- Consumes: `news.models.FetchRun` (Task 1), `news.fetch_runs.BOLUM_MODELLERI` (Task 2)
- Produces: `GET /api/v1/status/` → `{'generated_at': str, 'sections': {...}}`

- [ ] **Step 1: Testi yaz**

`news/tests/test_status.py`:

```python
"""GET /api/v1/status/ (spec 2026-09-20-a4, bolum 3.5)."""
from datetime import date

from django.urls import reverse
from django.utils import timezone

from news.models import CVEEntry, FetchRun
from news.tests.base import V1TestCase


class StatusViewTests(V1TestCase):

    def test_tokensiz_401(self):
        yanit = self.client.get('/api/v1/status/')

        self.assertEqual(yanit.status_code, 401)
        self.assertEqual(yanit.json()['error']['code'], 'unauthorized')

    def test_hic_fetchrun_yokken_200_ve_null(self):
        yanit = self.client.get('/api/v1/status/', **self.token_basligi())

        self.assertEqual(yanit.status_code, 200)
        cve = yanit.json()['sections']['cve']
        self.assertIsNone(cve['last_success_at'])
        self.assertIsNone(cve['last_status'])
        self.assertEqual(cve['total'], 0)

    def test_son_basarili_cekimi_ve_sayilari_dondurur(self):
        CVEEntry.objects.create(cve_id='CVE-2026-1', source='NVD', original_title='T',
                                original_description='D', published_date=date(2026, 9, 12),
                                link='https://ornek.test/1', needs_translation=True)
        FetchRun.objects.create(section='cve', trigger='beat', status='success',
                                fetched_count=268, saved_count=37,
                                finished_at=timezone.now())

        yanit = self.client.get('/api/v1/status/', **self.token_basligi())

        cve = yanit.json()['sections']['cve']
        self.assertEqual(cve['last_status'], 'success')
        self.assertEqual(cve['last_fetched_count'], 268)
        self.assertEqual(cve['last_saved_count'], 37)
        self.assertEqual(cve['pending_translation'], 1)
        self.assertEqual(cve['total'], 1)
        self.assertIsNotNone(cve['last_success_at'])

    def test_basarisiz_tur_last_success_at_i_ilerletmez(self):
        FetchRun.objects.create(section='cve', trigger='beat', status='failure',
                                error='disk I/O error', finished_at=timezone.now())

        cve = self.client.get('/api/v1/status/', **self.token_basligi()).json()['sections']['cve']

        self.assertEqual(cve['last_status'], 'failure')
        self.assertIsNone(cve['last_success_at'], 'son BASARILI cekim yok')

    def test_retranslate_bolumu_yanitta_yer_almaz(self):
        FetchRun.objects.create(section='retranslate', trigger='beat', status='success',
                                finished_at=timezone.now())

        bolumler = self.client.get('/api/v1/status/', **self.token_basligi()).json()['sections']

        self.assertNotIn('retranslate', bolumler)
        self.assertEqual(set(bolumler), {'cve', 'news', 'kubernetes', 'sre', 'devtools', 'ai'})

    def test_operator_alanlari_yanitta_yok(self):
        """Dar sozlesme: Gemini butcesi, by_provider, stopped_reason, trigger, error girmez."""
        FetchRun.objects.create(section='cve', trigger='admin', status='failure',
                                error='gizli', stopped_reason='gemini_budget',
                                by_provider={'gemini': 5}, finished_at=timezone.now())

        govde = self.client.get('/api/v1/status/', **self.token_basligi()).json()

        ham = str(govde)
        for yasak in ('by_provider', 'stopped_reason', 'trigger', 'gizli', 'gemini', 'circuit_open'):
            self.assertNotIn(yasak, ham, f'{yasak} dar sozlesmeye girmemeli')
```

- [ ] **Step 2: Testleri calistir, basarisiz olduklarini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_status -v 2`
Expected: FAIL — 404 (uc nokta yok).

- [ ] **Step 3: `StatusView`'i yaz**

`news/api_v1/views.py` sonuna ekle:

```python
class StatusView(V1APIView):
    """Veri tazeligi raporu (spec 2026-09-20-a4, bolum 3.5).

    Bilincli olarak DARDIR: yalnizca tuketicinin "veri bayat mi" sorusunu
    yanitlar. Operator verisi (Gemini butcesi, by_provider, stopped_reason,
    trigger, error) buraya girmez; o FetchRun'da ve admin'dedir.
    """

    def get(self, request):
        from django.utils import timezone

        from news.fetch_runs import BOLUM_MODELLERI
        from news.models import FetchRun

        bolumler = {}
        for ad, model in BOLUM_MODELLERI.items():
            son = FetchRun.objects.filter(section=ad).first()
            son_basarili = FetchRun.objects.filter(section=ad, status='success').first()
            bolumler[ad] = {
                'last_success_at': son_basarili.finished_at if son_basarili else None,
                'last_status': son.status if son else None,
                'last_fetched_count': son.fetched_count if son else None,
                'last_saved_count': son.saved_count if son else None,
                'pending_translation': model.objects.filter(needs_translation=True).count(),
                'total': model.objects.count(),
            }
        return Response({'generated_at': timezone.now(), 'sections': bolumler})
```

- [ ] **Step 4: URL'i ekle**

`news/api_v1/urls.py`, `health/` satirinin altina:

```python
    path('status/', views.StatusView.as_view(), name='v1-status'),
```

- [ ] **Step 5: Testleri calistir, gectiklerini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_status -v 2`
Expected: PASS (6 test).

- [ ] **Step 6: Tum paketi calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news`
Expected: `OK`, 294 test (288 + 6).

- [ ] **Step 7: Commit**

```bash
git add news/api_v1/views.py news/api_v1/urls.py news/tests/test_status.py
git commit -m "feat: GET /api/v1/status/ — tuketici icin veri tazeligi raporu

Bolum basina son cekim durumu, son basarili cekim zamani, kaynaktan
gelen/yazilan sayilari, bekleyen ceviri ve toplam kayit.

Bilincli olarak dar: Gemini butcesi, by_provider, stopped_reason,
trigger ve error bu uca girmez; operator verisi FetchRun ve admin'de.
retranslate bolumu yanitta yer almaz.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Admin duzeltmeleri

**Files:**
- Modify: `news/admin.py` (su an yalnizca 4 model kayitli)
- Test: `news/tests/test_admin.py` (yeni)

**Interfaces:**
- Consumes: `news.models.FetchRun` (Task 1)
- Produces: yok

- [ ] **Step 1: Testi yaz**

`news/tests/test_admin.py`:

```python
"""Admin duzeltmeleri (spec 2026-09-20-a4, bolum 3.6)."""
from datetime import date

from django.contrib import admin
from django.test import TestCase

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, FetchRun, KubernetesEntry, NewsArticle, SREEntry,
)


class AdminKayitTests(TestCase):

    def test_alti_model_ve_fetchrun_kayitli(self):
        for model in (NewsArticle, CVEEntry, KubernetesEntry, SREEntry,
                      DevToolsEntry, AINewsEntry, FetchRun):
            with self.subTest(model=model.__name__):
                self.assertIn(model, admin.site._registry)

    def test_fetchrun_salt_okunur(self):
        admin_sinifi = admin.site._registry[FetchRun]

        self.assertFalse(admin_sinifi.has_add_permission(None))
        self.assertFalse(admin_sinifi.has_change_permission(None))

    def test_alti_modelde_ceviri_filtreleri_var(self):
        for model in (NewsArticle, CVEEntry, KubernetesEntry, SREEntry,
                      DevToolsEntry, AINewsEntry):
            with self.subTest(model=model.__name__):
                filtreler = admin.site._registry[model].list_filter
                self.assertIn('needs_translation', filtreler)
                self.assertIn('translation_provider', filtreler)

    def test_karsilastirma_alani_iki_metni_de_icerir(self):
        kayit = CVEEntry.objects.create(
            cve_id='CVE-2026-1', source='NVD', original_title='Original title',
            original_description='A remote attacker can read files.',
            turkish_description='Uzaktaki bir saldirgan dosyalari okuyabilir.',
            published_date=date(2026, 9, 12), link='https://ornek.test/1')

        html = admin.site._registry[CVEEntry].karsilastirma(kayit)

        self.assertIn('A remote attacker can read files.', html)
        self.assertIn('Uzaktaki bir saldirgan dosyalari okuyabilir.', html)
```

- [ ] **Step 2: Testleri calistir, basarisiz olduklarini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_admin -v 2`
Expected: FAIL — `DevToolsEntry`, `AINewsEntry` ve `FetchRun` kayitli degil; `karsilastirma` yok.

- [ ] **Step 3: Admin'i yaz**

`news/admin.py` bastan yaz:

```python
from django.contrib import admin
from django.utils.html import format_html

from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, FetchRun, KubernetesEntry, NewsArticle, SREEntry,
)


class CeviriKarsilastirmaMixin:
    """Orijinal ve Turkce metni detay sayfasinda yan yana gosterir (spec 3.6).

    Anlam kaymasi hicbir otomatik kontrolle yakalanamaz (ADR-0003 bolum 11.5);
    bu yuzden gozle karsilastirma yolu acik tutulur. Turkce alanlar duzenlenebilir
    kalir, karsilastirma bloku salt okunurdur.
    """

    @admin.display(description='Orijinal / Turkce karsilastirma')
    def karsilastirma(self, kayit):
        satirlar = [
            ('Baslik', kayit.original_title or '', getattr(kayit, 'turkish_title', '') or ''),
            ('Aciklama', kayit.original_description or '', kayit.turkish_description or ''),
        ]
        hucreler = ''.join(
            '<tr>'
            '<th style="text-align:left;vertical-align:top;padding:4px 8px;">{}</th>'
            '<td style="vertical-align:top;padding:4px 8px;width:45%;">{}</td>'
            '<td style="vertical-align:top;padding:4px 8px;width:45%;">{}</td>'
            '</tr>'.format(ad, orijinal, turkce)
            for ad, orijinal, turkce in satirlar
        )
        return format_html(
            '<table style="width:100%;border-collapse:collapse;">'
            '<tr><th></th><th style="text-align:left;">Orijinal</th>'
            '<th style="text-align:left;">Turkce</th></tr>{}</table>',
            format_html(hucreler))

    @admin.display(description='Turkce baslik')
    def baslik_onizleme(self, kayit):
        metin = getattr(kayit, 'turkish_title', '') or kayit.original_title or ''
        return metin[:80] + ('...' if len(metin) > 80 else '')


CEVIRI_FILTRELERI = ('needs_translation', 'translation_provider')


@admin.register(NewsArticle)
class NewsArticleAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('baslik_onizleme', 'source', 'translation_provider', 'date', 'created_at')
    list_filter = ('source', 'date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'date'


@admin.register(CVEEntry)
class CVEEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('cve_id', 'source', 'severity', 'cvss_score', 'translation_provider', 'published_date')
    list_filter = ('source', 'severity', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('cve_id', 'turkish_title', 'original_title', 'turkish_description')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(KubernetesEntry)
class KubernetesEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('baslik_onizleme', 'source', 'category', 'version', 'translation_provider', 'published_date')
    list_filter = ('source', 'category', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description', 'version')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(SREEntry)
class SREEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('baslik_onizleme', 'source', 'translation_provider', 'published_date', 'created_at')
    list_filter = ('source', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(DevToolsEntry)
class DevToolsEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    # DevToolsEntry ayrica version ve entry_type tasir (models.py:130-152)
    list_display = ('baslik_onizleme', 'source', 'entry_type', 'version',
                    'translation_provider', 'published_date')
    list_filter = ('source', 'entry_type', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description', 'version')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(AINewsEntry)
class AINewsEntryAdmin(CeviriKarsilastirmaMixin, admin.ModelAdmin):
    list_display = ('baslik_onizleme', 'source', 'translation_provider', 'published_date', 'created_at')
    list_filter = ('source', 'published_date', 'created_at') + CEVIRI_FILTRELERI
    search_fields = ('turkish_title', 'original_title', 'turkish_description')
    readonly_fields = ('created_at', 'karsilastirma')
    date_hierarchy = 'published_date'


@admin.register(FetchRun)
class FetchRunAdmin(admin.ModelAdmin):
    """Salt okunur teshis ekrani; satirlari sinyaller yazar (spec 3.3)."""
    list_display = ('section', 'status', 'trigger', 'started_at', 'sure',
                    'fetched_count', 'saved_count', 'total_after', 'stopped_reason')
    list_filter = ('section', 'status', 'trigger', 'started_at')
    search_fields = ('error',)
    date_hierarchy = 'started_at'

    @admin.display(description='Sure')
    def sure(self, kayit):
        if not kayit.finished_at:
            return 'devam ediyor'
        return f'{(kayit.finished_at - kayit.started_at).total_seconds():.0f} sn'

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False
```

> Alan adlari `news/models.py`'den dogrulanmistir: `DevToolsEntry` → `version`, `entry_type`; `AINewsEntry` → ek alan yok; `KubernetesEntry` → `category`, `version`. `AINewsEntry` icin yukaridaki blok oldugu gibi kullanilir, ek sutun eklenmez.

- [ ] **Step 4: Testleri calistir, gectiklerini gor**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_admin -v 2`
Expected: PASS (4 test).

- [ ] **Step 5: Django kontrolu**

Run: `docker compose exec -T teknoloji-api python manage.py check`
Expected: `System check identified no issues`. `admin.E108`/`E116` gibi hatalar yanlis alan adi demektir.

- [ ] **Step 6: Tum paketi calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news`
Expected: `OK`, 298 test (294 + 4).

- [ ] **Step 7: Commit**

```bash
git add news/admin.py news/tests/test_admin.py
git commit -m "feat: admin — FetchRun ekrani, iki eksik model, ceviri karsilastirmasi

FetchRun salt okunur teshis ekrani olarak kaydedildi (bolum/durum/
tetikleyici/tarih filtreli, sure hesapli). DevToolsEntry ve AINewsEntry
admin'de hic gorunmuyordu, eklendi.

Alti modelde needs_translation ve translation_provider filtrelendi;
detay sayfasina salt okunur orijinal/Turkce karsilastirma bloku,
listeye 80 karakterlik baslik onizlemesi eklendi. Anlam kaymasi
otomatik yakalanamadigi icin gozle karsilastirma yolu (ADR-0003 11.5).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 7: Dagitim ve canli dogrulama

**Bu task canli sisteme dokunur ve MIGRATION icerir. Baslamadan kullaniciya haber ver.**

**Files:** yok (dagitim adimi)

**Interfaces:**
- Consumes: Task 1-6'nin tamami
- Produces: yok

- [ ] **Step 1: Dagitim oncesi durumu kaydet**

```bash
docker compose exec -T teknoloji-api python manage.py showmigrations news | tail -3
docker compose exec -T teknoloji-api python manage.py shell -c "
from news.models import CVEEntry
print('CVE satir:', CVEEntry.objects.count())
"
```

- [ ] **Step 2: Worker ve scheduler'i durdur**

Migration yeni tablo eklerken calisan bir task yari yolda kalmasin:

```bash
docker compose stop teknoloji-worker teknoloji-scheduler
```

- [ ] **Step 3: Migration'i uygula**

```bash
docker compose exec -T teknoloji-api python manage.py migrate news
```

Expected: `Applying news.0011_fetchrun... OK`

- [ ] **Step 4: Uc servisi de yeniden baslat**

Bind mount kodu yeniden yuklemez; sinyal modulu `ready()` icinde yuklendigi icin **worker'in yeniden baslamasi zorunludur**:

```bash
docker compose restart teknoloji-api
docker compose start teknoloji-worker teknoloji-scheduler
```

- [ ] **Step 5: Saglik kontrolu**

```bash
docker compose ps --format "table {{.Name}}\t{{.Status}}"
curl -s -o /dev/null -w "health: %{http_code}\n" http://localhost:8000/api/v1/health/
docker compose exec -T teknoloji-api python manage.py shell -c "
from news.fetch_runs import TASK_BOLUMLERI, BOLUM_MODELLERI
from news.models import FetchRun
print('sinyal modulu yuklu, bolum sayisi:', len(TASK_BOLUMLERI))
print('FetchRun tablosu erisilebilir:', FetchRun.objects.count())
"
```

- [ ] **Step 6: Bir cekim tetikle ve satirin olustugunu dogrula**

```bash
docker compose exec -T teknoloji-api python manage.py shell -c "
from news.tasks import fetch_sre_task
print('sonuc:', fetch_sre_task(days=30))
"
docker compose exec -T teknoloji-api python manage.py shell -c "
from news.models import FetchRun
for k in FetchRun.objects.all()[:5]:
    print(k.section, k.status, k.trigger, 'fetched=', k.fetched_count, 'saved=', k.saved_count, 'total=', k.total_after)
"
```

> Bu cagri task'i **dogrudan** calistirir, yani Celery sinyalleri tetiklenmez ve `FetchRun` satiri olusmaz. Satirin olusmasi icin `.apply_async()` ile kuyruga atilmasi veya Beat turunun beklenmesi gerekir. Dogrulamayi Step 7'ye birak; bu adim yalnizca donus sozlesmesinin zenginlestigini gosterir (`fetched_count` ve `translation_failures` anahtarlari yanitta olmali).

- [ ] **Step 7: Bir Beat turunu bekle ve spec bolum 7 hedeflerini dogrula**

Sonraki fetch slotundan (00/06/12/18 + dakika) sonra:

```bash
docker compose exec -T teknoloji-api python manage.py shell -c "
from news.models import FetchRun
print(f\"{'bolum':12}{'durum':9}{'tetik':7}{'fetched':>8}{'saved':>7}{'total':>7}\")
for k in FetchRun.objects.all()[:10]:
    print(f'{k.section:12}{k.status:9}{k.trigger:7}{k.fetched_count:8}{k.saved_count:7}{k.total_after:7}')
"
```

Kabul kriterleri (spec bolum 7):
1. Alti bolum icin birer satir olusmus, `trigger='beat'`.
2. Arayuzden "Getir" tetiklenince olusan satirin `trigger`'i `admin`.
3. **SRE ve DevTools satirlari `status='success'` ve `fetched_count > 0, saved_count = 0`** — spec 1.3'un dogrulanmasi; bu iki bolum `failure` gorunuyorsa durum semantigi yanlis uygulanmistir.
4. `/api/v1/status/` yanitindaki `total` degerleri veritabanindaki gercek sayilarla birebir uyusuyor.
5. Admin'de bir CVE kaydinin detayinda orijinal ve Turkce metin yan yana okunuyor.

- [ ] **Step 8: `/api/v1/status/`'u canlida dogrula**

```bash
TOK=$(docker compose exec -T teknoloji-api python manage.py shell -c "
from rest_framework.authtoken.models import Token
print(Token.objects.first().key)" 2>/dev/null | tr -d '\r' | tail -1)
curl -s -H "Authorization: Token $TOK" http://localhost:8000/api/v1/status/ | python -m json.tool
```

Expected: 200; alti bolum; `retranslate` yok; `by_provider`/`stopped_reason`/`trigger`/`error` yok.

---

## Sonrasi

- **ADR-0006 (veya ADR-0003 eki):** A4 uygulandiginda karar kaydi yazilir; selef spec bolum 11'in bu dokumanla degistirildigi ve durum semantigi karari (spec 1.3) not edilir.
- **A5:** drf-spectacular semasi, `/api/v1/docs/`, ornek istemci, README. `id` yerine `cve_id`/`link` uzerinden upsert kurali orada yazili hale gelir (ADR-0005 8.1).
- **SRE/DevTools kaynak incelemesi:** A4'un urettigi `FetchRun` verisiyle, bu kaynaklarin gercekten yeni icerik uretip uretmedigi ayri bir is olarak ele alinir.
- **Alarm/bildirim:** `FetchRun` veriyi uretir; esik asildiginda bildirim gondermek ayri bir karardir.
