# Ceviri Saglayici Zinciri — Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ucretsiz Google ucu kapaliyken haberlerin yerel LibreTranslate servisiyle aninda Turkceye cevrilmesi; her kaydin hangi saglayiciyla cevrildiginin saklanmasi, API ve frontend'de gosterilmesi ve Google acilinca otomatik yukseltilmesi.

**Architecture:** `translation_utils.translate_text` her metin icin `translation_providers.SAGLAYICILAR` sirasini (Google → LibreTranslate) dener; her denemede A3 dogrulamasi calisir, basarisiz olan bir sonrakine duser. Task'lar ve `retranslate_pending` kullanilan saglayicilari `consume_translation_providers()` ile toplayip kayda `translation_provider` olarak yazar. `retranslate_pending` iki asamalidir: bekleyenleri tam zincirle cevirir, LibreTranslate cevirilerini yalnizca Google ile yukseltir.

**Tech Stack:** Django 4.2.7, DRF 3.17.2, Celery 5.3.4, django-redis, requests 2.31.0 (zaten bagimlilik), React 18 + react-bootstrap (Vite 5), `libretranslate/libretranslate:v1.9.6`. **Yeni pip veya npm bagimliligi yok.**

**Spec:** `docs/superpowers/specs/2026-09-14-ceviri-saglayici-zinciri-design.md` — once onu oku. Bu plan spec'ten 10 noktada ayrilir; hepsi asagida "Spec'e Gore Netlestirmeler" altinda.

## Global Constraints

- **Hicbir test gercek Google'a veya gercek LibreTranslate'e gitmez.** LibreTranslate HTTP cagrilari `mock.patch('news.translation_providers.requests.post')` ile; zincir ve retranslate testleri `SahteSaglayici` ile yazilir (Task 4).
- **Task 1 bitmeden baska task'a baslama.** Dagitimdan sonra API konteynerinde `LIBRETRANSLATE_URL` tanimli olacak; Task 1'deki test calistiricisi olmadan mevcut testler sahte Google basarisiz olunca gercek LibreTranslate'e istek atar.
- **Hicbir test gercek Celery isi kuyruga atmaz.** `FLUSHDB`/`FLUSHALL` yasak; Redis anahtari yazan testler benzersiz onek kullanir ve siler.
- **Saglayici adlari sabittir:** `'google'`, `'libretranslate'`. Veritabanina, API'ye ve frontend'e bu degerler gider. Saglayici yoksa veritabaninda `''`, v1'de `null`.
- **Kullanici secimleri (spec durum satiri):** yukseltme hepsi-ya-da-hicbiri; eski cevrilmis kayitlar sessizce `google` (`updated_at` ilerlemez); bekleyen sinir 100, yukseltme siniri 5 (bolum basina); LibreTranslate `cpus: '4'`, `mem_limit: 2g`.
- **LibreTranslate parca siniri 160 karakter**, zaman asimi 60 sn, devre kesici 60 sn.
- **Kod yorumlari aksansiz Turkce; frontend kullanici metinleri Turkce karakterli** (mevcut bilesen kalibi: "Haber Detayı").
- **`news/views.py` ve `/api/*` URL'leri degismez.**
- **Testler konteyner icinde:** `docker compose exec -T teknoloji-api python manage.py test news`
- **Her task kendi commit'ini atar**; mesaj sonu `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` (uygulayan model neyse o).
- **Calisma dali:** `feat/ceviri-saglayici-zinciri`, bu planin ve spec'in bulundugu `docs/ceviri-saglayici-zinciri` dali `main`'e alindiktan sonra guncel `main`'den acilir.
- **Task 11 canli sisteme dokunur** (migration, konteyner yeniden olusturma, gercek ceviri). Task 11'e baslamadan kullaniciya haber ver.

## Ortam Notlari

| Konu | Deger |
|---|---|
| Proje / git koku | `cybersecurity_news/` |
| Konteynerlar | `teknoloji-api` (gunicorn), `teknoloji-worker`, `teknoloji-scheduler`, `teknoloji-redis`, `teknoloji-frontend` (Vite dev), yeni: `teknoloji-translate` |
| Kod yeniden yukleme | Yok. Kod degisikliginden sonra yeniden baslatma; **ortam degiskeni degisikliginden sonra `docker compose up -d --force-recreate`** (`restart` yeni ortami almaz) |
| Mevcut test sayisi | 140 (~3 sn) |
| Son migration | `0008_updated_at` |
| LibreTranslate imaji | `libretranslate/libretranslate:v1.9.6` yerelde mevcut (600 MB); icinde Python 3.11 var; kullanici `libretranslate`, `/home/libretranslate/.local` imajda mevcut ve ona ait — isimli volume sahipligi devralir (dogrulandi) |
| Modeller | Imajda yok; ilk acilista `en_tr` + `tr_en` iner (258 MB) |
| Ceviri durumu (2026-09-14) | 1035 kaydin 622'si bekleyen; Google "too many requests" |

## Mevcut Kodda Dikkat Edilecekler

1. **~30 test Google mantigini `translation_utils` modul adlari uzerinden mock'luyor:** `tu._gate`, `tu._get_gate`, `tu._make_translator`, `tu._translate_via_google`, `tu.MIN_INTERVAL`, `tu.RETRY_DELAYS`, `tu.COOLDOWN_SECONDS`. Bunlar yerinde kalmalidir.
2. **Mevcut testler canli Redis'teki `translate:cooldown` anahtarini okuyabiliyor.** `TranslationGateMixin` kullanmayan bir test `tu._get_gate()` ile canli devre kesici durumuna bakar; Google canlida kisitliyken bu test sonucu degistirir. Task 1 bunu kapatir.
3. **`retranslate_pending` donus sozlugundeki `stopped_by_cooldown` anahtari `stopped` olur**; `news/tests/test_retranslate.py`'de 3 yerde geciyor, Task 7 gunceller.
4. **`SerializerBicimTests.test_ortak_alanlar_ve_ic_ice_dil` alan kumesini birebir kontrol ediyor** (`news/tests/test_filters.py`), Task 8 gunceller.
5. **`CacheSurumuTests` surum 2'yi kontrol ediyor** (`news/tests/test_cache.py`), Task 8 3 yapar.
6. **Migration `NOT NULL` sutun ekler.** Migration uygulanirken eski kodla calisan bir worker yeni kayit eklerse `NOT NULL constraint failed` ile patlar (2026-09-12'de `updated_at` icin tam olarak bu oldu). Task 11 worker ve scheduler'i migration'dan **once** durdurur.

## Spec'e Gore Netlestirmeler

1. **Google mantigi `translation_providers.py`'ye tasinmaz.** Spec 4.1 "aynen tasinir" diyordu. Tasinsaydi mevcut ~30 testin mock noktalari sessizce bosa duserdi. `GoogleProvider` cagri aninda `translation_utils`'e basvuran ince bir sarmalayicidir; davranis birebir aynidir.
2. **`translate_text(metin, providers=...)` parametresi yerine `yalnizca_saglayicilar('google')` baglam yoneticisi.** Retranslate'in cevirici fonksiyonlari `translate_long_text`'i ve K8s `_translate_structured_changelog`'u cagiriyor; bu ic ice cagrilara parametre gecirilemez. Baglam yoneticisi hepsini kapsar.
3. **Proje test calistiricisi (`news/test_runner.py`) eklenir.** Testlerde `LIBRETRANSLATE_URL` bos ve Google/LibreTranslate devre kesicileri surec icidir. Spec'te yoktu; dagitimdan sonra zorunlu.
4. **LibreTranslate 4xx cevabi:** `None` doner, devre kesici **acmaz** (istek sorunudur, servis ayakta). Spec yalnizca baglanti hatasi/zaman asimi/5xx'i tanimliyordu.
5. **Bosluksuz uzun metinde sert kesim yer tutucuyu bolmez.** 160 karakterde hic bosluk yoksa kesim noktasi, sinira tasan bir `XTRM` kodunun basina cekilir.
6. **Bir saglayici `translate` icinde beklenmeyen istisna firlatirsa zincir bir sonrakine gecer** (spec'te tek bir dis `try` vardi; tek saglayicinin hatasi zinciri kesmemeli).
7. **Dagitim sirasi:** worker ve scheduler migration'dan once durdurulur (bkz. "Dikkat Edilecekler" 6).
8. **`LIBRETRANSLATE_URL` scheduler'a eklenmez**; scheduler ceviri yapmaz.
9. **`by_provider` yalnizca bekleyen asamasinin cevirilerini sayar**; yukseltmeler `upgraded` alaninda.
10. **Frontend etiketi ortak bir bilesen:** `frontend/src/components/MakineCevirisiEtiketi.jsx`. Spec 7.3 alti bilesene ayri ayri eklemeyi tarif ediyordu; ortak bilesen metnin tek yerde durmasini saglar.

## Dosya Yapisi

**Olusturulacak:**

| Dosya | Sorumluluk |
|---|---|
| `news/test_runner.py` | Testlerde LibreTranslate'i kapatir, devre kesicileri surec ici yapar |
| `news/translation_providers.py` | `GoogleProvider`, `LibreTranslateProvider`, metin parcalama/birlestirme, `SAGLAYICILAR` |
| `news/migrations/0009_translation_provider.py` | Alan + eski cevirileri `google` isaretleme |
| `news/tests/saglayici_yardimcilari.py` | `SahteSaglayici`, `SaglayiciZinciriMixin` |
| `news/tests/test_translation_providers.py` | Parcalama, LibreTranslate HTTP davranisi, Google sarmalayici |
| `news/tests/test_translation_chain.py` | Zincir sirasi, dusme, kisit, kayit saglayicisi, fetch task'inin alani yazmasi |
| `news/tests/test_migrations_0009.py` | Veri migration'i |
| `frontend/src/components/MakineCevirisiEtiketi.jsx` | "Makine çevirisi" etiketi (JSX + HTML disa aktarma) |

**Degistirilecek:**

| Dosya | Degisiklik |
|---|---|
| `cybernews/settings.py` | `LIBRETRANSLATE_URL`, `TEST_RUNNER`, cache `VERSION` 3 |
| `news/translation_utils.py` | Tanimlayici korumasi; zincirli `translate_text`; saglayici sayaci, kisit, hazirlik |
| `news/models.py` | Alti modele `translation_provider` |
| `news/tasks.py` | Alti task alani yazar |
| `news/retranslate.py` | Iki asama, yeni sinirlar, yeni donus bicimi |
| `news/api_v1/serializers.py` | `translation_provider` alani |
| `news/tests/test_altyapi.py`, `test_translation_verify.py`, `test_retranslate.py`, `test_filters.py`, `test_cache.py` | Yeni ve guncellenen testler |
| Alti frontend bileseni | Liste ve detayda etiket; CVE disa aktarmada etiket |
| `docker-compose.yml` | `teknoloji-translate` servisi, volume, `LIBRETRANSLATE_URL` |

---

### Task 1: Test ortamini canli ceviri servislerinden ayir

**Files:**
- Create: `news/test_runner.py`
- Modify: `cybernews/settings.py`
- Modify: `news/tests/test_altyapi.py`

**Interfaces:**
- Consumes: `translation_utils._gate`, `_LocalGate`, `_get_gate`
- Produces: `settings.LIBRETRANSLATE_URL: str` (ortamdan, varsayilan `''`); `settings.TEST_RUNNER = 'news.test_runner.GuvenliTestRunner'`; testler boyunca `settings.LIBRETRANSLATE_URL == ''` ve `tu._get_gate()` bir `_LocalGate`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_altyapi.py` sonuna ekle:

```python
from django.conf import settings as _ayarlar
from django.test import SimpleTestCase as _SimpleTestCase


class TestOrtamiIzolasyonuTests(_SimpleTestCase):
    """Testler canli LibreTranslate'e ve canli ceviri devre kesicisine dokunmamali.

    Dagitimdan sonra API konteynerinde LIBRETRANSLATE_URL tanimli olur ve testler
    ayni konteynerde kosar; bu testler o ortamda da gecmelidir.
    """

    def test_ozel_test_calistirici_ayarli(self):
        self.assertEqual(_ayarlar.TEST_RUNNER, 'news.test_runner.GuvenliTestRunner')

    def test_testlerde_libretranslate_kapali(self):
        self.assertEqual(_ayarlar.LIBRETRANSLATE_URL, '')

    def test_testlerde_google_devre_kesicisi_surec_ici(self):
        from news import translation_utils as tu
        self.assertIsInstance(tu._get_gate(), tu._LocalGate)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_altyapi.TestOrtamiIzolasyonuTests -v 2 2>&1 | tail -15`
Expected: 3 test de FAIL/ERROR — `TEST_RUNNER` varsayilan deger, `'Settings' object has no attribute 'LIBRETRANSLATE_URL'`, `_RedisGate` bir `_LocalGate` degil.

- [ ] **Step 2b: Mevcut testler canli devre kesicisine bagli mi, kaydet**

Run: `docker compose exec -T teknoloji-redis redis-cli pttl translate:cooldown`
Degeri not et (yalnizca bilgi; `-2` kapali demektir).

- [ ] **Step 3: Test calistiricisini yaz**

`news/test_runner.py`:

```python
"""Proje test calistiricisi.

Testler API konteynerinde kosar. O konteynerde LIBRETRANSLATE_URL tanimlidir ve
Redis canli devre kesici anahtarlarini tasir. Bu calistirici iki garanti verir:

1. Hicbir test gercek LibreTranslate'e gitmez: LIBRETRANSLATE_URL testler boyunca
   bostur. LibreTranslate testleri adresi override_settings ile kendileri verir ve
   HTTP'yi mock'lar.
2. Hicbir test canli ceviri devre kesicisini okumaz veya acmaz: kapilar surec
   icidir. Aksi halde Google canlida kisitliyken test sonuclari degisirdi.
"""
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class GuvenliTestRunner(DiscoverRunner):

    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._libretranslate_kapali = override_settings(LIBRETRANSLATE_URL='')
        self._libretranslate_kapali.enable()

        from news import translation_utils as tu
        tu._gate = tu._LocalGate()

    def teardown_test_environment(self, **kwargs):
        self._libretranslate_kapali.disable()
        super().teardown_test_environment(**kwargs)
```

- [ ] **Step 4: Ayarlari ekle**

`cybernews/settings.py` — `CELERY_BROKER_URL` satirindan **once** ekle:

```python
# Yerel LibreTranslate servisi: Google kapaliyken devreye giren yedek ceviri
# saglayicisi. Bos ise hic denenmez (bkz. news/translation_providers.py).
LIBRETRANSLATE_URL = os.environ.get('LIBRETRANSLATE_URL', '')

# Testler canli LibreTranslate'e ve canli ceviri devre kesicisine dokunmaz.
TEST_RUNNER = 'news.test_runner.GuvenliTestRunner'
```

- [ ] **Step 5: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_altyapi -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 6: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 143 tests`, `OK`

- [ ] **Step 7: Commit**

```bash
git add news/test_runner.py cybernews/settings.py news/tests/test_altyapi.py
git commit -m "$(cat <<'MSG'
test: testleri canli LibreTranslate ve canli devre kesicisinden ayir

Testler API konteynerinde kosuyor. Dagitimdan sonra orada
LIBRETRANSLATE_URL tanimli olacak; sahte Google basarisiz olunca mevcut
testler gercek LibreTranslate'e istek atardi. Ayrica mixin kullanmayan
testler canli Redis'teki Google devre kesicisini okuyordu; Google
canlida kisitliyken sonuclari degisebilirdi.

GuvenliTestRunner testler boyunca LIBRETRANSLATE_URL'i bosaltiyor ve
Google kapisini surec ici yapiyor. LIBRETRANSLATE_URL ayari eklendi.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: Alt cizgili tanimlayicilari ve cagrilari koru

**Files:**
- Modify: `news/translation_utils.py` (`_protect_terms`)
- Modify: `news/tests/test_translation_verify.py`

**Interfaces:**
- Consumes: `_protect_terms`, `_restore_terms`
- Produces: `_protect_terms` artik `ad()`, `Sinif::metod()`, `nesne.metod()` bicimli bos parantezli cagrilari ve en az bir alt cizgi iceren tanimlayicilari da yer tutucuyla korur

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_translation_verify.py` sonuna ekle:

```python
class TanimlayiciKorumaTests(SimpleTestCase):
    """LibreTranslate alt cizgiyi siliyor (parse_array -> parse array); Google da zaman zaman boluyor."""

    def test_alt_cizgili_tanimlayici_korunur(self):
        korunmus, esleme = tu._protect_terms('Exploitation requires comments on tribe_events posts.')
        self.assertIn('tribe_events', esleme.values())
        self.assertNotIn('tribe_events', korunmus)

    def test_bos_parantezli_cagrilar_korunur_ve_geri_konur(self):
        metin = ('It bypasses is_safe_widget_instance() and reaches '
                 'Element_Classes::parse_array() or obj.run() directly.')
        korunmus, esleme = tu._protect_terms(metin)
        for tanimlayici in ('is_safe_widget_instance()', 'Element_Classes::parse_array()', 'obj.run()'):
            self.assertIn(tanimlayici, esleme.values())
        self.assertEqual(tu._restore_terms(korunmus, esleme), metin)

    def test_siradan_metinde_yer_tutucu_uretilmez(self):
        _, esleme = tu._protect_terms('The attacker can read files remotely.')
        self.assertEqual(esleme, {})
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_verify.TanimlayiciKorumaTests -v 2 2>&1 | tail -15`
Expected: ilk iki test FAIL; `test_siradan_metinde_yer_tutucu_uretilmez` gecer.

- [ ] **Step 3: Deseni ekle**

`news/translation_utils.py` — `_protect_terms` icinde su iki satirin arasina:

```python
    result = re.sub(r'github\.com/[\w./-]+', _replace_match, result)
```

```python
    # 5) Surum numaralari: v1.2.3, 9.3.1, 2025.2
```

sunu ekle:

```python
    # 4b) Bos parantezli cagrilar: parse_array(), Element_Classes::parse_array(), obj.run()
    result = re.sub(
        r'\b[A-Za-z_][A-Za-z0-9_]*(?:(?:::|\.)[A-Za-z_][A-Za-z0-9_]*)*\(\)',
        _replace_match, result
    )

    # 4c) Alt cizgili tanimlayicilar: tribe_events, pg_stat_lock
    # LibreTranslate alt cizgiyi siler; Google da zaman zaman kelimelere boler.
    result = re.sub(r'\b[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+\b', _replace_match, result)
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_verify -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 17 tests`, `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 146 tests`, `OK`. Mevcut bir test duserse durma: o testin girdisinde alt cizgili tanimlayici var mi bak ve kullaniciya bildir.

- [ ] **Step 6: Commit**

```bash
git add news/translation_utils.py news/tests/test_translation_verify.py
git commit -m "$(cat <<'MSG'
feat: alt cizgili tanimlayicilari ve bos parantezli cagrilari ceviriden koru

LibreTranslate denemesinde alt cizgi siliniyordu (parse_array -> parse
array); CVE aciklamalari bu tur tanimlayicilarla dolu. Yer tutucuyla
korununca bir ornekte 0/3 -> 3/3 saglam kaldi. Google cevirilerine de
fayda sagliyor.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: Saglayicilar — Google sarmalayici ve LibreTranslate

**Files:**
- Create: `news/translation_providers.py`, `news/tests/test_translation_providers.py`
- Modify: `news/test_runner.py`, `news/tests/test_altyapi.py`

**Interfaces:**
- Consumes: `tu._get_gate`, `tu._translate_via_google`, `tu._RedisGate`, `tu._LocalGate`; `settings.LIBRETRANSLATE_URL`
- Produces:
  - Sabitler: `LIBRETRANSLATE_CHUNK_CHARS` (160), `LIBRETRANSLATE_TIMEOUT` (60.0), `LIBRETRANSLATE_COOLDOWN` (60)
  - `parcala(metin: str, sinir: int = None) -> List[List[str]]` — dis liste satirlar, ic liste o satirin parcalari; bos satir `[]`
  - `birlestir(satirlar: List[List[str]], cevrilen: List[str]) -> str`
  - `GoogleProvider` ve `LibreTranslateProvider`: `name: str`, `available() -> bool`, `translate(protected: str) -> Optional[str]`
  - `_lt_gate`, `_get_lt_gate()` — LibreTranslate devre kesicisi (Redis onek `libretranslate`)
  - `SAGLAYICILAR: tuple` — `(GoogleProvider(), LibreTranslateProvider())`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_translation_providers.py`:

```python
"""Ceviri saglayicisi testleri (spec 4.1). Ag erisimi yok; HTTP mock'lanir."""
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from news import translation_providers as tp
from news import translation_utils as tu

LT_ADRES = 'http://lt-test:5000'


class ParcalamaTests(SimpleTestCase):

    def test_satirlar_ve_bos_satir_korunur(self):
        self.assertEqual(tp.parcala('First line.\n\nSecond line here.', 160),
                         [['First line.'], [], ['Second line here.']])

    def test_cumle_sonlarindan_bolunur(self):
        self.assertEqual(tp.parcala('One sentence. Two sentence! Three?', 160),
                         [['One sentence.', 'Two sentence!', 'Three?']])

    def test_uzun_cumle_virgulden_bolunur_ve_virgul_kaybolmaz(self):
        metin = 'a' * 50 + ', ' + 'b' * 40
        self.assertEqual(tp.parcala(metin, 80), [['a' * 50 + ',', 'b' * 40]])

    def test_uzun_cumle_bosluktan_bolunur(self):
        metin = ('word ' * 30).strip()
        parcalar = tp.parcala(metin, 40)[0]
        self.assertTrue(all(len(p) <= 40 for p in parcalar))
        self.assertEqual(' '.join(parcalar), metin)

    def test_sert_kesim_yer_tutucuyu_bolmez(self):
        metin = 'x' * 35 + 'XTRM0001X' + 'y' * 20
        parcalar = tp.parcala(metin, 40)[0]
        self.assertTrue(any('XTRM0001X' in p for p in parcalar))
        self.assertEqual(''.join(parcalar), metin)

    def test_bosluksuz_metin_sinirdan_kesilir(self):
        self.assertEqual([len(p) for p in tp.parcala('z' * 100, 40)[0]], [40, 40, 20])

    def test_birlestir_satir_yapisini_korur(self):
        self.assertEqual(tp.birlestir([['a', 'b'], [], ['c']], ['A', 'B', 'C']), 'A B\n\nC')


class LibreTranslateTestMixin:

    def setUp(self):
        super().setUp()
        yama = mock.patch.object(tp, '_lt_gate', tu._LocalGate())
        yama.start()
        self.addCleanup(yama.stop)

    def _yanit(self, durum=200, govde=None):
        yanit = mock.Mock(status_code=durum)
        yanit.json.return_value = govde
        return yanit


class LibreTranslateHazirlikTests(LibreTranslateTestMixin, SimpleTestCase):

    def test_adres_yoksa_hazir_degil(self):
        with override_settings(LIBRETRANSLATE_URL=''):
            self.assertFalse(tp.LibreTranslateProvider().available())

    @override_settings(LIBRETRANSLATE_URL=LT_ADRES)
    def test_adres_varsa_hazir(self):
        self.assertTrue(tp.LibreTranslateProvider().available())

    @override_settings(LIBRETRANSLATE_URL=LT_ADRES)
    def test_devre_kesici_acikken_hazir_degil(self):
        tp._get_lt_gate().start_cooldown(60)
        self.assertFalse(tp.LibreTranslateProvider().available())


@override_settings(LIBRETRANSLATE_URL=LT_ADRES)
class LibreTranslateCeviriTests(LibreTranslateTestMixin, SimpleTestCase):

    def test_parcalar_tek_istekte_gider_ve_satirlar_korunur(self):
        metin = 'First sentence. Second sentence.\nThird line.'
        with mock.patch('news.translation_providers.requests.post', return_value=self._yanit(
                govde={'translatedText': ['Birinci cümle.', 'İkinci cümle.', 'Üçüncü satır.']})) as post:
            sonuc = tp.LibreTranslateProvider().translate(metin)

        self.assertEqual(sonuc, 'Birinci cümle. İkinci cümle.\nÜçüncü satır.')
        post.assert_called_once()
        adres = post.call_args.args[0]
        self.assertEqual(adres, f'{LT_ADRES}/translate')
        self.assertEqual(post.call_args.kwargs['json'], {
            'q': ['First sentence.', 'Second sentence.', 'Third line.'],
            'source': 'en', 'target': 'tr', 'format': 'text'})
        self.assertEqual(post.call_args.kwargs['timeout'], tp.LIBRETRANSLATE_TIMEOUT)

    def test_baglanti_hatasi_none_ve_devre_kesici(self):
        with mock.patch('news.translation_providers.requests.post',
                        side_effect=requests.ConnectionError('baglanti yok')):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))
        self.assertTrue(tp._get_lt_gate().cooldown_active())

    def test_zaman_asimi_none_ve_devre_kesici(self):
        with mock.patch('news.translation_providers.requests.post',
                        side_effect=requests.Timeout('yavas')):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))
        self.assertTrue(tp._get_lt_gate().cooldown_active())

    def test_5xx_none_ve_devre_kesici(self):
        with mock.patch('news.translation_providers.requests.post', return_value=self._yanit(503)):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))
        self.assertTrue(tp._get_lt_gate().cooldown_active())

    def test_4xx_none_ama_devre_kesici_acilmaz(self):
        with mock.patch('news.translation_providers.requests.post', return_value=self._yanit(400)):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))
        self.assertFalse(tp._get_lt_gate().cooldown_active())

    def test_liste_uzunlugu_uyusmazsa_none(self):
        with mock.patch('news.translation_providers.requests.post', return_value=self._yanit(
                govde={'translatedText': ['Tek parça.']})):
            self.assertIsNone(tp.LibreTranslateProvider().translate('One. Two.'))
        self.assertFalse(tp._get_lt_gate().cooldown_active())

    def test_bozuk_json_none(self):
        yanit = self._yanit()
        yanit.json.side_effect = ValueError('json degil')
        with mock.patch('news.translation_providers.requests.post', return_value=yanit):
            self.assertIsNone(tp.LibreTranslateProvider().translate('Some text here.'))


class GoogleSarmalayiciTests(SimpleTestCase):

    def test_hazirlik_google_devre_kesicisini_izler(self):
        kapi = tu._LocalGate()
        with mock.patch.object(tu, '_gate', kapi):
            self.assertTrue(tp.GoogleProvider().available())
            kapi.start_cooldown(60)
            self.assertFalse(tp.GoogleProvider().available())

    def test_ceviri_mevcut_google_mantigina_devredilir(self):
        with mock.patch.object(tu, '_translate_via_google', return_value='çeviri') as google:
            self.assertEqual(tp.GoogleProvider().translate('metin'), 'çeviri')
        google.assert_called_once_with('metin')

    def test_sira_google_once(self):
        self.assertEqual([s.name for s in tp.SAGLAYICILAR], ['google', 'libretranslate'])
```

`news/tests/test_altyapi.py` icindeki `TestOrtamiIzolasyonuTests` sinifina ekle:

```python
    def test_testlerde_libretranslate_devre_kesicisi_surec_ici(self):
        from news import translation_providers as tp
        from news import translation_utils as tu
        self.assertIsInstance(tp._get_lt_gate(), tu._LocalGate)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_providers news.tests.test_altyapi -v 2 2>&1 | tail -15`
Expected: ERROR — `No module named 'news.translation_providers'`

- [ ] **Step 3: `translation_providers.py`'yi yaz**

```python
"""Ceviri saglayicilari (spec 2026-09-14-ceviri-saglayici-zinciri, bolum 4.1).

translation_utils.translate_text saglayicilari SAGLAYICILAR sirasiyla dener.
Her saglayici ayni arayuzu uygular:

    name: str                             veritabanina yazilan ad
    available() -> bool                   simdi denenebilir mi
    translate(protected) -> str | None    terimleri korunmus metni cevirir; erisilemezse None

Google mantigi (hiz siniri, yeniden deneme, devre kesici) translation_utils
icinde kalir: mevcut testler oradaki adlari mock'luyor. GoogleProvider cagri
aninda oraya basvuran ince bir sarmalayicidir.
"""
import os
import re
from typing import List, Optional

import requests
from django.conf import settings

from . import translation_utils as tu

# LibreTranslate uzun, noktalamasi zayif bolumlerde yer tutucu dusuruyor.
# Denemede (60 gercek metin) <=160 karakterlik parcalar kaybi 14'ten 4'e indirdi.
LIBRETRANSLATE_CHUNK_CHARS = int(os.environ.get('LIBRETRANSLATE_CHUNK_CHARS', '160'))
LIBRETRANSLATE_TIMEOUT = float(os.environ.get('LIBRETRANSLATE_TIMEOUT', '60'))
# Yerel servis dusmusse bekleyip tekrar denemek cekimi yavaslatir; kisa sure atla.
LIBRETRANSLATE_COOLDOWN = int(os.environ.get('LIBRETRANSLATE_COOLDOWN', '60'))

_CUMLE_SONU = re.compile(r'(?<=[.!?])\s+')
_YER_TUTUCU_UZUNLUGU = len('XTRM0001X')


def _kesme_noktasi(cumle: str, sinir: int) -> int:
    virgul = cumle.rfind(', ', 0, sinir)
    if virgul > sinir // 2:
        return virgul + 1  # virgul ilk parcada kalsin
    bosluk = cumle.rfind(' ', 0, sinir)
    if bosluk > sinir // 2:
        return bosluk
    # Bosluk yok: sinira tasan bir yer tutucuyu ortadan bolme
    yer_tutucu = cumle.rfind('XTRM', max(0, sinir - _YER_TUTUCU_UZUNLUGU + 1), sinir)
    if yer_tutucu > 0:
        return yer_tutucu
    return sinir


def parcala(metin: str, sinir: int = None) -> List[List[str]]:
    """Metni satirlara, her satiri en fazla `sinir` karakterlik parcalara boler."""
    sinir = LIBRETRANSLATE_CHUNK_CHARS if sinir is None else sinir
    satirlar = []
    for satir in metin.split('\n'):
        parcalar = []
        for cumle in _CUMLE_SONU.split(satir.strip()):
            cumle = cumle.strip()
            while len(cumle) > sinir:
                kes = _kesme_noktasi(cumle, sinir)
                parcalar.append(cumle[:kes].strip())
                cumle = cumle[kes:].strip()
            if cumle:
                parcalar.append(cumle)
        satirlar.append(parcalar)
    return satirlar


def birlestir(satirlar: List[List[str]], cevrilen: List[str]) -> str:
    """parcala ciktisini cevrilmis parcalarla ayni satir yapisinda birlestirir."""
    kalan = iter(cevrilen)
    return '\n'.join(' '.join(next(kalan).strip() for _ in satir) for satir in satirlar)


class GoogleProvider:
    name = 'google'

    def available(self) -> bool:
        return not tu._get_gate().cooldown_active()

    def translate(self, protected: str) -> Optional[str]:
        return tu._translate_via_google(protected)


_lt_gate = None


def _get_lt_gate():
    """LibreTranslate devre kesicisi; Redis varsa tum worker'larda paylasilir."""
    global _lt_gate
    if _lt_gate is None:
        try:
            from django_redis import get_redis_connection
            client = get_redis_connection('default')
            client.ping()
            _lt_gate = tu._RedisGate(client, prefix='libretranslate')
        except Exception:
            _lt_gate = tu._LocalGate()
    return _lt_gate


class LibreTranslateProvider:
    name = 'libretranslate'

    def _adres(self) -> str:
        return (getattr(settings, 'LIBRETRANSLATE_URL', '') or '').rstrip('/')

    def available(self) -> bool:
        return bool(self._adres()) and not _get_lt_gate().cooldown_active()

    def _devre_kesici(self, sebep: str) -> None:
        print(f"  [Ceviri] LibreTranslate erisilemiyor ({sebep}); "
              f"{LIBRETRANSLATE_COOLDOWN} sn atlanacak.")
        _get_lt_gate().start_cooldown(LIBRETRANSLATE_COOLDOWN)

    def translate(self, protected: str) -> Optional[str]:
        adres = self._adres()
        if not adres:
            return None
        satirlar = parcala(protected)
        parcalar = [parca for satir in satirlar for parca in satir]
        if not parcalar:
            return protected

        try:
            yanit = requests.post(
                f'{adres}/translate',
                json={'q': parcalar, 'source': 'en', 'target': 'tr', 'format': 'text'},
                timeout=LIBRETRANSLATE_TIMEOUT,
            )
        except requests.RequestException as hata:
            self._devre_kesici(type(hata).__name__)
            return None

        if yanit.status_code >= 500:
            self._devre_kesici(f'HTTP {yanit.status_code}')
            return None
        if yanit.status_code != 200:
            # Istek sorunu; servis ayakta, devre kesici acilmaz
            print(f"  [Ceviri] LibreTranslate istegi reddetti (HTTP {yanit.status_code}).")
            return None

        try:
            cevrilen = yanit.json()['translatedText']
        except (ValueError, KeyError, TypeError):
            print("  [Ceviri] LibreTranslate gecersiz yanit dondurdu.")
            return None
        if not isinstance(cevrilen, list) or len(cevrilen) != len(parcalar):
            print("  [Ceviri] LibreTranslate parca sayisi uyusmadi.")
            return None
        return birlestir(satirlar, cevrilen)


SAGLAYICILAR = (GoogleProvider(), LibreTranslateProvider())
```

- [ ] **Step 4: Test calistiricisina LibreTranslate kapisini ekle**

`news/test_runner.py` — `setup_test_environment` icinde `tu._gate = tu._LocalGate()` satirinin altina ekle:

```python
        from news import translation_providers as tp
        tp._lt_gate = tu._LocalGate()
```

- [ ] **Step 5: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_providers news.tests.test_altyapi -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`; `test_translation_providers` icin 20 test.

- [ ] **Step 6: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 167 tests`, `OK`

- [ ] **Step 7: Commit**

```bash
git add news/translation_providers.py news/tests/test_translation_providers.py news/test_runner.py news/tests/test_altyapi.py
git commit -m "$(cat <<'MSG'
feat: Google ve LibreTranslate ceviri saglayicilari

LibreTranslateProvider metni <=160 karakterlik parcalara bolup tek
istekte gonderiyor ve satir yapisini koruyarak birlestiriyor. Baglanti
hatasi, zaman asimi ve 5xx'te 60 sn'lik kendi devre kesicisini aciyor;
4xx ve parca sayisi uyusmazliginda acmiyor. LIBRETRANSLATE_URL yoksa hic
denenmiyor.

GoogleProvider mevcut Google mantigina cagri aninda basvuran ince bir
sarmalayici; hiz siniri, yeniden deneme ve devre kesici translation_utils
icinde kaliyor, mevcut testlerin mock noktalari degismiyor.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: Zincirli ceviri ve kayit duzeyinde saglayici

**Files:**
- Modify: `news/translation_utils.py`
- Create: `news/tests/saglayici_yardimcilari.py`, `news/tests/test_translation_chain.py`

**Interfaces:**
- Consumes: `translation_providers.SAGLAYICILAR` (Task 3)
- Produces (`translation_utils`):
  - `consume_translation_providers() -> Set[str]` — son cagridan beri basariyla kullanilan saglayici adlari; sifirlar
  - `kayit_saglayicisi(kullanilanlar: Iterable[str]) -> str` — `'libretranslate'` > `'google'` > `''`
  - `yalnizca_saglayicilar(*adlar)` — baglam yoneticisi; icinde yalnizca bu adlardaki saglayicilar denenir
  - `saglayicilar() -> list` — kisit uygulanmis sirali saglayici listesi
  - `herhangi_saglayici_hazir() -> bool`
  - `translate_text(text)` — imza ayni; zinciri dener
- Produces (`news/tests/saglayici_yardimcilari.py`):
  - `SahteSaglayici(name, cevap=None, hazir=True)` — `cevap`: fonksiyon, sozluk (bilinmeyen anahtara `None`) veya sabit; `.cagrilar: list`
  - `SaglayiciZinciriMixin.saglayicilari_ayarla(*saglayicilar)` — `tp.SAGLAYICILAR`'i test boyunca degistirir

- [ ] **Step 1: Test yardimcilarini yaz**

`news/tests/saglayici_yardimcilari.py`:

```python
"""Ceviri saglayici zinciri testleri icin sahte saglayicilar. Ag erisimi yok."""
from unittest import mock

from news import translation_providers as tp


class SahteSaglayici:
    """Saglayici arayuzunu uygular.

    cevap: korunmus metni alan bir fonksiyon, sozluk (bilinmeyen anahtara None)
    veya sabit bir deger. None, saglayicinin erisilemedigi anlamina gelir.
    """

    def __init__(self, name, cevap=None, hazir=True):
        self.name = name
        self._cevap = cevap
        self.hazir = hazir
        self.cagrilar = []

    def available(self):
        return self.hazir

    def translate(self, protected):
        self.cagrilar.append(protected)
        if callable(self._cevap):
            return self._cevap(protected)
        if isinstance(self._cevap, dict):
            return self._cevap.get(protected)
        return self._cevap


class SaglayiciZinciriMixin:

    def saglayicilari_ayarla(self, *saglayicilar):
        yama = mock.patch.object(tp, 'SAGLAYICILAR', tuple(saglayicilar))
        yama.start()
        self.addCleanup(yama.stop)
        return saglayicilar
```

- [ ] **Step 2: Basarisiz testi yaz**

`news/tests/test_translation_chain.py`:

```python
"""Ceviri saglayici zinciri testleri (spec 4.2, 4.4)."""
from django.test import SimpleTestCase

from news import translation_utils as tu
from news.tests.saglayici_yardimcilari import SahteSaglayici, SaglayiciZinciriMixin

METIN = 'Attackers can read arbitrary files.'  # 5 kelime: yanki kontrolune tabi


def google_eki(protected):
    return 'GOOGLE ' + protected


def libre_eki(protected):
    return 'LIBRE ' + protected


class SaglayiciZinciriTests(SaglayiciZinciriMixin, SimpleTestCase):

    def setUp(self):
        super().setUp()
        tu.consume_translation_failures()
        tu.consume_translation_providers()

    def test_google_basariliysa_libretranslate_cagrilmaz(self):
        google, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', google_eki), SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'GOOGLE ' + METIN)
        self.assertEqual(libre.cagrilar, [])
        self.assertEqual(tu.consume_translation_providers(), {'google'})
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_google_erisilemezse_libretranslate(self):
        _, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', None), SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)
        self.assertEqual(len(libre.cagrilar), 1)
        self.assertEqual(tu.consume_translation_providers(), {'libretranslate'})

    def test_google_dogrulamaya_takilirsa_libretranslate(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', lambda p: p),  # yanki
            SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)
        self.assertEqual(tu.consume_translation_providers(), {'libretranslate'})
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_hicbiri_basarisizsa_orijinal_ve_sayac(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', None), SahteSaglayici('libretranslate', lambda p: p))

        self.assertEqual(tu.translate_text(METIN), METIN)
        self.assertEqual(tu.consume_translation_failures(), 1)
        self.assertEqual(tu.consume_translation_providers(), set())

    def test_hazir_olmayan_saglayici_cagrilmaz(self):
        google, _ = self.saglayicilari_ayarla(
            SahteSaglayici('google', google_eki, hazir=False), SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)
        self.assertEqual(google.cagrilar, [])

    def test_saglayici_istisnasi_zinciri_kesmez(self):
        def patlayan(_):
            raise RuntimeError('beklenmeyen')
        self.saglayicilari_ayarla(
            SahteSaglayici('google', patlayan), SahteSaglayici('libretranslate', libre_eki))

        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)

    def test_yalnizca_google_kisiti(self):
        _, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', None), SahteSaglayici('libretranslate', libre_eki))

        with tu.yalnizca_saglayicilar('google'):
            self.assertEqual(tu.translate_text(METIN), METIN)
        self.assertEqual(libre.cagrilar, [])
        self.assertEqual(tu.consume_translation_failures(), 1)
        # Kisit baglam disinda kalkar
        self.assertEqual(tu.translate_text(METIN), 'LIBRE ' + METIN)

    def test_herhangi_saglayici_hazir(self):
        google, libre = self.saglayicilari_ayarla(
            SahteSaglayici('google', hazir=False), SahteSaglayici('libretranslate', hazir=True))
        self.assertTrue(tu.herhangi_saglayici_hazir())
        with tu.yalnizca_saglayicilar('google'):
            self.assertFalse(tu.herhangi_saglayici_hazir())
        libre.hazir = False
        self.assertFalse(tu.herhangi_saglayici_hazir())

    def test_uzun_metnin_parcalari_farkli_saglayicilardan_gelebilir(self):
        birinci, ikinci = 'First sentence is right here.', 'Second sentence is right here.'
        self.saglayicilari_ayarla(
            SahteSaglayici('google', {birinci: 'Birinci cümle tam burada.'}),
            SahteSaglayici('libretranslate', libre_eki))

        tu.translate_long_text(f'{birinci} {ikinci}', chunk_size=35)

        self.assertEqual(tu.consume_translation_providers(), {'google', 'libretranslate'})

    def test_consume_translation_providers_sifirlar(self):
        self.saglayicilari_ayarla(SahteSaglayici('google', google_eki))
        tu.translate_text(METIN)
        self.assertEqual(tu.consume_translation_providers(), {'google'})
        self.assertEqual(tu.consume_translation_providers(), set())


class KayitSaglayicisiTests(SimpleTestCase):

    def test_en_dusuk_kalite_belirleyicidir(self):
        self.assertEqual(tu.kayit_saglayicisi({'google', 'libretranslate'}), 'libretranslate')
        self.assertEqual(tu.kayit_saglayicisi({'libretranslate'}), 'libretranslate')
        self.assertEqual(tu.kayit_saglayicisi({'google'}), 'google')
        self.assertEqual(tu.kayit_saglayicisi(set()), '')
```

- [ ] **Step 3: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_chain -v 2 2>&1 | tail -20`
Expected: ERROR/FAIL — `module 'news.translation_utils' has no attribute 'consume_translation_providers'` vb.

- [ ] **Step 4: Zinciri yaz**

`news/translation_utils.py`:

a) Import satirlarini su hale getir:

```python
import os
import re
import time
from contextlib import contextmanager
from typing import Dict, Iterable, List, Optional, Set, Tuple
```

b) `consume_translation_failures` fonksiyonunun hemen altina ekle:

```python
# ------------------------------------------------------------
# Saglayici zinciri (spec 2026-09-14-ceviri-saglayici-zinciri)
# ------------------------------------------------------------
# translate_text saglayicilari translation_providers.SAGLAYICILAR sirasiyla
# dener: Google -> LibreTranslate -> orijinal metin.

_used_providers: Set[str] = set()
_saglayici_kisiti = None


def consume_translation_providers() -> Set[str]:
    """Son cagridan beri basariyla kullanilan saglayici adlarini dondurur ve sifirlar."""
    global _used_providers
    kullanilan, _used_providers = _used_providers, set()
    return kullanilan


def kayit_saglayicisi(kullanilanlar: Iterable[str]) -> str:
    """Kaydin saglayicisi: en dusuk kaliteli parca belirleyicidir."""
    kullanilanlar = set(kullanilanlar)
    if 'libretranslate' in kullanilanlar:
        return 'libretranslate'
    if 'google' in kullanilanlar:
        return 'google'
    return ''


@contextmanager
def yalnizca_saglayicilar(*adlar):
    """Blok icinde yalnizca bu adlardaki saglayicilar denenir (orn. yukseltme: 'google')."""
    global _saglayici_kisiti
    onceki = _saglayici_kisiti
    _saglayici_kisiti = set(adlar)
    try:
        yield
    finally:
        _saglayici_kisiti = onceki


def saglayicilar() -> list:
    from . import translation_providers as tp
    if _saglayici_kisiti is None:
        return list(tp.SAGLAYICILAR)
    return [s for s in tp.SAGLAYICILAR if s.name in _saglayici_kisiti]


def herhangi_saglayici_hazir() -> bool:
    return any(s.available() for s in saglayicilar())
```

c) `translate_text` fonksiyonunu tamamen su hale getir:

```python
def translate_text(text: str) -> str:
    """
    Tek bir metin parcasini Turkce'ye cevirir.
    Terim koruma uygulanir. Saglayicilar sirayla denenir (bkz. saglayicilar());
    her denemenin cevabi onarilir, dogrulanir (verify_translation) ve geri konur.
    Guvenilir ceviri ureten ilk saglayicinin sonucu doner ve adi
    consume_translation_providers ile okunur. Hicbiri basarili olmazsa orijinal
    metin doner ve basarisizlik sayaci artar (bkz. consume_translation_failures).
    """
    global _failure_count
    if not text or len(text.strip()) == 0:
        return ""

    try:
        protected, replacements = _protect_terms(text)
    except Exception as e:
        print(f"  [Ceviri] Hata: {e}")
        _failure_count += 1
        return text

    for saglayici in saglayicilar():
        if not saglayici.available():
            continue
        try:
            translated = saglayici.translate(protected)
            if translated is None:
                continue
            # Saglayici yer tutucuyu 'xtrm 0001x' gibi bozabilir; geri koymadan ONCE onarilmali
            translated = _repair_placeholders(translated)
            sorun = verify_translation(protected, translated, replacements)
            if sorun is None:
                restored = _restore_terms(translated, replacements)
                if any(kod in restored for kod in replacements):
                    sorun = 'yer tutucu kalintisi'
            if sorun:
                print(f"  [Ceviri] {saglayici.name} dogrulama basarisiz ({sorun}).")
                continue
            sonuc = turkish_post_process(restored)
        except Exception as e:
            print(f"  [Ceviri] {saglayici.name} hata: {e}")
            continue
        _used_providers.add(saglayici.name)
        return sonuc

    _failure_count += 1
    return text
```

d) "3. GOOGLE TRANSLATE CEVIRI" bolum basligi yorumunun son satirinin altina ekle:

```python
# Google bu zincirin ilk saglayicisidir; LibreTranslate yedektir
# (bkz. news/translation_providers.py ve saglayicilar()).
```

- [ ] **Step 5: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_chain -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 11 tests`, `OK`

- [ ] **Step 6: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 178 tests`, `OK`. Mevcut ceviri testlerinden biri duserse durma ve bildir: zincir LibreTranslate yapilandirilmamisken eski davranisi birebir korumalidir.

- [ ] **Step 7: Commit**

```bash
git add news/translation_utils.py news/tests/saglayici_yardimcilari.py news/tests/test_translation_chain.py
git commit -m "$(cat <<'MSG'
feat: translate_text saglayici zincirini denesin

Her metin icin Google -> LibreTranslate -> orijinal. Her denemede A3
dogrulamasi calisiyor; erisilemeyen, dogrulamaya takilan veya istisna
firlatan saglayici bir sonrakine birakiyor. Basarili saglayicinin adi
consume_translation_providers ile okunuyor; kayit_saglayicisi en dusuk
kaliteli parcayi kaydin saglayicisi sayiyor.

yalnizca_saglayicilar baglam yoneticisi yukseltme asamasinin ic ice
cagrilarda (translate_long_text, K8s yapisal changelog) yalnizca Google'i
denemesini sagliyor. LibreTranslate yapilandirilmamisken davranis
oncekiyle ayni.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: `translation_provider` alani ve migration 0009

**Files:**
- Modify: `news/models.py`
- Create: `news/migrations/0009_translation_provider.py`, `news/tests/test_migrations_0009.py`

**Interfaces:**
- Consumes: yok
- Produces: Alti modelde `translation_provider` (`CharField`, `max_length=20`, `blank=True`, `default=''`, secenekler `google`/`libretranslate`); migration modulunde `eski_cevirileri_google_isaretle(apps, schema_editor)` ve `geri_al(apps, schema_editor)`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_migrations_0009.py`:

```python
"""Migration 0009 veri adimi: eski cevrilmis kayitlar sessizce 'google' olur (kullanici secimi)."""
import importlib
from datetime import date

from django.apps import apps
from django.test import TestCase

from news.models import AINewsEntry, CVEEntry


class CeviriSaglayicisiMigrationTests(TestCase):

    def setUp(self):
        self.goc = importlib.import_module('news.migrations.0009_translation_provider')
        self.cevrilmis = AINewsEntry.objects.create(
            source='Test', original_title='A', turkish_title='A tr', original_description='B',
            link='https://ornek.test/goc/1', published_date=date(2026, 9, 14), needs_translation=False)
        self.bekleyen = CVEEntry.objects.create(
            cve_id='CVE-2026-9001', source='NVD', original_title='CVE-2026-9001',
            original_description='Pending body.', published_date=date(2026, 9, 14),
            link='https://ornek.test/goc/2', needs_translation=True)

    def test_cevrilmis_google_bekleyen_bos(self):
        self.goc.eski_cevirileri_google_isaretle(apps, None)

        self.cevrilmis.refresh_from_db()
        self.bekleyen.refresh_from_db()
        self.assertEqual(self.cevrilmis.translation_provider, 'google')
        self.assertEqual(self.bekleyen.translation_provider, '')

    def test_isaretleme_updated_at_ilerletmez(self):
        once = AINewsEntry.objects.get(pk=self.cevrilmis.pk).updated_at
        self.goc.eski_cevirileri_google_isaretle(apps, None)
        self.assertEqual(AINewsEntry.objects.get(pk=self.cevrilmis.pk).updated_at, once)

    def test_geri_alma_alani_bosaltir(self):
        self.goc.eski_cevirileri_google_isaretle(apps, None)
        self.goc.geri_al(apps, None)
        self.cevrilmis.refresh_from_db()
        self.assertEqual(self.cevrilmis.translation_provider, '')
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_migrations_0009 -v 2 2>&1 | tail -10`
Expected: ERROR — `No module named 'news.migrations.0009_translation_provider'`

- [ ] **Step 3: Alani alti modele ekle**

`news/models.py` — alti modelin her birinde `needs_translation` satirinin hemen altina:

```python
    translation_provider = models.CharField(
        max_length=20, blank=True, default='',
        choices=[('google', 'Google'), ('libretranslate', 'LibreTranslate')],
        verbose_name='Ceviri Saglayicisi')
```

- [ ] **Step 4: Migration'i uret, veri adimini ekle**

Run: `docker compose exec -T teknoloji-api python manage.py makemigrations news --name translation_provider`
Expected: `news/migrations/0009_translation_provider.py` — alti `AddField`.

Uretilen dosyayi tamamen su hale getir (alan tanimlari Django'nun urettigiyle birebir aynidir; yalnizca veri adimi eklenir):

```python
from django.db import migrations, models

MODELLER = ('ainewsentry', 'cveentry', 'devtoolsentry', 'kubernetesentry', 'newsarticle', 'sreentry')


def eski_cevirileri_google_isaretle(apps, schema_editor):
    """2026-09-14'e kadar tek saglayici Google'di: cevrilmis kayitlar 'google' olur.

    QuerySet.update updated_at'i ilerletmez; tuketicinin delta akisina kayit dusmez.
    Aciklamasi 30 karakterden kisa oldugu icin hic cevrilmemis CVE'ler de 'google'
    gorunur; cevrilecek metinleri olmadigi icin zararsizdir.
    """
    for ad in MODELLER:
        apps.get_model('news', ad).objects.filter(needs_translation=False).update(translation_provider='google')


def geri_al(apps, schema_editor):
    for ad in MODELLER:
        apps.get_model('news', ad).objects.update(translation_provider='')


class Migration(migrations.Migration):

    dependencies = [
        ('news', '0008_updated_at'),
    ]

    operations = [
        *[
            migrations.AddField(
                model_name=ad,
                name='translation_provider',
                field=models.CharField(
                    blank=True, default='', max_length=20,
                    choices=[('google', 'Google'), ('libretranslate', 'LibreTranslate')],
                    verbose_name='Ceviri Saglayicisi'),
            )
            for ad in MODELLER
        ],
        migrations.RunPython(eski_cevirileri_google_isaretle, geri_al),
    ]
```

- [ ] **Step 5: Model ile migration'in esit oldugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`. Degisiklik gorulurse alan tanimini Step 3 ile karsilastir.

**Canli veritabanina `migrate` UYGULAMA.** Migration Task 11'de, worker durdurulduktan sonra uygulanir. Testler kendi test veritabanini olusturur.

- [ ] **Step 6: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_migrations_0009 -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 3 tests`, `OK`

- [ ] **Step 7: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 181 tests`, `OK`

- [ ] **Step 8: Commit**

```bash
git add news/models.py news/migrations/0009_translation_provider.py news/tests/test_migrations_0009.py
git commit -m "$(cat <<'MSG'
feat: kayitlara translation_provider alani

Alti modele google/libretranslate/bos degerli alan eklendi. Migration
0009 mevcut cevrilmis kayitlari 'google' olarak isaretliyor (bugune kadar
tek saglayici Google'di); QuerySet.update kullanildigi icin updated_at
ilerlemiyor ve tuketiciye kayit dusmuyor.

Dagitim notu: migration NOT NULL sutun ekliyor; uygulanmadan once worker
ve scheduler durdurulmali.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: Fetch task'lari saglayiciyi yazsin

**Files:**
- Modify: `news/tasks.py`
- Modify: `news/tests/test_translation_chain.py`

**Interfaces:**
- Consumes: `consume_translation_providers`, `kayit_saglayicisi` (Task 4); `translation_provider` alani (Task 5)
- Produces: Alti fetch task'i her kayda `translation_provider` yazar

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_translation_chain.py` sonuna ekle:

```python
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from news import tasks
from news.models import AINewsEntry
from news.tests.base import LOCMEM_CACHE
from news.tests.test_translation import TranslationGateMixin


def _ham_ai(baslik, govde, slug):
    return {'title': baslik, 'description': govde, 'link': f'https://ornek.test/zincir/{slug}',
            'date': '2026-09-14', 'source': 'MIT Tech Review AI'}


@override_settings(CACHES=LOCMEM_CACHE)
class FetchTaskSaglayiciTests(SaglayiciZinciriMixin, TranslationGateMixin, TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        tu.consume_translation_providers()

    def _cek(self, girdiler):
        with mock.patch.object(tasks.MultiAINewsScraper, 'fetch_all', return_value=girdiler):
            return tasks.fetch_ai_news_task(days=30)

    def test_task_kayit_saglayicisini_yazar(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', {
                'Only google title': 'Yalnızca google başlığı',
                'Google body text for this story.': 'Bu haberin google gövde metni.',
                'Mixed story title': 'Karışık haber başlığı',
            }),
            SahteSaglayici('libretranslate', libre_eki))

        self._cek([
            _ham_ai('Only google title', 'Google body text for this story.', 'google'),
            _ham_ai('Mixed story title', 'Body text that only libre translates.', 'karisik'),
        ])

        google = AINewsEntry.objects.get(link='https://ornek.test/zincir/google')
        karisik = AINewsEntry.objects.get(link='https://ornek.test/zincir/karisik')
        self.assertEqual(google.translation_provider, 'google')
        self.assertFalse(google.needs_translation)
        self.assertEqual(karisik.translation_provider, 'libretranslate')
        self.assertFalse(karisik.needs_translation)

    def test_hicbir_saglayici_yoksa_bos_ve_bekleyen(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', hazir=False), SahteSaglayici('libretranslate', hazir=False))

        self._cek([_ham_ai('Nothing translates this title', 'Nothing translates this body.', 'yok')])

        kayit = AINewsEntry.objects.get(link='https://ornek.test/zincir/yok')
        self.assertEqual(kayit.translation_provider, '')
        self.assertTrue(kayit.needs_translation)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_chain.FetchTaskSaglayiciTests -v 2 2>&1 | tail -12`
Expected: FAIL — `translation_provider` bos kaliyor (`'' != 'google'`).

- [ ] **Step 3: Alti task'i guncelle**

`news/tasks.py` icinde her task ayni iki kaliba sahiptir; alti kopyayi birden, sayilarini dogrulayarak degistir:

```bash
docker compose exec -T teknoloji-api python - <<'PY'
import io
p = '/app/news/tasks.py'
s = io.open(p, encoding='utf-8').read()

eski_import = 'from .translation_utils import consume_translation_failures\n'
yeni_import = ('from .translation_utils import (\n'
               '    consume_translation_failures, consume_translation_providers, kayit_saglayicisi,\n'
               ')\n')
assert s.count(eski_import) == 1
s = s.replace(eski_import, yeni_import)

eski_sifirla = '            consume_translation_failures()\n            for '
yeni_sifirla = '            consume_translation_failures()\n            consume_translation_providers()\n            for '
assert s.count(eski_sifirla) == 6, s.count(eski_sifirla)
s = s.replace(eski_sifirla, yeni_sifirla)

eski_alan = "                        'needs_translation': consume_translation_failures() > 0,\n"
yeni_alan = (eski_alan +
             "                        'translation_provider': kayit_saglayicisi(consume_translation_providers()),\n")
assert s.count(eski_alan) == 6, s.count(eski_alan)
s = s.replace(eski_alan, yeni_alan)

io.open(p, 'w', encoding='utf-8').write(s)
print('alti task guncellendi')
PY
```

Expected: `alti task guncellendi`. `AssertionError` alirsan dosya plan yazildigindan beri degismistir; durma ve bildir.

`news/tasks.py` icindeki `# Not: needs_translation degeri ...` yorum blogunun altina ekle:

```python
# translation_provider ayni anda okunur: kaydin cevirisinde kullanilan
# saglayicilarin en dusuk kalitelisi (bkz. translation_utils.kayit_saglayicisi).
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_chain -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 13 tests`, `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 183 tests`, `OK`

- [ ] **Step 6: Commit**

```bash
git add news/tasks.py news/tests/test_translation_chain.py
git commit -m "$(cat <<'MSG'
feat: fetch task'lari kaydin ceviri saglayicisini yazsin

Alti task her kayit icin kullanilan saglayicilari
consume_translation_providers ile topluyor ve en dusuk kalitelisini
translation_provider olarak yaziyor. needs_translation hesabi degismedi.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 7: `retranslate_pending` — iki asama

**Files:**
- Modify: `news/retranslate.py`
- Modify: `news/tests/test_retranslate.py`

**Interfaces:**
- Consumes: `herhangi_saglayici_hazir`, `yalnizca_saglayicilar`, `consume_translation_providers`, `kayit_saglayicisi` (Task 4); `translation_provider` (Task 5)
- Produces:
  - `RETRANSLATE_BATCH` varsayilani **100**; yeni `RETRANSLATE_UPGRADE_BATCH` (5)
  - `retranslate_pending(redis_client=None, prefix='retranslate', batch=None, upgrade_batch=None) -> dict`
  - Donus: `{'translated': int, 'failed': int, 'upgraded': int, 'stopped': bool, 'by_provider': {'google': int, 'libretranslate': int}, 'sections': {bolum: {'translated': int, 'failed': int, 'upgraded': int}}}`
  - Redis anahtarlari: `{prefix}:cursor:{bolum}` (bekleyen), `{prefix}:upgrade-cursor:{bolum}` (yukseltme)

- [ ] **Step 1: Mevcut testleri yeni donus bicimine guncelle**

`news/tests/test_retranslate.py`:

1. Tum `sonuc['stopped_by_cooldown']` ifadelerini `sonuc['stopped']` yap (3 yer).
2. `test_bekleyen_kayit_feede_bakmadan_cevrilir` icindeki satiri

```python
        self.assertEqual(sonuc['sections']['ai'], {'translated': 1, 'failed': 0})
```

su hale getir:

```python
        self.assertEqual(sonuc['sections']['ai'], {'translated': 1, 'failed': 0, 'upgraded': 0})
        self.assertEqual(sonuc['by_provider'], {'google': 1, 'libretranslate': 0})
        self.assertEqual(kayit.translation_provider, 'google')
```

3. `RetranslateTestBase._calistir` metodunu su hale getir:

```python
    def _calistir(self, batch=8, upgrade_batch=5):
        from news.retranslate import retranslate_pending
        return retranslate_pending(redis_client=self.redis, prefix=self.prefix,
                                   batch=batch, upgrade_batch=upgrade_batch)
```

4. Dosyanin import blogunun sonuna ekle:

```python
from news.tests.saglayici_yardimcilari import SahteSaglayici, SaglayiciZinciriMixin


def _google(protected):
    return 'GOOGLE ' + protected


def _libre(protected):
    return 'LIBRE ' + protected
```

- [ ] **Step 2: Yeni basarisiz testleri yaz**

`news/tests/test_retranslate.py` icinde `RetranslateGoreviTests` sinifindan **once** ekle:

```python
class RetranslateSaglayiciTests(SaglayiciZinciriMixin, RetranslateTestBase):
    """Spec 6.2: bekleyenler tam zincirle, yukseltme yalnizca Google ile."""

    def _libre_kaydi(self, slug, baslik='Farmers adopt new sensors',
                     govde='Sensors measure soil moisture every hour.'):
        return AINewsEntry.objects.create(
            source='MIT Tech Review AI', original_title=baslik, turkish_title='LIBRE ' + baslik,
            original_description=govde, turkish_description='LIBRE ' + govde,
            link=f'https://ornek.test/yukselt/{slug}', published_date=date(2026, 9, 14),
            needs_translation=False, translation_provider='libretranslate')

    def test_varsayilan_sinirlar(self):
        from news import retranslate
        self.assertEqual(retranslate.RETRANSLATE_BATCH, 100)
        self.assertEqual(retranslate.RETRANSLATE_UPGRADE_BATCH, 5)

    def test_google_kapaliyken_libretranslate_ile_devam_eder(self):
        self.saglayicilari_ayarla(SahteSaglayici('google', _google, hazir=False),
                                  SahteSaglayici('libretranslate', _libre))
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'lt')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(kayit.turkish_title, 'LIBRE Farmers adopt new sensors')
        self.assertFalse(sonuc['stopped'])
        self.assertEqual(sonuc['by_provider'], {'google': 0, 'libretranslate': 1})

    def test_hicbir_saglayici_yoksa_durur(self):
        google, libre = self.saglayicilari_ayarla(SahteSaglayici('google', _google, hazir=False),
                                                  SahteSaglayici('libretranslate', _libre, hazir=False))
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'yok')

        sonuc = self._calistir()

        self.assertTrue(sonuc['stopped'])
        self.assertEqual(google.cagrilar + libre.cagrilar, [])

    def test_google_acikken_libretranslate_cevirisi_yukseltilir(self):
        _, libre = self.saglayicilari_ayarla(SahteSaglayici('google', _google),
                                             SahteSaglayici('libretranslate', _libre))
        kayit = self._libre_kaydi('tam')
        once = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(sonuc['upgraded'], 1)
        self.assertEqual(sonuc['sections']['ai']['upgraded'], 1)
        self.assertEqual(kayit.translation_provider, 'google')
        self.assertEqual(kayit.turkish_title, 'GOOGLE Farmers adopt new sensors')
        self.assertGreater(kayit.updated_at, once, 'Yukseltme delta akisina dusmeli')
        self.assertEqual(libre.cagrilar, [], 'Yukseltme LibreTranslate kullanmamali')

    def test_google_kapaliyken_yukseltme_yapilmaz(self):
        google, libre = self.saglayicilari_ayarla(SahteSaglayici('google', _google, hazir=False),
                                                  SahteSaglayici('libretranslate', _libre))
        kayit = self._libre_kaydi('kapali')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(google.cagrilar + libre.cagrilar, [])

    def test_kismi_yukseltme_kayda_yazilmaz(self):
        """Kullanici secimi: hepsi ya da hicbiri."""
        self.saglayicilari_ayarla(
            SahteSaglayici('google', {'Farmers adopt new sensors': 'Çiftçiler yeni sensörler benimsiyor'}),
            SahteSaglayici('libretranslate', _libre))
        kayit = self._libre_kaydi('kismi')
        once = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(kayit.turkish_title, 'LIBRE Farmers adopt new sensors')
        self.assertEqual(kayit.updated_at, once)

    def test_yukseltme_bolum_siniri(self):
        self.saglayicilari_ayarla(SahteSaglayici('google', _google),
                                  SahteSaglayici('libretranslate', _libre))
        for i in range(7):
            self._libre_kaydi(f'sinir-{i}')

        sonuc = self._calistir(upgrade_batch=5)

        self.assertEqual(sonuc['upgraded'], 5)
        self.assertEqual(AINewsEntry.objects.filter(translation_provider='libretranslate').count(), 2)

    def test_karisik_bekleyen_kayit_libretranslate_sayilir(self):
        self.saglayicilari_ayarla(
            SahteSaglayici('google', {'Farmers adopt new sensors': 'Çiftçiler yeni sensörler benimsiyor'}),
            SahteSaglayici('libretranslate', _libre))
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'karisik')

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(kayit.turkish_title, 'Çiftçiler yeni sensörler benimsiyor')
```

MRO notu: `SaglayiciZinciriMixin` `setUp` tanimlamaz; `RetranslateTestBase.setUp` normal calisir.

Bu siniftaki yukseltme testlerinde bekleyen kayit yoktur; `test_google_kapaliyken_libretranslate_ile_devam_eder` ve `test_karisik_bekleyen...` icinde yukseltme adayi yoktur. Bu yuzden saglayici cagri sayilari yalnizca test edilen asamayi yansitir.

- [ ] **Step 3: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate -v 2 2>&1 | tail -25`
Expected: FAIL/ERROR — `KeyError: 'stopped'`, `retranslate_pending() got an unexpected keyword argument 'upgrade_batch'` vb.

- [ ] **Step 4: `retranslate.py`'yi yeniden yaz**

`news/retranslate.py` dosyasini tamamen su hale getir. `_baslik_ve_uzun_aciklama`, `_cve`, `_kubernetes`, `BOLUMLER`, `_canli_redis` mevcut dosyadakiyle birebir aynidir.

```python
"""Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir ve LibreTranslate
cevirilerini Google acildiginda yukseltir.

Asama 1 — Bekleyenler (needs_translation=True), tam saglayici zinciriyle
(Google -> LibreTranslate). A3 plani netlestirme 8'deki imlec kurallari aynen
gecerlidir: her bolum icin Redis'te bir imlec ({prefix}:cursor:{bolum}); icerik
yuzunden cevrilemeyen kayit sirada kalir ama imlec onu gecer; sona gelinince
imlec silinir. Gorev yalnizca HICBIR saglayici hazir degilse durur; bu durumda
imlec o kaydi gecmez.

Asama 2 — Yukseltme (needs_translation=False, translation_provider='libretranslate'),
yalnizca Google hazirsa ve yalnizca Google ile. Kaydin tum parcalari Google'la
cevrilebildiyse yazilir (hepsi ya da hicbiri); aksi halde LibreTranslate cevirisi
yerinde kalir. Kendi imleci vardir ({prefix}:upgrade-cursor:{bolum}).

Yazma kurallari:
  - Basarisiz denemede kayda yazilmaz: updated_at ilerlemez.
  - Basarida Turkce alanlar, needs_translation=False, translation_provider ve
    updated_at yazilir; ceviri delta akisindan tuketiciye gider.
"""
import os
from typing import Dict

from . import translation_utils as tu
from .api_v1.cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
from .cache_utils import cache_yenile
from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

# Bolum basina. LibreTranslate yerel ve hizli oldugu icin bekleyen siniri yuksek.
RETRANSLATE_BATCH = int(os.environ.get('RETRANSLATE_BATCH', '100'))
# Yukseltme ucretsiz Google kotasini kullanir; dusuk tutulur.
RETRANSLATE_UPGRADE_BATCH = int(os.environ.get('RETRANSLATE_UPGRADE_BATCH', '5'))


def _baslik_ve_uzun_aciklama(kayit) -> Dict[str, str]:
    # scraper_multi, sre_scraper, devtools_scraper ve ai_scraper ile ayni kural
    return {
        'turkish_title': tu.translate_text(kayit.original_title),
        'turkish_description': tu.translate_long_text(kayit.original_description),
    }


def _cve(kayit) -> Dict[str, str]:
    # cve_scraper.process_cves ile ayni: baslik cevrilmez, 30 karakterden kisa aciklama oldugu gibi kalir
    aciklama = kayit.original_description or ''
    return {
        'turkish_title': kayit.original_title,
        'turkish_description': tu.translate_text(aciklama) if len(aciklama.strip()) > 30 else aciklama,
    }


def _kubernetes(kayit) -> Dict[str, str]:
    # k8s_scraper.MultiK8sScraper.process_entries ile ayni ayrim
    aciklama = kayit.original_description or ''
    if kayit.source == 'GitHub Releases' and '===SECTION:' in aciklama:
        from .k8s_scraper import MultiK8sScraper
        turkce_aciklama = MultiK8sScraper()._translate_structured_changelog(aciklama)
    else:
        turkce_aciklama = tu.translate_long_text(aciklama)
    return {
        'turkish_title': tu.translate_text(kayit.original_title),
        'turkish_description': turkce_aciklama,
    }


BOLUMLER = (
    ('news', NewsArticle, _baslik_ve_uzun_aciklama),
    ('cve', CVEEntry, _cve),
    ('kubernetes', KubernetesEntry, _kubernetes),
    ('sre', SREEntry, _baslik_ve_uzun_aciklama),
    ('devtools', DevToolsEntry, _baslik_ve_uzun_aciklama),
    ('ai', AINewsEntry, _baslik_ve_uzun_aciklama),
)


def _canli_redis():
    from django_redis import get_redis_connection
    return get_redis_connection('default')


def _imlecten_sonraki(redis_client, anahtar, sorgu, sinir):
    ham = redis_client.get(anahtar)
    if ham:
        try:
            sorgu = apply_cursor(sorgu, *decode_cursor(ham.decode('utf-8')))
        except InvalidCursor:
            redis_client.delete(anahtar)
    return list(sorgu[:sinir])


def _cevir_ve_olc(cevir, kayit):
    """Kaydi cevirir; (alanlar, basarisizlik_sayisi, kullanilan_saglayicilar) dondurur."""
    tu.consume_translation_failures()
    tu.consume_translation_providers()
    alanlar = cevir(kayit)
    return alanlar, tu.consume_translation_failures(), tu.consume_translation_providers()


def _yaz(kayit, alanlar, saglayici):
    for alan, deger in alanlar.items():
        setattr(kayit, alan, deger)
    kayit.needs_translation = False
    kayit.translation_provider = saglayici
    kayit.save(update_fields=[*alanlar, 'needs_translation', 'translation_provider', 'updated_at'])


def _bekleyenler(ad, model, cevir, redis_client, prefix, sinir, sonuc):
    """Asama 1. Donus: (cevrilen, basarisiz, durdu)."""
    anahtar = f'{prefix}:cursor:{ad}'
    sorgu = model.objects.filter(needs_translation=True).order_by('updated_at', 'id')
    kayitlar = _imlecten_sonraki(redis_client, anahtar, sorgu, sinir)

    cevrilen = basarisiz = 0
    durdu = False
    for kayit in kayitlar:
        if not tu.herhangi_saglayici_hazir():
            durdu = True
            break
        deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)
        alanlar, hata, kullanilan = _cevir_ve_olc(cevir, kayit)

        if hata:
            if not tu.herhangi_saglayici_hazir():
                # Erisim sorunu: imleci ilerletme, bir sonraki tur once bu kaydi denesin
                durdu = True
                break
            basarisiz += 1  # icerik hatasi: imlec gecer, kayit sirada kalir
        else:
            saglayici = tu.kayit_saglayicisi(kullanilan)
            _yaz(kayit, alanlar, saglayici)
            cevrilen += 1
            if saglayici:
                sonuc['by_provider'][saglayici] += 1
        redis_client.set(anahtar, deneme_oncesi)

    if not durdu and len(kayitlar) < sinir:
        redis_client.delete(anahtar)  # sona gelindi; bir sonraki tur bastan
    return cevrilen, basarisiz, durdu


def _yukselt(ad, model, cevir, redis_client, prefix, sinir):
    """Asama 2. Yalnizca Google. Donus: yukseltilen kayit sayisi."""
    anahtar = f'{prefix}:upgrade-cursor:{ad}'
    yukseltilen = 0
    with tu.yalnizca_saglayicilar('google'):
        if not tu.herhangi_saglayici_hazir():
            return 0
        sorgu = (model.objects.filter(needs_translation=False, translation_provider='libretranslate')
                 .order_by('updated_at', 'id'))
        kayitlar = _imlecten_sonraki(redis_client, anahtar, sorgu, sinir)

        durdu = False
        for kayit in kayitlar:
            if not tu.herhangi_saglayici_hazir():
                durdu = True
                break
            deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)
            alanlar, hata, kullanilan = _cevir_ve_olc(cevir, kayit)

            if not hata and kullanilan == {'google'}:
                _yaz(kayit, alanlar, 'google')
                yukseltilen += 1
            elif not tu.herhangi_saglayici_hazir():
                durdu = True  # Google asama ortasinda kapandi; imleci ilerletme
                break
            redis_client.set(anahtar, deneme_oncesi)

        if not durdu and len(kayitlar) < sinir:
            redis_client.delete(anahtar)
    return yukseltilen


def retranslate_pending(redis_client=None, prefix: str = 'retranslate',
                        batch: int = None, upgrade_batch: int = None) -> Dict:
    redis_client = redis_client or _canli_redis()
    batch = RETRANSLATE_BATCH if batch is None else batch
    upgrade_batch = RETRANSLATE_UPGRADE_BATCH if upgrade_batch is None else upgrade_batch
    sonuc = {'translated': 0, 'failed': 0, 'upgraded': 0, 'stopped': False,
             'by_provider': {'google': 0, 'libretranslate': 0}, 'sections': {}}

    for ad, model, cevir in BOLUMLER:
        if not tu.herhangi_saglayici_hazir():
            sonuc['stopped'] = True
            break

        cevrilen, basarisiz, durdu = _bekleyenler(ad, model, cevir, redis_client, prefix, batch, sonuc)
        yukseltilen = 0 if durdu else _yukselt(ad, model, cevir, redis_client, prefix, upgrade_batch)

        if cevrilen or yukseltilen:
            cache_yenile(ad)
        sonuc['sections'][ad] = {'translated': cevrilen, 'failed': basarisiz, 'upgraded': yukseltilen}
        sonuc['translated'] += cevrilen
        sonuc['failed'] += basarisiz
        sonuc['upgraded'] += yukseltilen

        if durdu:
            sonuc['stopped'] = True
            break

    return sonuc
```

- [ ] **Step 5: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 25 tests`, `OK`

- [ ] **Step 6: Test anahtari kalmadigini dogrula**

Run: `docker compose exec -T teknoloji-redis redis-cli --scan --pattern 'test-retranslate-*' | wc -l`
Expected: `0`

- [ ] **Step 7: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 191 tests`, `OK`

- [ ] **Step 8: Commit**

```bash
git add news/retranslate.py news/tests/test_retranslate.py
git commit -m "$(cat <<'MSG'
feat: retranslate iki asamali — bekleyenler zincirle, yukseltme Google ile

Bekleyenler tam saglayici zinciriyle cevriliyor; gorev artik Google
devre kesicisi acik diye durmuyor, yalnizca hicbir saglayici hazir
degilse duruyor. LibreTranslate hizli oldugu icin bolum basina sinir
8 -> 100 (622 kayitlik birikim ilk birkac calismada erir).

Yukseltme yalnizca Google hazirken libretranslate isaretli kayitlari
yalnizca Google ile yeniden ceviriyor; tum parcalar Google'la
cevrilebilirse yaziyor (hepsi ya da hicbiri), updated_at ilerliyor ve
tuketici daha iyi ceviriyi delta akisindan aliyor. Kota icin bolum basina 5.

Donus sozlugunde stopped_by_cooldown -> stopped; upgraded ve
by_provider eklendi.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 8: API alani ve cache surumu

**Files:**
- Modify: `news/api_v1/serializers.py`, `cybernews/settings.py`
- Modify: `news/tests/test_filters.py`, `news/tests/test_cache.py`

**Interfaces:**
- Consumes: `translation_provider` (Task 5)
- Produces: v1 her kayitta `translation_provider`: `'google' | 'libretranslate' | null`; `/api/*` serializer'lari alani otomatik icerir; `CACHES['default']['VERSION'] == 3`

- [ ] **Step 1: Mevcut testleri guncelle ve yeni testleri yaz**

`news/tests/test_filters.py` — `test_ortak_alanlar_ve_ic_ice_dil` icindeki kume:

```python
        self.assertEqual(set(veri.keys()), {
            'id', 'type', 'source', 'title', 'description', 'link',
            'published_date', 'needs_translation', 'updated_at',
        })
```

su hale gelir:

```python
        self.assertEqual(set(veri.keys()), {
            'id', 'type', 'source', 'title', 'description', 'link',
            'published_date', 'needs_translation', 'updated_at', 'translation_provider',
        })
```

Ayni sinifa ekle:

```python
    def test_saglayici_bos_ise_null(self):
        entry = AINewsEntry.objects.create(
            source='Test', original_title='T', original_description='D',
            link='https://ornek.test/ai/saglayici-bos', published_date=date(2026, 9, 14))
        self.assertIsNone(AINewsEntryV1Serializer(entry).data['translation_provider'])

    def test_saglayici_degeri_doner(self):
        entry = AINewsEntry.objects.create(
            source='Test', original_title='T', original_description='D',
            link='https://ornek.test/ai/saglayici-lt', published_date=date(2026, 9, 14),
            translation_provider='libretranslate')
        self.assertEqual(AINewsEntryV1Serializer(entry).data['translation_provider'], 'libretranslate')

    def test_eski_api_serializeri_alani_icerir(self):
        from news.serializers import AINewsEntrySerializer
        entry = AINewsEntry.objects.create(
            source='Test', original_title='T', original_description='D',
            link='https://ornek.test/ai/eski-api', published_date=date(2026, 9, 14),
            translation_provider='google')
        self.assertEqual(AINewsEntrySerializer(entry).data['translation_provider'], 'google')
```

`news/tests/test_cache.py` — `CacheSurumuTests`:

```python
        self.assertEqual(settings.CACHES['default'].get('VERSION'), 2)
```

su hale gelir:

```python
        self.assertEqual(settings.CACHES['default'].get('VERSION'), 3)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_filters news.tests.test_cache -v 2 2>&1 | tail -15`
Expected: alan kumesi, iki v1 saglayici testi ve surum testi FAIL. `test_eski_api_serializeri_alani_icerir` zaten gecer (`fields='__all__'`).

- [ ] **Step 3: Serializer'i guncelle**

`news/api_v1/serializers.py` — `BaseEntrySerializer` icinde `description = serializers.SerializerMethodField()` satirinin altina:

```python
    translation_provider = serializers.SerializerMethodField()
```

`ORTAK_ALANLAR` listesini su hale getir:

```python
    ORTAK_ALANLAR = [
        'id', 'type', 'source', 'title', 'description', 'link',
        'published_date', 'needs_translation', 'updated_at', 'translation_provider',
    ]
```

`get_description` metodunun altina:

```python
    def get_translation_provider(self, obj):
        # 'google', 'libretranslate' veya ceviri yoksa null. Tuketici
        # 'libretranslate' icin "makine cevirisi" etiketi gosterebilir.
        return obj.translation_provider or None
```

- [ ] **Step 4: Cache surumunu artir**

`cybernews/settings.py` — `CACHES` icinde:

```python
        "VERSION": 2,
```

su hale gelir (ustundeki yorum ayni kalir):

```python
        "VERSION": 3,
```

- [ ] **Step 5: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_filters news.tests.test_cache -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 6: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 194 tests`, `OK`

- [ ] **Step 7: Commit**

```bash
git add news/api_v1/serializers.py cybernews/settings.py news/tests/test_filters.py news/tests/test_cache.py
git commit -m "$(cat <<'MSG'
feat: v1 kayitlarinda translation_provider; cache surumu 3

v1 her kayitta 'google', 'libretranslate' veya null donduruyor; mevcut
tuketicileri kirmayan bir ekleme. /api/* serializer'lari alani
fields='__all__' ile otomatik aliyor; cache blob sekli degistigi icin
surum 3'e cikti.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 9: Frontend "Makine çevirisi" etiketi

**Files:**
- Create: `frontend/src/components/MakineCevirisiEtiketi.jsx`
- Modify: `frontend/src/components/NewsComponent.jsx`, `CVEComponent.jsx`, `KubernetesComponent.jsx`, `SREComponent.jsx`, `DevToolsComponent.jsx`, `AINewsComponent.jsx`

**Interfaces:**
- Consumes: API kayitlarindaki `translation_provider` (Task 8)
- Produces: `export default function MakineCevirisiEtiketi({ kayit, className })` — `kayit.translation_provider === 'libretranslate'` degilse `null`; `export const makineCevirisiHtml = (kayit) => string` — HTML disa aktarma icin

Frontend'de birim test altyapisi yok; dogrulama `vite build` ile yapilir (CI da ayni derlemeyi kosar).

- [ ] **Step 1: Ortak bileseni yaz**

`frontend/src/components/MakineCevirisiEtiketi.jsx`:

```jsx
import { Badge } from 'react-bootstrap'

// LibreTranslate cevirileri Google'dan belirgin sekilde dusuk kalitelidir ve
// anlam hatasi icerebilir (spec 2026-09-14, bolum 2.4). Okuyucu uyarilir; Google
// erisilebilir oldugunda bu kayitlar otomatik olarak yukseltilir.
const ACIKLAMA =
  'LibreTranslate ile çevrildi. Google erişilebilir olduğunda otomatik olarak iyileştirilecek; anlam hatası olabilir, orijinal metne bakın.'

export default function MakineCevirisiEtiketi({ kayit, className = 'ms-2' }) {
  if (kayit?.translation_provider !== 'libretranslate') return null
  return (
    <Badge bg="warning" text="dark" className={className} title={ACIKLAMA}>
      Makine çevirisi
    </Badge>
  )
}

export const makineCevirisiHtml = (kayit) =>
  kayit?.translation_provider === 'libretranslate'
    ? `<span class="badge" style="background:#ffc107;color:#212529" title="${ACIKLAMA}">Makine çevirisi</span>`
    : ''
```

- [ ] **Step 2: Bes bilesene liste ve detay etiketini ekle**

`NewsComponent.jsx`, `KubernetesComponent.jsx`, `SREComponent.jsx`, `DevToolsComponent.jsx`, `AINewsComponent.jsx` dosyalarinin **her birinde**:

1. `react-bootstrap` import blogunun altina ekle:

```jsx
import MakineCevirisiEtiketi from './MakineCevirisiEtiketi'
```

2. **Liste:** Liste ogesinde `item.turkish_title` gosteren `<h6 className="mb-1 fw-bold">` blogunu kapatan `</h6>` satirinin hemen altina ekle:

```jsx
                      <MakineCevirisiEtiketi kayit={item} className="mt-1" />
```

3. **Detay:** Detay modalinda basligi gosteren `<h5 className="fw-bold mb-3">` blogunun kapanisindan (`</h5>`) hemen sonra ekle. Degisken adi bilesene gore degisir:

| Dosya | Eklenecek satir |
|---|---|
| `NewsComponent.jsx` | `<MakineCevirisiEtiketi kayit={selectedNews} className="mb-3" />` |
| `KubernetesComponent.jsx`, `SREComponent.jsx`, `DevToolsComponent.jsx`, `AINewsComponent.jsx` | `<MakineCevirisiEtiketi kayit={selectedEntry} className="mb-3" />` |

`NewsComponent.jsx`'te modal basligi tek satirdir: `<h5 className="fw-bold mb-3">{selectedNews.turkish_title}</h5>` — etiketi bu satirin altina koy.

- [ ] **Step 3: CVE bilesenine ekle**

`CVEComponent.jsx`:

1. `react-bootstrap` import blogunun altina:

```jsx
import MakineCevirisiEtiketi, { makineCevirisiHtml } from './MakineCevirisiEtiketi'
```

2. **Liste:** `<h6 className="mb-1 fw-bold">{item.cve_id}</h6>` satirinin hemen altina:

```jsx
                      <MakineCevirisiEtiketi kayit={item} className="mb-1" />
```

3. **Detay:** CVE'lerde cevrilen alan aciklamadir. `<h6 className="fw-bold text-danger">Açıklama</h6>` satirinin hemen altina:

```jsx
                    <MakineCevirisiEtiketi kayit={selectedCVE} className="mb-2" />
```

4. **HTML disa aktarma:** Sablondaki su satiri:

```
  <span class="badge" style="background:${severityColor(item.severity)}">${item.severity || 'Bilinmiyor'}</span>
```

su hale getir:

```
  <span class="badge" style="background:${severityColor(item.severity)}">${item.severity || 'Bilinmiyor'}</span>
  ${makineCevirisiHtml(item)}
```

- [ ] **Step 4: Eklemeleri say**

```bash
cd frontend/src/components && for f in NewsComponent KubernetesComponent SREComponent DevToolsComponent AINewsComponent CVEComponent; do printf "%-22s %s\n" $f "$(grep -c 'MakineCevirisiEtiketi' $f.jsx)"; done; grep -c 'makineCevirisiHtml' CVEComponent.jsx; cd -
```

Expected: bes bilesende `3` (import + liste + detay), `CVEComponent` `3`, son satir `2` (import + sablon).

- [ ] **Step 5: Derle**

Run: `docker compose exec -T teknoloji-frontend npx vite build --outDir /tmp/vite-dogrulama --emptyOutDir 2>&1 | tail -5`
Expected: `✓ built in ...`; hata yok. Cikti konteynerin `/tmp` dizinine yazilir, bind mount'taki `dist/`'e dokunulmaz.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "$(cat <<'MSG'
feat(frontend): LibreTranslate cevirilerinde "Makine çevirisi" etiketi

Alti bolumde listede ve detayda, CVE HTML disa aktarmasinda kucuk bir
uyari etiketi. Uzerine gelince cevirinin LibreTranslate'ten geldigini,
anlam hatasi olabilecegini ve Google acilinca iyilestirilecegini
soyluyor. Metin tek bir ortak bilesende.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 10: Compose'a LibreTranslate servisi

**Files:**
- Modify: `docker-compose.yml`

**Interfaces:**
- Consumes: `settings.LIBRETRANSLATE_URL` (Task 1)
- Produces: `teknoloji-translate` servisi (ic ag, port acik degil); `teknoloji-translate-models` volume; `teknoloji-api` ve `teknoloji-worker` ortaminda `LIBRETRANSLATE_URL=http://teknoloji-translate:5000`

Bu task konteyner **baslatmaz**; yalnizca tanimi yazar ve dogrular.

- [ ] **Step 1: Servisi ekle**

`docker-compose.yml` — `# Redis Cache & Message Broker` yorumundan **once** ekle:

```yaml
  # LibreTranslate (yedek ceviri saglayicisi; Google kapaliyken devreye girer)
  teknoloji-translate:
    image: libretranslate/libretranslate:v1.9.6
    container_name: teknoloji-translate
    environment:
      - LT_LOAD_ONLY=en,tr
      - LT_UPDATE_MODELS=false
    volumes:
      # Modeller imajda yok, ilk acilista iner (258 MB). Volume olmazsa her
      # yeniden olusturmada tekrar iner ve internet yoksa servis acilmaz.
      - teknoloji-translate-models:/home/libretranslate/.local
    # Denemede yuk altinda 12 cekirdegin tamamini doyurdu; diger servisleri ac birakmasin
    cpus: '4'
    mem_limit: 2g
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:5000/languages', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 120s
    restart: unless-stopped
    networks:
      - teknoloji-network

```

Port **eklenmez**: servis kimlik dogrulamasizdir, yalnizca ic agdan erisilir.

- [ ] **Step 2: API ve worker'a adresi ekle**

`teknoloji-api` ve `teknoloji-worker` servislerinin `environment` listelerinde `- CELERY_BROKER_URL=redis://teknoloji-redis:6379/1` satirinin altina:

```yaml
      - LIBRETRANSLATE_URL=http://teknoloji-translate:5000
```

`teknoloji-scheduler`'a **eklenmez** (ceviri yapmaz). `depends_on` **eklenmez**: LibreTranslate yedektir, acilmamis olmasi api veya worker'in baslamasini engellememelidir.

- [ ] **Step 3: Volume'u ekle**

Dosya sonundaki `volumes:` blogunu su hale getir:

```yaml
volumes:
  teknoloji-redis-data:
  teknoloji-translate-models:
```

- [ ] **Step 4: Dogrula**

```bash
docker compose config --quiet && echo GECERLI
docker compose config --services | grep -c teknoloji-translate
docker compose config | grep -c "LIBRETRANSLATE_URL: http://teknoloji-translate:5000"
docker compose config | grep -A1 "teknoloji-translate-models" | head -4
```

Expected: `GECERLI`, `1`, `2` (api + worker), volume tanimi gorunur.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "$(cat <<'MSG'
feat(compose): LibreTranslate servisi

libretranslate/libretranslate:v1.9.6, yalnizca en/tr modelleri, modeller
kalici volume'da, 4 CPU / 2 GB sinir, healthcheck, disa port yok.
api ve worker LIBRETRANSLATE_URL ile baglaniyor; depends_on bilincli
olarak yok, servis yedek oldugu icin acilisi engellememeli.

Helm chart Faz B'de guncellenecek.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 11: Canli dagitim ve dogrulama

Kod yazmaz. **Canli veriyi degistirir** (migration, bekleyen kayitlarin cevirisi) ve konteynerleri yeniden olusturur. **Baslamadan once kullaniciya haber ver ve onay al.**

**Files:** degistirilmez

- [ ] **Step 1: Calisan is olmadigini dogrula**

Run: `docker compose exec -T teknoloji-worker celery -A cybernews inspect active 2>&1 | grep -E "empty|name"`
Expected: `- empty -`. Bos degilse bitmesini bekle.

- [ ] **Step 2: Veritabani yedegi**

```bash
docker compose exec -T teknoloji-api python -c "
import sqlite3
k = sqlite3.connect('/app/db.sqlite3'); h = sqlite3.connect('/tmp/db-yedek-ceviri-zinciri.sqlite3')
k.backup(h); h.close(); k.close()
print(sqlite3.connect('/tmp/db-yedek-ceviri-zinciri.sqlite3').execute('pragma integrity_check').fetchone()[0])"
docker cp teknoloji-api:/tmp/db-yedek-ceviri-zinciri.sqlite3 ../db-yedek-ceviri-zinciri-$(date +%Y%m%d-%H%M).sqlite3
```

Expected: `ok`; yedek dosyasi git kokunun bir ust dizininde (repoya girmez).

- [ ] **Step 3: LibreTranslate servisini baslat ve saglikli olmasini bekle**

```bash
docker compose up -d teknoloji-translate
for i in $(seq 1 40); do d=$(docker inspect -f '{{.State.Health.Status}}' teknoloji-translate); echo "$i: $d"; [ "$d" = "healthy" ] && break; sleep 10; done
docker compose exec -T teknoloji-translate sh -c 'ls /home/libretranslate/.local/share/argos-translate/packages; du -sh /home/libretranslate/.local'
```

Expected: `healthy`; `translate-en_tr-1_5` ve `translate-tr_en-1_5`; ~258 MB.

- [ ] **Step 4: Worker ve scheduler'i DURDUR (migration oncesi)**

```bash
docker compose stop teknoloji-worker teknoloji-scheduler
```

Gerekce: migration `NOT NULL` sutun ekler; eski kodla calisan worker bu sirada kayit eklerse patlar (2026-09-12 regresyonu).

- [ ] **Step 5: Migration'i uygula**

Run: `docker compose exec -T teknoloji-api python manage.py migrate news`
Expected: `Applying news.0009_translation_provider... OK`

- [ ] **Step 6: Surecleri yeni ortam degiskeniyle yeniden OLUSTUR**

```bash
docker compose up -d --force-recreate teknoloji-api teknoloji-worker teknoloji-scheduler
docker compose exec -T teknoloji-api printenv LIBRETRANSLATE_URL
docker compose exec -T teknoloji-worker printenv LIBRETRANSLATE_URL
docker compose logs --since 2m teknoloji-worker 2>&1 | grep -E "ready\.|ERROR" | tail -2
```

Expected: iki kez `http://teknoloji-translate:5000`; worker `ready.`, `ERROR` yok. (`restart` yeni ortam degiskenini almaz; `--force-recreate` sart.)

- [ ] **Step 7: Worker'dan saglayici durumunu gor**

```bash
docker compose exec -T teknoloji-worker python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings'); django.setup()
from news import translation_providers as tp, translation_utils as tu
print({s.name: s.available() for s in tp.SAGLAYICILAR})
print('LibreTranslate deneme:', tp.LibreTranslateProvider().translate('The attacker can read arbitrary files on the server.'))"
```

Expected: `libretranslate: True`; Turkce bir cumle. `google` degeri `False` olabilir (devre kesici acik) — beklenir.

- [ ] **Step 8: Test paketini canli ortamda kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`. Bu calisma `LIBRETRANSLATE_URL` tanimli konteynerde yapildigi icin `TestOrtamiIzolasyonuTests`'in gecmesi Task 1'in canlida calistigini kanitlar.

- [ ] **Step 9: Onceki durumu kaydet**

```bash
docker compose exec -T teknoloji-api python - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybernews.settings'); django.setup()
from news.models import NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry
for m in (NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry):
    q = m.objects
    print(f"{m.__name__:16s} bekleyen={q.filter(needs_translation=True).count():4d} "
          f"google={q.filter(translation_provider='google').count():4d} "
          f"libre={q.filter(translation_provider='libretranslate').count():4d} toplam={q.count()}")
PY
```

Expected: `libre=0`; `google` degerleri Task 5 veri adiminin sonucunu gosterir.

- [ ] **Step 10: Retranslate'i calisan worker'da bir kez calistir**

```bash
docker compose exec -T teknoloji-api python - <<'PY'
import os, time, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybernews.settings'); django.setup()
from news.tasks import retranslate_pending_task
is_ = retranslate_pending_task.delay()
t = time.time()
print('sonuc:', is_.get(timeout=3600))
print(f'sure: {time.time() - t:.0f} sn')
PY
```

Expected: `stopped: False`; `translated` yuzlerle; Google kapaliysa `by_provider['libretranslate']` buyuk. Sonucta `error` veya istisna yok.

- [ ] **Step 11: Sonraki durumu kaydet ve karsilastir**

Step 9'daki komutu tekrar calistir.
Expected: bekleyen sayilari belirgin dustu (CVE'de 100'e kadar, digerlerinde bolum boyutu kadar); `libre` artti.

- [ ] **Step 12: Bozuk ceviri kalmadigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py bozuk_cevirileri_isaretle | tail -1`
Expected: `TOPLAM: 0`

- [ ] **Step 13: Bir kac LibreTranslate cevirisini gozle**

```bash
docker compose exec -T teknoloji-api python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings'); django.setup()
from news.models import CVEEntry, AINewsEntry
for m in (CVEEntry, AINewsEntry):
    for o in m.objects.filter(translation_provider='libretranslate').order_by('-updated_at')[:2]:
        print(m.__name__, o.id, '|', (o.turkish_description or '')[:220].replace(chr(10), ' '), '\n')"
```

Ciktiyi kullaniciya goster; kalite degerlendirmesi onun.

- [ ] **Step 14: API ve cache**

```bash
TOKEN=$(docker compose exec -T teknoloji-api python -c "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings');django.setup();from rest_framework.authtoken.models import Token;print(Token.objects.get(user__username='entegrasyon').key)" | tr -d '\r')
curl -s -H "Authorization: Token $TOKEN" "http://localhost:8000/api/v1/ai/?limit=500" | python -c "import sys,json,collections; d=json.load(sys.stdin); print(collections.Counter(r['translation_provider'] for r in d['results']))"
curl -s http://localhost:8000/api/ai/ | python -c "import sys,json; d=json.load(sys.stdin)['data']; print('eski api alani:', 'translation_provider' in d[0])"
docker compose exec -T teknoloji-redis redis-cli --scan --pattern ':3:ai_entries'
```

Expected: sayac `google`, `libretranslate` ve belki `None` iceriyor; `eski api alani: True`; `:3:ai_entries`.

- [ ] **Step 15: Frontend**

```bash
curl -s -o /dev/null -w "etiket bileseni -> %{http_code}\n" http://localhost:3000/src/components/MakineCevirisiEtiketi.jsx
curl -s -o /dev/null -w "frontend        -> %{http_code}\n" http://localhost:3000/
```

Expected: ikisi de `200`. Kullanicidan `http://localhost:3000` uzerinde AI sekmesinde "Makine çevirisi" etiketini gormesini ve uzerine gelince aciklamayi okumasini iste.

- [ ] **Step 16: LibreTranslate dusunce sistem calismaya devam ediyor mu**

```bash
docker compose stop teknoloji-translate
docker compose exec -T teknoloji-worker python -c "
import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings'); django.setup()
from news import translation_utils as tu
tu.consume_translation_failures()
metin = 'Researchers found a new flaw in the login page today.'
print('sonuc ayni mi (orijinal):', tu.translate_text(metin) == metin)
print('basarisizlik:', tu.consume_translation_failures())
print('hazir saglayici var mi:', tu.herhangi_saglayici_hazir())"
docker compose start teknoloji-translate
for i in $(seq 1 20); do d=$(docker inspect -f '{{.State.Health.Status}}' teknoloji-translate); [ "$d" = "healthy" ] && break; sleep 10; done; echo "tekrar: $d"
docker compose logs --since 5m teknoloji-translate 2>&1 | grep -c "Downloading"
```

Expected: istisna yok; Google da kapaliysa `sonuc ayni mi (orijinal): True`, `basarisizlik: 1`, `hazir saglayici var mi: False` (LibreTranslate devre kesicisi acildi). Servis `healthy` doner; son satir `0` (modeller volume'dan geldi, yeniden inmedi).

- [ ] **Step 17: Son test ve push**

```bash
docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"
git push -u origin feat/ceviri-saglayici-zinciri
```

Expected: `OK`; dal push edildi.

---

## Bitis Kriterleri

- [ ] Google kapaliyken bekleyen kayitlar LibreTranslate ile cevriliyor; retranslate durmuyor (Task 11 Step 10-11)
- [ ] Her kayitta `translation_provider`; eski cevrilmis kayitlar `google`, `updated_at` ilerlemedi
- [ ] Google acikken LibreTranslate cevirileri yalnizca Google ile ve hepsi-ya-da-hicbiri kuraliyla yukseltiliyor (testler)
- [ ] v1 ve `/api/*` alani donduruyor; frontend etiketi gorunuyor
- [ ] LibreTranslate dusunce hicbir cagri patlamiyor; geri gelince modeller yeniden inmiyor
- [ ] Hicbir test gercek Google'a, gercek LibreTranslate'e veya canli devre kesicisine dokunmuyor; test paketi yesil

## Sonrasi

- **A4:** `FetchRun`'a `translation_failures` yaninda `by_provider` da yazilmali (spec bolum 12). A4 de migration icerir: worker/scheduler durdurma adimi A4 planinda da acikca yer almali.
- **Faz B notu:** Helm'e LibreTranslate Deployment + Service + PVC + kaynak sinirlari + `LIBRETRANSLATE_URL`.
- **A5 notu:** README'ye `LIBRETRANSLATE_*`, `RETRANSLATE_UPGRADE_BATCH`, yeni servis ve etiket.
