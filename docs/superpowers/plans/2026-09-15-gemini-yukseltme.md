# Gemini ile Kayit Duzeyinde Ceviri Yukseltme — Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cekim aninda yalniz LibreTranslate ile aninda Turkce; `retranslate_pending` bekleyen ve LibreTranslate kayitlarini Gemini API ile kayit basina tek istekle Gemini kalitesine yukseltir; Google Translate kazima yolu tamamen kalkar; her kayit saglayici rozeti tasir.

**Architecture:** Yeni `news/gemini.py` tek genel fonksiyon sunar: `kaydi_cevir(alanlar) -> dict | None` (JSON modu, Redis paylasimli aralik kapisi, gunluk istek butcesi, devre kesici). `news/retranslate.py` iki asamasinda once Gemini'yi dener: bekleyenlerde Gemini basarisizsa mevcut LibreTranslate zincirine duser; yukseltme yalniz Gemini ile yapilir. `translation_utils` ve `translation_providers`'dan Google (`GtxTranslator`, `_translate_via_google`, `GoogleProvider`, `curl_cffi`) silinir; `_RedisGate`/`_LocalGate` ve A3 dogrulama yardimcilari kalir. Frontend'de `MakineCevirisiEtiketi` → saglayici bazli `CeviriEtiketi`.

**Tech Stack:** Django 4.2.7, DRF 3.17.2, Celery 5.3.4, django-redis 5.4.0, `requests` 2.31.0 (zaten var), React 18 + react-bootstrap (Vite 5), Gemini API `v1beta generateContent` (`gemini-3.5-flash-lite`). **Yeni pip/npm bagimliligi yok; `curl_cffi` cikar.**

**Spec:** `docs/superpowers/specs/2026-09-15-gemini-yukseltme-design.md` — once onu oku.

**Onceki planlar:** `2026-09-14-ceviri-saglayici-zinciri.md` (retranslate iki asama, LibreTranslate), A3 plani (dogrulama, imlec kurallari).

## Global Constraints

- **Hicbir test gercek Gemini'ye, gercek LibreTranslate'e veya gercek Google'a gitmez.** Gemini HTTP'si `mock.patch('news.gemini.requests.post')` ile; LibreTranslate testleri mevcut kaliplariyla (`mock.patch('news.translation_providers.requests.post')`). `GuvenliTestRunner` testlerde `GEMINI_API_KEY`'i bosaltir ve Gemini kapisi/butcesini surec ici tutar.
- **Hicbir test gercek Celery isi kuyruga atmaz.** Retranslate testleri `retranslate_pending()`'i dogrudan cagirir.
- **Redis anahtari yazan testler benzersiz onek kullanir ve kendi anahtarlarini siler.** `FLUSHDB`/`FLUSHALL` yasak; db 0 canli cache. `news.tests.base.test_redis_client()` ve `uuid4().hex` onek kalibi.
- **Anahtar (`GEMINI_API_KEY`) hicbir dosyaya, loga, hata mesajina, commit'e girmez.** Kod `settings.GEMINI_API_KEY`'i okur; deger `cybersecurity_news/.env`'den (gitignore'da, 2026-09-15'te yerine kondu) compose ile gelir. Task'lar `.env`'i okumaz, yazmaz, `cat` etmez.
- **Saglayici adlari sabittir:** `'gemini'`, `'libretranslate'`, `'google'` (eski kayitlar; yeni uretilmez).
- **Kota degerleri (spec 1.1):** `GEMINI_DAILY_BUDGET=400`, `GEMINI_MIN_INTERVAL=5`, `GEMINI_COOLDOWN=600`, `GEMINI_TIMEOUT=60`, `GEMINI_MODEL=gemini-3.5-flash-lite`, `RETRANSLATE_UPGRADE_BATCH=40`.
- **Gemini ciktisina `turkish_post_process` ve `XTRM` yer tutucu korumasi uygulanmaz** (spec 3.2).
- **Kod yorumlari aksansiz Turkce; frontend kullanici metinleri Turkce karakterli** (mevcut kalip: "Makine çevirisi").
- **`news/views.py`, `/api/*` ve v1 URL'leri degismez.** Serializer'lar `translation_provider`'i zaten donduruyor.
- **Testler konteyner icinde:** `docker compose exec -T teknoloji-api python manage.py test news`
- **Her task kendi commit'ini atar;** mesaj Turkce, aksansiz, sonu `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>` (uygulayan model neyse o).
- **Calisma dali:** `feat/gemini-yukseltme`. Bu planin ve spec'in bulundugu `docs/gemini-yukseltme` dali `main`'e alindiktan sonra guncel `main`'den acilir (`git checkout main && git pull --ff-only && git checkout -b feat/gemini-yukseltme`).
- **Task 6 canli sisteme dokunur** (imaj, ortam degiskeni, gercek Gemini istegi). Task 6'ya baslamadan kullaniciya haber ver.

## Ortam Notlari (yeni bir context icin)

| Konu | Deger |
|---|---|
| Proje / git koku | `cybersecurity_news/` |
| Konteynerlar | `teknoloji-api` (gunicorn), `teknoloji-worker`, `teknoloji-scheduler`, `teknoloji-redis`, `teknoloji-translate` (LibreTranslate), `teknoloji-frontend` (Vite dev) |
| Kod yeniden yukleme | Yok. Python degisikligi → `docker compose restart teknoloji-api teknoloji-worker`; **ortam degiskeni degisikligi → `docker compose up -d --force-recreate <servis>`**; **`requirements.txt` degisikligi → `docker compose build teknoloji-api` + force-recreate api/worker/scheduler**; **frontend degisikligi → `docker compose restart teknoloji-frontend`** (Windows bind mount'ta Vite HMR tetiklenmiyor; Task 5 bunu `usePolling` ile duzeltir) |
| Mevcut test sayisi | 208 (~3.5 sn) |
| Son migration | `0009_translation_provider` |
| Ceviri durumu (2026-09-15 12:50) | 1305 kayit, 92 bekleyen; saglayici: libretranslate 978, google 256, bos 71 |
| Canli Redis anahtarlari | `retranslate:cursor:*`, `retranslate:upgrade-cursor:*`, `libretranslate:cooldown`, `translate:*` (Google kapisi; Task 4 sonrasi olu) |
| Test Redis yardimcisi | `news/tests/base.py::test_redis_client()` |
| Mevcut sahte saglayici | `news/tests/saglayici_yardimcilari.py::SahteSaglayici(name, cevap, hazir)` + `SaglayiciZinciriMixin.saglayicilari_ayarla(...)` |

## Mevcut Kodda Dikkat Edilecekler

1. `translation_utils.translate_text` saglayicilari `saglayicilar()` uzerinden `tp.SAGLAYICILAR`'dan okur; `yalnizca_saglayicilar` yalniz `retranslate._yukselt` tarafindan kullanilir (Task 3'te kullanim biter, Task 4'te silinir).
2. `tests/test_translation.py::TranslationGateMixin.use_translator` `tu._make_translator`'i mock'lar; ~60 test buna dayanir (`test_translation`, `test_retranslate`, `test_cache`, `test_filters`, `test_haber_aciklamasi`, `test_migrations_0009`, `test_translation_verify`). Task 4 bu mixin'i LibreTranslate'e cevirir; testlerin govdesi degismez.
3. `retranslate._yaz(kayit, alanlar, saglayici)` `update_fields=[*alanlar, 'needs_translation', 'translation_provider', 'updated_at']` yazar — Gemini yolunda `alanlar` DB alan adlariyla (`turkish_title`, `turkish_description`) verilmelidir.
4. CVE kurali: baslik cevrilmez, 30 karakterden kisa aciklama oldugu gibi kalir (`retranslate._cve`). Haber kurali (2026-09-15): orijinal aciklama bossa `turkish_description`'a dokunulmaz.
5. `tu.MIN_RATIO`, `tu._normalize_for_echo`, `tu._RedisGate`, `tu._LocalGate` Task 4'ten sonra da kalir; Gemini bunlari kullanir.
6. Frontend'de `MakineCevirisiEtiketi` 6 bilesende 18 yerde kullaniliyor (`import` + JSX; CVE'de ayrica `makineCevirisiHtml`).

## Dosya Yapisi

| Dosya | Sorumluluk | Task |
|---|---|---|
| `news/gemini.py` (yeni) | Gemini istemcisi: `hazir()`, `butce_var()`, `butce_kullanimi()`, `kaydi_cevir()`, butce/kapi/devre kesici | 1 |
| `cybernews/settings.py` | `GEMINI_API_KEY` ayari | 1 |
| `news/test_runner.py` | Testlerde anahtar bos, Gemini kapi/butce surec ici; `tu._gate` satiri kalkar | 1, 4 |
| `news/tests/test_gemini.py` (yeni) | Gemini istemcisi testleri | 1 |
| `news/models.py`, `news/migrations/0010_translation_provider_gemini.py` | `gemini` secenegi | 2 |
| `news/retranslate.py` | Gemini-once bekleyenler, yalniz-Gemini yukseltme, `stopped_reason`, `UPGRADE_BATCH=40` | 3 |
| `news/tests/test_retranslate.py` | Gemini asama testleri; Google yukseltme testleri kalkar | 3, 4 |
| `news/translation_utils.py`, `news/translation_providers.py`, `requirements.txt` | Google ve `curl_cffi` kaldirma | 4 |
| `news/tests/test_translation.py`, `test_translation_chain.py`, `test_translation_providers.py`, `test_google_gtx.py` | Google testleri kaldirma, mixin'i LibreTranslate'e cevirme | 4 |
| `frontend/src/components/CeviriEtiketi.jsx` (yeni, eskisinin yerine), 6 bilesen, `frontend/vite.config.js` | Saglayici rozeti; dev proxy `/admin`,`/static`; `usePolling` | 5 |
| `docker-compose.yml` | `GEMINI_API_KEY` api + worker | 6 |
| `README.md`, `docs/ADR-0004-*.md`, spec durum satiri | Belgeler | 7 |

---

### Task 1: `news/gemini.py` — Gemini istemcisi

**Files:**
- Create: `news/gemini.py`
- Modify: `cybernews/settings.py` (LIBRETRANSLATE_URL satirinin altina), `news/test_runner.py`
- Test: `news/tests/test_gemini.py`

**Interfaces:**
- Consumes: `tu._RedisGate(client, prefix)`, `tu._LocalGate()`, `tu.MIN_RATIO`, `tu._normalize_for_echo`, `settings.GEMINI_API_KEY`
- Produces (Task 3 bunlara dayanir):
  - `gemini.hazir() -> bool` — anahtar dolu ve devre kesici kapali ve gunluk butce var
  - `gemini.butce_var() -> bool`, `gemini.butce_kullanimi() -> int`, `gemini.butce_anahtari() -> str`
  - `gemini.kaydi_cevir(alanlar: Dict[str, str]) -> Optional[Dict[str, str]]` — ayni anahtarlarla Turkce; `None` cevrilemedi
  - Modul globalleri (testler patch'ler): `gemini._gate`, `gemini._butce`, `gemini.GEMINI_MIN_INTERVAL`, `gemini.GEMINI_DAILY_BUDGET`
  - Siniflar: `gemini._LocalButce`, `gemini._RedisButce(client, prefix='gemini')`

- [ ] **Step 1: Ayar ve test calistiricisi**

`cybernews/settings.py` — `LIBRETRANSLATE_URL` satirinin hemen altina:

```python
# Gemini API (retranslate'te kayit duzeyinde yukseltme; bkz. news/gemini.py).
# Bos ise Gemini hic denenmez. Deger yalniz ortam degiskeninden gelir.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
```

`news/test_runner.py` — `setup_test_environment` icine, `tp._lt_gate = tu._LocalGate()` satirindan sonra:

```python
        # Hicbir test gercek Gemini'ye gitmez: anahtar bos, kapi ve butce surec ici.
        self._gemini_kapali = override_settings(GEMINI_API_KEY='')
        self._gemini_kapali.enable()
        from news import gemini
        gemini._gate = tu._LocalGate()
        gemini._butce = gemini._LocalButce()
```

ve `teardown_test_environment` icine `self._libretranslate_kapali.disable()` satirindan sonra `self._gemini_kapali.disable()`.

Dokumantasyon satirini da guncelle (dosya basindaki docstring'e 3. madde): `3. Hicbir test gercek Gemini'ye gitmez: GEMINI_API_KEY bos, kapi/butce surec ici; Gemini testleri anahtari override_settings ile verir ve HTTP'yi mock'lar.`

- [ ] **Step 2: Basarisiz testleri yaz**

`news/tests/test_gemini.py`:

```python
"""Gemini istemcisi (spec 2026-09-15-gemini-yukseltme, bolum 3.2). Ag erisimi yok."""
import json
import uuid
from unittest import mock

import requests
from django.test import SimpleTestCase, TestCase, override_settings

from news import gemini
from news import translation_utils as tu
from news.tests.base import test_redis_client

ANAHTAR = 'test-anahtar'


def _yanit(durum=200, govde=None, metin=None, finish='STOP', ham=''):
    """Gemini generateContent yaniti. govde: modelin JSON ciktisi (dict); metin: ham part metni."""
    yanit = mock.Mock(status_code=durum, text=ham)
    if durum != 200:
        yanit.json.side_effect = ValueError('JSON degil')
        return yanit
    part = metin if metin is not None else json.dumps(govde, ensure_ascii=False)
    yanit.json.return_value = {'candidates': [{'finishReason': finish, 'content': {'parts': [{'text': part}]}}]}
    return yanit


class GeminiTestMixin:
    """Anahtar dolu, kapi/butce surec ici, bekleme yok. (override_settings mixin'e dekorator olarak
    uygulanamaz — yalniz SimpleTestCase alt siniflarina; bu yuzden setUp'ta enable edilir.)"""

    def setUp(self):
        super().setUp()
        ayar = override_settings(GEMINI_API_KEY=ANAHTAR)
        ayar.enable()
        self.addCleanup(ayar.disable)
        for hedef, deger in (('_gate', tu._LocalGate()), ('_butce', gemini._LocalButce()),
                             ('GEMINI_MIN_INTERVAL', 0.0)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)

    def _post(self, *yanitlar, side_effect=None):
        if side_effect is not None:
            yama = mock.patch('news.gemini.requests.post', side_effect=side_effect)
        elif len(yanitlar) == 1:
            yama = mock.patch('news.gemini.requests.post', return_value=yanitlar[0])
        else:
            yama = mock.patch('news.gemini.requests.post', side_effect=list(yanitlar))
        post = yama.start()
        self.addCleanup(yama.stop)
        return post


ALANLAR = {'title': 'Attackers exploit a new flaw in the parser',
           'description': 'Unauthenticated attackers can execute arbitrary code remotely by sending a crafted request.'}
CEVIRI = {'title': 'Saldırganlar ayrıştırıcıdaki yeni bir açığı istismar ediyor',
          'description': 'Kimliği doğrulanmamış saldırganlar özel hazırlanmış bir istek göndererek uzaktan rastgele kod çalıştırabilir.'}


class GeminiHazirlikTests(GeminiTestMixin, SimpleTestCase):

    def test_anahtar_yoksa_hazir_degil_ve_istek_atilmaz(self):
        post = self._post(_yanit(govde=CEVIRI))
        with override_settings(GEMINI_API_KEY=''):
            self.assertFalse(gemini.hazir())
            self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertEqual(post.call_count, 0)

    def test_anahtar_varsa_hazir(self):
        self.assertTrue(gemini.hazir())

    def test_devre_kesici_acikken_hazir_degil(self):
        gemini._gate.start_cooldown(60)
        self.assertFalse(gemini.hazir())


class GeminiIstekTests(GeminiTestMixin, SimpleTestCase):

    def test_istek_sekli(self):
        post = self._post(_yanit(govde=CEVIRI))
        gemini.kaydi_cevir(ALANLAR)
        args, kwargs = post.call_args
        self.assertEqual(args[0], 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent')
        self.assertEqual(kwargs['headers']['x-goog-api-key'], ANAHTAR)
        self.assertEqual(kwargs['timeout'], gemini.GEMINI_TIMEOUT)
        govde = kwargs['json']
        self.assertEqual(govde['generationConfig']['responseMimeType'], 'application/json')
        self.assertEqual(set(govde['generationConfig']['responseSchema']['properties']), {'title', 'description'})
        self.assertEqual(govde['generationConfig']['responseSchema']['required'], ['title', 'description'])
        self.assertEqual(json.loads(govde['contents'][0]['parts'][0]['text']), ALANLAR)
        self.assertIn('AYNEN', govde['systemInstruction']['parts'][0]['text'])

    def test_basarili_yanit_alanlari_dondurur(self):
        self._post(_yanit(govde=CEVIRI))
        self.assertEqual(gemini.kaydi_cevir(ALANLAR), CEVIRI)

    def test_bos_alanlar_gonderilmez(self):
        post = self._post(_yanit(govde={'title': CEVIRI['title']}))
        sonuc = gemini.kaydi_cevir({'title': ALANLAR['title'], 'description': '   '})
        self.assertEqual(sonuc, {'title': CEVIRI['title']})
        self.assertEqual(set(post.call_args.kwargs['json']['generationConfig']['responseSchema']['properties']), {'title'})

    def test_hepsi_bossa_istek_yok(self):
        post = self._post(_yanit(govde={}))
        self.assertIsNone(gemini.kaydi_cevir({'title': '', 'description': ' '}))
        self.assertEqual(post.call_count, 0)

    def test_hicbir_istisna_sizmaz(self):
        self._post(side_effect=RuntimeError('beklenmeyen'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())


class GeminiDogrulamaTests(GeminiTestMixin, SimpleTestCase):

    def test_bos_ceviri_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': ''}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_eksik_alan_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title']}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_kirpilmis_ceviri_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': 'Kısa.'}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_asiri_uzun_ceviri_reddedilir(self):
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': 'x' * (len(ALANLAR['description']) * 4)}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_yanki_reddedilir(self):
        self._post(_yanit(govde={'title': ALANLAR['title'].upper(), 'description': CEVIRI['description']}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))

    def test_kisa_metin_ayni_kalabilir(self):
        # 'Kubernetes 1.31 released' 3 kelime: mesru olarak ayni kalabilir
        self._post(_yanit(govde={'title': 'Kubernetes 1.31 released'}))
        self.assertEqual(gemini.kaydi_cevir({'title': 'Kubernetes 1.31 released'}), {'title': 'Kubernetes 1.31 released'})

    def test_hepsi_ya_da_hicbiri(self):
        # Bir alan gecemezse gecen alan da donmez
        self._post(_yanit(govde={'title': CEVIRI['title'], 'description': ''}))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))


class GeminiHataTests(GeminiTestMixin, SimpleTestCase):

    def test_429_devre_kesiciyi_acar_butceyi_geri_almaz(self):
        self._post(_yanit(durum=429, ham='{"error": {"status": "RESOURCE_EXHAUSTED"}}'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertTrue(gemini._gate.cooldown_active())
        self.assertFalse(gemini.hazir())
        self.assertEqual(gemini.butce_kullanimi(), 1)

    def test_5xx_devre_kesiciyi_acar(self):
        self._post(_yanit(durum=503))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertTrue(gemini._gate.cooldown_active())

    def test_baglanti_hatasi_devre_kesiciyi_acar(self):
        self._post(side_effect=requests.ConnectionError('kopuk'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertTrue(gemini._gate.cooldown_active())

    def test_401_devre_kesici_acmaz_butce_geri_alinir(self):
        self._post(_yanit(durum=401, ham='{"error": {"status": "UNAUTHENTICATED"}}'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())
        self.assertEqual(gemini.butce_kullanimi(), 0)
        self.assertTrue(gemini.hazir())

    def test_safety_finish_reason_reddedilir(self):
        self._post(_yanit(govde=CEVIRI, finish='SAFETY'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())

    def test_bozuk_json_reddedilir(self):
        self._post(_yanit(metin='{"title": "yarim'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertFalse(gemini._gate.cooldown_active())

    def test_json_dict_degilse_reddedilir(self):
        self._post(_yanit(metin='["liste"]'))
        self.assertIsNone(gemini.kaydi_cevir(ALANLAR))


class GeminiButceTests(GeminiTestMixin, SimpleTestCase):

    def test_gunluk_butce_asilmaz(self):
        with mock.patch.object(gemini, 'GEMINI_DAILY_BUDGET', 2):
            post = self._post(_yanit(govde=CEVIRI))
            self.assertEqual(gemini.kaydi_cevir(ALANLAR), CEVIRI)
            self.assertEqual(gemini.kaydi_cevir(ALANLAR), CEVIRI)
            self.assertFalse(gemini.butce_var())
            self.assertFalse(gemini.hazir())
            self.assertIsNone(gemini.kaydi_cevir(ALANLAR))
        self.assertEqual(post.call_count, 2)
        self.assertEqual(gemini.butce_kullanimi(), 2)

    def test_butce_anahtari_utc_gun(self):
        self.assertRegex(gemini.butce_anahtari(), r'^budget:\d{4}-\d{2}-\d{2}$')


class RedisButceTests(TestCase):

    def setUp(self):
        self.redis = test_redis_client()
        self.prefix = f'test-gemini-{uuid.uuid4().hex}'
        self.butce = gemini._RedisButce(self.redis, prefix=self.prefix)
        self.addCleanup(self._temizle)

    def _temizle(self):
        for anahtar in self.redis.scan_iter(f'{self.prefix}:*'):
            self.redis.delete(anahtar)

    def test_artir_azalt_oku_ve_ttl(self):
        self.assertEqual(self.butce.oku('budget:2026-09-15'), 0)
        self.assertEqual(self.butce.artir('budget:2026-09-15'), 1)
        self.assertEqual(self.butce.artir('budget:2026-09-15'), 2)
        self.butce.azalt('budget:2026-09-15')
        self.assertEqual(self.butce.oku('budget:2026-09-15'), 1)
        ttl = self.redis.ttl(f'{self.prefix}:budget:2026-09-15')
        self.assertTrue(0 < ttl <= 48 * 3600)

    def test_django_ortaminda_redis_butce_ve_kapi(self):
        with mock.patch.object(gemini, '_butce', None), mock.patch.object(gemini, '_gate', None):
            self.assertIsInstance(gemini._get_butce(), gemini._RedisButce)
            self.assertIsInstance(gemini._get_gate(), tu._RedisGate)
```

- [ ] **Step 3: Testlerin basarisiz oldugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_gemini 2>&1 | tail -5`
Expected: `ImportError`/`ModuleNotFoundError: No module named 'news.gemini'` (tum testler hata).

- [ ] **Step 4: `news/gemini.py`'yi yaz**

```python
"""Gemini API ile kayit duzeyinde ceviri (spec 2026-09-15-gemini-yukseltme, bolum 3.2).

Yalnizca retranslate kullanir. Kayit basina TEK istek: cevrilecek alanlar JSON
olarak gider, ayni anahtarlarla Turkce doner. Kota korumasi:
  - Redis paylasimli aralik kapisi: istekler arasi en az GEMINI_MIN_INTERVAL sn
  - Gunluk istek butcesi (GEMINI_DAILY_BUDGET): istek ONCESI artar, 4xx'te geri alinir
  - 429 / 5xx / ag hatasi -> GEMINI_COOLDOWN sn devre kesici
Hicbir istisna disari cikmaz; cevrilemeyen kayit icin None doner.
XTRM yer tutucu korumasi ve turkish_post_process uygulanmaz: terimler prompt'la korunur.
"""
import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, Optional

import requests
from django.conf import settings

from . import translation_utils as tu

GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-3.5-flash-lite')
GEMINI_TIMEOUT = float(os.environ.get('GEMINI_TIMEOUT', '60'))
GEMINI_MIN_INTERVAL = float(os.environ.get('GEMINI_MIN_INTERVAL', '5'))   # 15 RPM'in altinda kal
GEMINI_DAILY_BUDGET = int(os.environ.get('GEMINI_DAILY_BUDGET', '400'))   # 500 RPD'nin altinda kal
GEMINI_COOLDOWN = int(os.environ.get('GEMINI_COOLDOWN', '600'))
GEMINI_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
MAX_RATIO = 3.0
ECHO_MIN_WORDS = 4

SISTEM_TALIMATI = (
    "Sen teknik haber ve guvenlik bultenleri ceviren bir cevirmensin. Verilen JSON nesnesindeki "
    "her alanin Ingilizce metnini dogal ve anlasilir Turkceye cevir; ayni anahtarlarla bir JSON nesnesi dondur.\n"
    "Kurallar:\n"
    "- Teknik terimleri, urun/kutuphane/sirket/kisi adlarini, kod parcalarini, dosya yollarini, fonksiyon "
    "adlarini, CVE numaralarini, surum ve commit numaralarini AYNEN birak; Turkce ek getirmek disinda degistirme.\n"
    "- Satir sonlarini, madde isaretlerini, numaralandirmayi ve '===SECTION:' gibi yapisal isaretleri "
    "oldugu gibi koru.\n"
    "- Ozetleme, ekleme, yorum yapma; metnin tamamini cevir.\n"
    "- Guvenlik terimlerini teknik anlamiyla cevir (orn. 'unauthenticated attacker' -> "
    "'kimligi dogrulanmamis saldirgan', 'remote code execution' -> 'uzaktan kod calistirma').\n"
    "- Yalnizca JSON dondur."
)

_gate = None
_butce = None


def _anahtar() -> str:
    return (getattr(settings, 'GEMINI_API_KEY', '') or '').strip()


def _redis_client():
    try:
        from django_redis import get_redis_connection
        client = get_redis_connection('default')
        client.ping()
        return client
    except Exception:
        return None


def _get_gate():
    """Aralik kapisi + devre kesici; Redis varsa tum worker'larda paylasilir."""
    global _gate
    if _gate is None:
        client = _redis_client()
        _gate = tu._RedisGate(client, prefix='gemini') if client else tu._LocalGate()
    return _gate


class _LocalButce:
    """Tek surec icin gunluk sayac (Redis yoksa ve testlerde)."""

    def __init__(self):
        self.sayaclar = {}

    def artir(self, anahtar: str) -> int:
        self.sayaclar[anahtar] = self.sayaclar.get(anahtar, 0) + 1
        return self.sayaclar[anahtar]

    def azalt(self, anahtar: str) -> None:
        self.sayaclar[anahtar] = max(self.sayaclar.get(anahtar, 0) - 1, 0)

    def oku(self, anahtar: str) -> int:
        return self.sayaclar.get(anahtar, 0)


class _RedisButce:
    """Tum worker sureclerinin paylastigi gunluk sayac; anahtar 48 saat sonra kendiliginden silinir."""

    def __init__(self, client, prefix: str = 'gemini'):
        self.client = client
        self.prefix = prefix

    def _tam(self, anahtar: str) -> str:
        return f'{self.prefix}:{anahtar}'

    def artir(self, anahtar: str) -> int:
        tam = self._tam(anahtar)
        deger = int(self.client.incr(tam))
        if deger == 1:
            self.client.expire(tam, 48 * 3600)
        return deger

    def azalt(self, anahtar: str) -> None:
        self.client.decr(self._tam(anahtar))

    def oku(self, anahtar: str) -> int:
        return int(self.client.get(self._tam(anahtar)) or 0)


def _get_butce():
    global _butce
    if _butce is None:
        client = _redis_client()
        _butce = _RedisButce(client) if client else _LocalButce()
    return _butce


def butce_anahtari() -> str:
    """UTC gune gore: Google kotasi da UTC'de sifirlanir."""
    return f'budget:{datetime.now(timezone.utc):%Y-%m-%d}'


def butce_kullanimi() -> int:
    return _get_butce().oku(butce_anahtari())


def butce_var() -> bool:
    return butce_kullanimi() < GEMINI_DAILY_BUDGET


def hazir() -> bool:
    return bool(_anahtar()) and not _get_gate().cooldown_active() and butce_var()


def _devre_kesici(sebep: str) -> None:
    print(f"  [Gemini] erisilemiyor ({sebep}); {GEMINI_COOLDOWN} sn atlanacak.")
    _get_gate().start_cooldown(GEMINI_COOLDOWN)


def _kelime_sayisi(metin: str) -> int:
    return len(re.findall(r'[^\W\d_]{2,}', metin))


def _alan_sorunu(orijinal: str, ceviri) -> Optional[str]:
    """Alan cevirisinin guvenilir olup olmadigi; sorun varsa kisa aciklama."""
    if not isinstance(ceviri, str) or not ceviri.strip():
        return 'bos'
    oran = len(ceviri) / max(len(orijinal), 1)
    if oran < tu.MIN_RATIO or oran > MAX_RATIO:
        return f'oran {oran:.2f}'
    if (_kelime_sayisi(orijinal) >= ECHO_MIN_WORDS
            and tu._normalize_for_echo(ceviri) == tu._normalize_for_echo(orijinal)):
        return 'yanki'
    return None


def _istek_govdesi(alanlar: Dict[str, str]) -> dict:
    return {
        'systemInstruction': {'parts': [{'text': SISTEM_TALIMATI}]},
        'contents': [{'role': 'user', 'parts': [{'text': json.dumps(alanlar, ensure_ascii=False)}]}],
        'generationConfig': {
            'temperature': 0.2,
            'responseMimeType': 'application/json',
            'responseSchema': {
                'type': 'OBJECT',
                'properties': {ad: {'type': 'STRING'} for ad in alanlar},
                'required': list(alanlar),
            },
        },
    }


def _yaniti_coz(yanit) -> Optional[dict]:
    try:
        aday = yanit.json()['candidates'][0]
        if aday.get('finishReason') not in (None, 'STOP'):
            print(f"  [Gemini] yanit tamamlanmadi ({aday.get('finishReason')}).")
            return None
        cikti = json.loads(aday['content']['parts'][0]['text'])
    except (ValueError, KeyError, IndexError, TypeError) as hata:
        print(f"  [Gemini] yanit cozulemedi ({type(hata).__name__}).")
        return None
    if not isinstance(cikti, dict):
        print("  [Gemini] yanit JSON nesnesi degil.")
        return None
    return cikti


def kaydi_cevir(alanlar: Dict[str, str]) -> Optional[Dict[str, str]]:
    """Kaydin cevrilecek alanlarini tek istekle cevirir. None: cevrilemedi (sebep loglandi)."""
    alanlar = {ad: metin for ad, metin in alanlar.items() if isinstance(metin, str) and metin.strip()}
    if not alanlar or not hazir():
        return None

    butce, anahtar = _get_butce(), butce_anahtari()
    if butce.artir(anahtar) > GEMINI_DAILY_BUDGET:
        butce.azalt(anahtar)
        print(f"  [Gemini] gunluk butce doldu ({GEMINI_DAILY_BUDGET}).")
        return None

    _get_gate().wait_for_slot(GEMINI_MIN_INTERVAL)
    try:
        yanit = requests.post(
            GEMINI_URL.format(model=GEMINI_MODEL),
            headers={'x-goog-api-key': _anahtar(), 'Content-Type': 'application/json'},
            json=_istek_govdesi(alanlar),
            timeout=GEMINI_TIMEOUT,
        )
    except requests.RequestException as hata:
        _devre_kesici(type(hata).__name__)
        return None
    except Exception as hata:  # beklenmeyen hata retranslate'i durdurmasin
        print(f"  [Gemini] beklenmeyen hata: {type(hata).__name__}")
        return None

    if yanit.status_code == 429 or yanit.status_code >= 500:
        _devre_kesici(f'HTTP {yanit.status_code}')
        return None
    if yanit.status_code != 200:
        # Istek sorunu (anahtar, gecersiz govde): kota harcanmadi, devre kesici acilmaz
        butce.azalt(anahtar)
        print(f"  [Gemini] istek reddedildi (HTTP {yanit.status_code}): {yanit.text[:200]}")
        return None

    cikti = _yaniti_coz(yanit)
    if cikti is None:
        return None
    sonuc = {}
    for ad, orijinal in alanlar.items():
        sorun = _alan_sorunu(orijinal, cikti.get(ad))
        if sorun:
            print(f"  [Gemini] dogrulama basarisiz ({ad}: {sorun}).")
            return None
        sonuc[ad] = cikti[ad].strip()
    return sonuc
```

- [ ] **Step 5: Testleri calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_gemini 2>&1 | tail -3`
Expected: `Ran 26 tests ... OK`

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran|^OK|FAILED"`
Expected: `Ran 234 tests ... OK` (208 + 26)

- [ ] **Step 6: Commit**

```bash
git add news/gemini.py news/tests/test_gemini.py cybernews/settings.py news/test_runner.py
git commit -m "feat: Gemini istemcisi — kayit duzeyinde ceviri, gunluk butce, aralik kapisi, devre kesici

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 2: `translation_provider` secenegine `gemini`, migration 0010

**Files:**
- Modify: `news/models.py` (alti modelde `choices` listesi)
- Create: `news/migrations/0010_translation_provider_gemini.py` (`makemigrations` uretir)
- Test: `news/tests/test_migrations_0010.py`

**Interfaces:**
- Produces: `translation_provider` deger kumesi `'' | 'google' | 'libretranslate' | 'gemini'`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_migrations_0010.py`:

```python
"""Migration 0010: translation_provider secenegine 'gemini' eklenir; sema ve veri degismez."""
from django.core.management import call_command
from django.test import TestCase
from io import StringIO

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)


class GeminiSecenegiTests(TestCase):

    def test_alti_modelde_gemini_secenegi_var(self):
        for model in (AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry):
            secenekler = [kod for kod, _ in model._meta.get_field('translation_provider').choices]
            self.assertEqual(secenekler, ['google', 'libretranslate', 'gemini'], model.__name__)

    def test_migration_eksigi_yok(self):
        cikti = StringIO()
        call_command('makemigrations', 'news', '--check', '--dry-run', stdout=cikti)
        self.assertIn('No changes detected', cikti.getvalue())
```

- [ ] **Step 2: Basarisiz oldugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_migrations_0010 2>&1 | tail -4`
Expected: `test_alti_modelde_gemini_secenegi_var` FAIL (`['google', 'libretranslate'] != [...]`); `test_migration_eksigi_yok` gecer (henuz degisiklik yok).

- [ ] **Step 3: Modelleri degistir ve migration uret**

`news/models.py` — alti modelde de su satiri degistir (6 yer; `grep -n "choices=\[('google'" news/models.py` ile bul):

```python
        choices=[('google', 'Google'), ('libretranslate', 'LibreTranslate'), ('gemini', 'Gemini')],
```

Run: `docker compose exec -T teknoloji-api python manage.py makemigrations news -n translation_provider_gemini`
Expected: `news/migrations/0010_translation_provider_gemini.py` olusur, icinde 6 `AlterField`.

Dosya root sahipliginde olusabilir; `git status` ile gorundugunu dogrula.

- [ ] **Step 4: Testleri calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran|^OK|FAILED"`
Expected: `Ran 236 tests ... OK`

- [ ] **Step 5: Commit**

```bash
git add news/models.py news/migrations/0010_translation_provider_gemini.py news/tests/test_migrations_0010.py
git commit -m "feat: translation_provider secenegine gemini (migration 0010, sema degismez)

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 3: `retranslate_pending` — Gemini once, yukseltme yalniz Gemini

**Files:**
- Modify: `news/retranslate.py`
- Modify: `news/tests/test_retranslate.py` (Google yukseltme testleri kalkar, Gemini testleri eklenir)

**Interfaces:**
- Consumes: `gemini.hazir()`, `gemini.butce_var()`, `gemini.kaydi_cevir(alanlar)` (Task 1)
- Produces: `retranslate_pending(...)` donusu:
  `{'translated': int, 'failed': int, 'upgraded': int, 'stopped': bool, 'stopped_reason': None | 'no_provider' | 'gemini_budget', 'by_provider': {'gemini': int, 'libretranslate': int, ...}, 'sections': {bolum: {'translated', 'failed', 'upgraded'}}}`
  ve `RETRANSLATE_UPGRADE_BATCH` varsayilani 40. `_gemini_alanlari(ad, kayit) -> Dict[str, str]`, `_gemini_ile_cevir(ad, kayit) -> Optional[Dict[str, str]]`.

- [ ] **Step 1: Google yukseltme testlerini kaldir, Gemini testlerini yaz**

`news/tests/test_retranslate.py` icinde:

0. `by_provider` artik her zaman `gemini` anahtarini tasir; iki mevcut beklentiyi guncelle:
   - `test_bekleyen_kayit_feede_bakmadan_cevrilir` (satir ~88): `{'google': 1, 'libretranslate': 0}` → `{'gemini': 0, 'libretranslate': 0, 'google': 1}` (Google Task 4'te kalkana kadar zincir hala Google; provider `'google'` beklentisi bu task'ta kalir).
   - `test_google_kapaliyken_libretranslate_ile_devam_eder` (satir ~249): `{'google': 0, 'libretranslate': 1}` → `{'gemini': 0, 'libretranslate': 1}`.
1. `RetranslateSaglayiciTests` sinifindan su testleri **sil**: `test_google_acikken_libretranslate_cevirisi_yukseltilir`, `test_google_kapaliyken_yukseltme_yapilmaz`, `test_kismi_yukseltme_kayda_yazilmaz`, `test_yukseltme_bolum_siniri`. `test_varsayilan_sinirlar` icindeki `RETRANSLATE_UPGRADE_BATCH` beklentisini `40` yap. Sinif docstring'ini `"""Spec 2026-09-15: bekleyenler Gemini-once, sonra zincir; yukseltme yalniz Gemini."""` yap.
2. `_libre_kaydi` yardimcisini sinif disina, modul duzeyine tasi (yeni sinif da kullanacak):

```python
def _libre_kaydi(slug, baslik='Farmers adopt new sensors', govde='Sensors measure soil moisture every hour.'):
    return AINewsEntry.objects.create(
        source='MIT Tech Review AI', original_title=baslik, turkish_title='LIBRE ' + baslik,
        original_description=govde, turkish_description='LIBRE ' + govde,
        link=f'https://ornek.test/rt/{slug}', published_date=date(2026, 9, 12),
        needs_translation=False, translation_provider='libretranslate')
```

(`RetranslateSaglayiciTests` icindeki `self._libre_kaydi(...)` cagrilarini `_libre_kaydi(...)` yap.)

3. Import'lara ekle: `from news import gemini` ve `from news.models import NewsArticle`.
4. Dosyanin sonuna ekle:

```python
class GeminiSahteMixin:
    """gemini modulunu ag erisimi olmadan taklit eder."""

    def gemini_ayarla(self, cevap=None, hazir=True, butce=True):
        """cevap: alanlar sozlugunu alan fonksiyon, sabit sozluk ya da None (cevrilemedi)."""
        self.gemini_cagrilar = []

        def kaydi_cevir(alanlar):
            self.gemini_cagrilar.append(dict(alanlar))
            return cevap(alanlar) if callable(cevap) else cevap

        for hedef, deger in (('hazir', lambda: hazir and butce), ('butce_var', lambda: butce),
                             ('kaydi_cevir', kaydi_cevir)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)


def _gemini_cevirisi(alanlar):
    return {ad: 'GEMINI ' + metin for ad, metin in alanlar.items()}


class RetranslateGeminiTests(GeminiSahteMixin, SaglayiciZinciriMixin, RetranslateTestBase):

    def setUp(self):
        super().setUp()
        self.libre = self.saglayicilari_ayarla(SahteSaglayici('libretranslate', _libre))[0]

    # --- Asama 1: bekleyenler ---

    def test_bekleyen_once_gemini_ile_cevrilir(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g1')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.turkish_title, 'GEMINI Farmers adopt new sensors')
        self.assertEqual(kayit.turkish_description, 'GEMINI Sensors measure soil moisture every hour.')
        self.assertEqual(kayit.translation_provider, 'gemini')
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(sonuc['by_provider']['gemini'], 1)
        self.assertEqual(self.libre.cagrilar, [])
        self.assertEqual(self.gemini_cagrilar, [{'title': 'Farmers adopt new sensors',
                                                'description': 'Sensors measure soil moisture every hour.'}])

    def test_gemini_cevrilemezse_zincire_duser(self):
        self.gemini_ayarla(None)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g2')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertTrue(kayit.turkish_title.startswith('LIBRE'))
        self.assertEqual(sonuc['by_provider'], {'gemini': 0, 'libretranslate': 1})

    def test_gemini_hazir_degilse_asama_durmaz(self):
        self.gemini_ayarla(_gemini_cevirisi, hazir=False)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g3')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertFalse(sonuc['stopped'])
        self.assertIsNone(sonuc['stopped_reason'])

    def test_zincir_kapali_gemini_acik_bekleyen_cevrilir(self):
        self.libre.hazir = False
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g4')

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'gemini')
        self.assertFalse(sonuc['stopped'])

    def test_hicbiri_yoksa_durur_ve_sebep_yazilir(self):
        self.libre.hazir = False
        self.gemini_ayarla(None, hazir=False)
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'g5')

        sonuc = self._calistir()

        self.assertTrue(sonuc['stopped'])
        self.assertEqual(sonuc['stopped_reason'], 'no_provider')

    def test_cve_kisa_aciklama_gemini_adayi_degil(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = CVEEntry.objects.create(
            cve_id='CVE-2026-0001', source='NVD', original_title='CVE-2026-0001 - Guvenlik Acigi',
            turkish_title='CVE-2026-0001 - Guvenlik Acigi', original_description='Short text.',
            turkish_description='Short text.', link='https://ornek.test/cve/1',
            published_date=date(2026, 9, 12), severity='Orta', needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertEqual(kayit.turkish_description, 'Short text.')
        self.assertFalse(kayit.needs_translation)

    def test_cve_uzun_aciklama_yalniz_description_ile_gider(self):
        self.gemini_ayarla(_gemini_cevirisi)
        govde = 'A remote attacker can read arbitrary files from the server.'
        kayit = CVEEntry.objects.create(
            cve_id='CVE-2026-0002', source='NVD', original_title='CVE-2026-0002 - Guvenlik Acigi',
            turkish_title='CVE-2026-0002 - Guvenlik Acigi', original_description=govde,
            turkish_description=govde, link='https://ornek.test/cve/2',
            published_date=date(2026, 9, 12), severity='Yuksek', needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [{'description': govde}])
        self.assertEqual(kayit.turkish_title, 'CVE-2026-0002 - Guvenlik Acigi')
        self.assertEqual(kayit.turkish_description, 'GEMINI ' + govde)
        self.assertEqual(kayit.translation_provider, 'gemini')

    def test_kubernetes_yapisal_changelog_tek_alan_olarak_gider(self):
        self.gemini_ayarla(_gemini_cevirisi)
        govde = '===SECTION:Features===\n- Add new scheduler flag.\n===SECTION:Bug Fixes===\n- Fix kubelet crash.'
        kayit = KubernetesEntry.objects.create(
            source='GitHub Releases', category='release', version='v1.31.0',
            original_title='Kubernetes v1.31.0 released', turkish_title='Kubernetes v1.31.0 released',
            original_description=govde, turkish_description=govde, link='https://ornek.test/k8s/1',
            published_date=date(2026, 9, 12), needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [{'title': 'Kubernetes v1.31.0 released', 'description': govde}])
        self.assertEqual(kayit.turkish_description, 'GEMINI ' + govde)

    def test_haber_bos_orijinal_aciklama_gonderilmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = NewsArticle.objects.create(
            source='The Hacker News', original_title='Story number 1 published',
            turkish_title='Story number 1 published', original_description='',
            turkish_description='Mevcut Türkçe gövde.', link='https://ornek.test/haber/g1',
            date=date(2026, 9, 14), original_date='2026-09-14', needs_translation=True)

        self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(self.gemini_cagrilar, [{'title': 'Story number 1 published'}])
        self.assertEqual(kayit.turkish_title, 'GEMINI Story number 1 published')
        self.assertEqual(kayit.turkish_description, 'Mevcut Türkçe gövde.')

    # --- Asama 2: yukseltme ---

    def test_libretranslate_kaydi_gemini_ile_yukseltilir(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _libre_kaydi('y1')
        eski = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'gemini')
        self.assertEqual(kayit.turkish_title, 'GEMINI Farmers adopt new sensors')
        self.assertEqual(kayit.turkish_description, 'GEMINI Sensors measure soil moisture every hour.')
        self.assertGreater(kayit.updated_at, eski)
        self.assertEqual(sonuc['upgraded'], 1)
        self.assertEqual(sonuc['sections']['ai']['upgraded'], 1)

    def test_gemini_cevrilemezse_yukseltme_yazilmaz(self):
        self.gemini_ayarla(None)
        kayit = _libre_kaydi('y2')
        eski = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertEqual(kayit.translation_provider, 'libretranslate')
        self.assertEqual(kayit.updated_at, eski)
        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(len(self.gemini_cagrilar), 1)

    def test_gemini_hazir_degilse_yukseltme_baslamaz(self):
        self.gemini_ayarla(_gemini_cevirisi, hazir=False)
        _libre_kaydi('y3')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(self.gemini_cagrilar, [])
        self.assertIsNone(sonuc['stopped_reason'])

    def test_butce_bitince_yukseltme_durur_ve_sebep_yazilir(self):
        self.gemini_ayarla(_gemini_cevirisi, butce=False)
        _libre_kaydi('y4')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        self.assertFalse(sonuc['stopped'])           # LibreTranslate zinciri hala calisir
        self.assertEqual(sonuc['stopped_reason'], 'gemini_budget')

    def test_butce_asama_ortasinda_bitince_imlec_ilerlemez(self):
        durum = {'kalan': 1}

        def cevap(alanlar):
            durum['kalan'] -= 1
            return _gemini_cevirisi(alanlar)

        self.gemini_ayarla(cevap)
        # hazir() ikinci kayittan once False'a dusmeli
        mock.patch.object(gemini, 'hazir', lambda: durum['kalan'] > 0).start()
        for i in range(3):
            _libre_kaydi(f'y5-{i}', baslik=f'Story number {i + 1} published')

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 1)
        self.assertEqual(AINewsEntry.objects.filter(translation_provider='libretranslate').count(), 2)
        # Imlec ilk kaydin arkasinda kaldi: bir sonraki tur ikinci kayittan devam eder
        self.assertTrue(self.redis.exists(f'{self.prefix}:upgrade-cursor:ai'))

    def test_yukseltme_bolum_siniri(self):
        self.gemini_ayarla(_gemini_cevirisi)
        for i in range(4):
            _libre_kaydi(f'y6-{i}', baslik=f'Story number {i + 1} published')

        sonuc = self._calistir(upgrade_batch=3)

        self.assertEqual(sonuc['upgraded'], 3)
        self.assertEqual(AINewsEntry.objects.filter(translation_provider='libretranslate').count(), 1)

    def test_google_kayitlari_yukseltilmez(self):
        self.gemini_ayarla(_gemini_cevirisi)
        kayit = _libre_kaydi('y7')
        kayit.translation_provider = 'google'
        kayit.save(update_fields=['translation_provider'])

        sonuc = self._calistir()

        self.assertEqual(sonuc['upgraded'], 0)
        self.assertEqual(self.gemini_cagrilar, [])
```

`test_butce_asama_ortasinda_bitince_imlec_ilerlemez` icindeki `mock.patch.object(...).start()` icin cleanup ekle: `yama = mock.patch.object(gemini, 'hazir', lambda: durum['kalan'] > 0); yama.start(); self.addCleanup(yama.stop)`.

5. `RetranslateTestBase.setUp` sonuna ekle (mevcut testler Gemini'siz kalsin):

```python
        self.gemini_ayarla_varsayilan()
```

ve `RetranslateTestBase` sinifina:

```python
    def gemini_ayarla_varsayilan(self):
        """Gemini kapali: mevcut zincir testleri etkilenmez. Gemini testleri kendi ayarini yapar."""
        for hedef, deger in (('hazir', lambda: False), ('butce_var', lambda: True), ('kaydi_cevir', lambda alanlar: None)):
            yama = mock.patch.object(gemini, hedef, deger)
            yama.start()
            self.addCleanup(yama.stop)
```

(`GeminiSahteMixin.gemini_ayarla` daha sonra patch'ledigi icin onu ezer; `mock.patch` yigini sirayla geri alinir.)

- [ ] **Step 2: Basarisiz oldugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate 2>&1 | grep -E "^Ran|FAILED|ERROR:|FAIL:" | head -20`
Expected: `RetranslateGeminiTests` testleri FAIL/ERROR (`stopped_reason` KeyError, provider `libretranslate` != `gemini`, `by_provider` KeyError 'gemini'); eski testler gecer.

- [ ] **Step 3: `news/retranslate.py`'yi degistir**

Modul docstring'ini degistir:

```python
"""Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir ve LibreTranslate
cevirilerini Gemini ile yukseltir (spec 2026-09-15-gemini-yukseltme, bolum 3.3).

Asama 1 — Bekleyenler (needs_translation=True): once Gemini kayit duzeyinde
(baslik + aciklama tek istek); cevrilemezse saglayici zinciri (LibreTranslate).
A3 plani netlestirme 8'deki imlec kurallari aynen gecerlidir: her bolum icin
Redis'te bir imlec ({prefix}:cursor:{bolum}); icerik yuzunden cevrilemeyen
kayit sirada kalir ama imlec onu gecer; sona gelinince imlec silinir. Gorev
yalnizca HICBIR saglayici (Gemini dahil) hazir degilse durur; imlec o kaydi gecmez.

Asama 2 — Yukseltme (needs_translation=False, translation_provider='libretranslate'),
yalnizca Gemini ile. Gemini tum alanlari dogrulamadan gecirdiyse yazilir (hepsi ya
da hicbiri, gemini.kaydi_cevir icinde); aksi halde LibreTranslate cevirisi yerinde
kalir ve imlec ilerler. Gemini hazir degilse (anahtar yok / devre kesici / gunluk
butce) asama baslamaz; butce asama ortasinda biterse imlec ilerletilmeden durur.
Kendi imleci vardir ({prefix}:upgrade-cursor:{bolum}). Google kayitlari yukseltilmez.

Yazma kurallari:
  - Basarisiz denemede kayda yazilmaz: updated_at ilerlemez.
  - Basarida Turkce alanlar, needs_translation=False, translation_provider ve
    updated_at yazilir; ceviri delta akisindan tuketiciye gider.
"""
```

Import'lara ekle: `from typing import Dict, Optional` (Dict zaten var) ve `from . import gemini`.

`RETRANSLATE_UPGRADE_BATCH` satirini degistir:

```python
# Yukseltme Gemini gunluk butcesini kullanir; asil sinir butcedir (gemini.GEMINI_DAILY_BUDGET).
RETRANSLATE_UPGRADE_BATCH = int(os.environ.get('RETRANSLATE_UPGRADE_BATCH', '40'))
```

`BOLUMLER` tanimindan once ekle:

```python
_GEMINI_DB_ALANI = {'title': 'turkish_title', 'description': 'turkish_description'}


def _gemini_alanlari(ad: str, kayit) -> Dict[str, str]:
    """Gemini'ye gidecek alanlar (spec 3.3). Bos sozluk: kayit Gemini adayi degil."""
    aciklama = (kayit.original_description or '').strip()
    if ad == 'cve':
        # cve_scraper kurali: baslik cevrilmez, 30 karakterden kisa aciklama oldugu gibi kalir
        return {'description': aciklama} if len(aciklama) > 30 else {}
    alanlar = {'title': (kayit.original_title or '').strip()}
    if aciklama:  # 2026-09-15 haber kurali: orijinal bossa Turkce govdeye dokunma
        alanlar['description'] = aciklama
    return {alan: metin for alan, metin in alanlar.items() if metin}


def _gemini_ile_cevir(ad: str, kayit) -> Optional[Dict[str, str]]:
    """Kaydi Gemini ile cevirir; DB alan adlariyla sozluk ya da None (aday degil / hazir degil / cevrilemedi)."""
    alanlar = _gemini_alanlari(ad, kayit)
    if not alanlar or not gemini.hazir():
        return None
    sonuc = gemini.kaydi_cevir(alanlar)
    if sonuc is None:
        return None
    return {_GEMINI_DB_ALANI[alan]: metin for alan, metin in sonuc.items()}
```

`_bekleyenler` fonksiyonunu su hale getir:

```python
def _bekleyenler(ad, model, cevir, redis_client, prefix, sinir, sonuc):
    """Asama 1. Donus: (cevrilen, basarisiz, durdu)."""
    anahtar = f'{prefix}:cursor:{ad}'
    sorgu = model.objects.filter(needs_translation=True).order_by('updated_at', 'id')
    kayitlar = _imlecten_sonraki(redis_client, anahtar, sorgu, sinir)

    cevrilen = basarisiz = 0
    durdu = False
    for kayit in kayitlar:
        if not (tu.herhangi_saglayici_hazir() or gemini.hazir()):
            durdu = True
            break
        deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)

        gemini_alanlar = _gemini_ile_cevir(ad, kayit)
        if gemini_alanlar is not None:
            _yaz(kayit, gemini_alanlar, 'gemini')
            cevrilen += 1
            sonuc['by_provider']['gemini'] += 1
            redis_client.set(anahtar, deneme_oncesi)
            continue

        if not tu.herhangi_saglayici_hazir():
            durdu = True  # Gemini cevirmedi, zincir kapali: imleci ilerletme
            break
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
                sonuc['by_provider'][saglayici] = sonuc['by_provider'].get(saglayici, 0) + 1
        redis_client.set(anahtar, deneme_oncesi)

    if not durdu and len(kayitlar) < sinir:
        redis_client.delete(anahtar)  # sona gelindi; bir sonraki tur bastan
    return cevrilen, basarisiz, durdu
```

`_yukselt` fonksiyonunu tamamen degistir:

```python
def _yukselt(ad, model, redis_client, prefix, sinir, sonuc):
    """Asama 2. Yalnizca Gemini. Donus: yukseltilen kayit sayisi."""
    if not gemini.hazir():
        if not gemini.butce_var():
            sonuc['stopped_reason'] = 'gemini_budget'
        return 0
    anahtar = f'{prefix}:upgrade-cursor:{ad}'
    sorgu = (model.objects.filter(needs_translation=False, translation_provider='libretranslate')
             .order_by('updated_at', 'id'))
    kayitlar = _imlecten_sonraki(redis_client, anahtar, sorgu, sinir)

    yukseltilen = 0
    durdu = False
    for kayit in kayitlar:
        if not gemini.hazir():
            durdu = True  # butce/devre kesici asama ortasinda; imleci ilerletme
            if not gemini.butce_var():
                sonuc['stopped_reason'] = 'gemini_budget'
            break
        deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)
        alanlar = _gemini_ile_cevir(ad, kayit)
        if alanlar is not None:
            _yaz(kayit, alanlar, 'gemini')
            yukseltilen += 1
        redis_client.set(anahtar, deneme_oncesi)

    if not durdu and len(kayitlar) < sinir:
        redis_client.delete(anahtar)
    return yukseltilen
```

`retranslate_pending` fonksiyonunu su hale getir:

```python
def retranslate_pending(redis_client=None, prefix: str = 'retranslate',
                        batch: int = None, upgrade_batch: int = None) -> Dict:
    redis_client = redis_client or _canli_redis()
    batch = RETRANSLATE_BATCH if batch is None else batch
    upgrade_batch = RETRANSLATE_UPGRADE_BATCH if upgrade_batch is None else upgrade_batch
    sonuc = {'translated': 0, 'failed': 0, 'upgraded': 0, 'stopped': False, 'stopped_reason': None,
             'by_provider': {'gemini': 0, 'libretranslate': 0}, 'sections': {}}

    for ad, model, cevir in BOLUMLER:
        if not (tu.herhangi_saglayici_hazir() or gemini.hazir()):
            sonuc['stopped'] = True
            sonuc['stopped_reason'] = 'no_provider'
            break

        cevrilen, basarisiz, durdu = _bekleyenler(ad, model, cevir, redis_client, prefix, batch, sonuc)
        yukseltilen = 0 if durdu else _yukselt(ad, model, redis_client, prefix, upgrade_batch, sonuc)

        if cevrilen or yukseltilen:
            cache_yenile(ad)
        sonuc['sections'][ad] = {'translated': cevrilen, 'failed': basarisiz, 'upgraded': yukseltilen}
        sonuc['translated'] += cevrilen
        sonuc['failed'] += basarisiz
        sonuc['upgraded'] += yukseltilen

        if durdu:
            sonuc['stopped'] = True
            sonuc['stopped_reason'] = 'no_provider'
            break

    return sonuc
```

`tu.yalnizca_saglayicilar` artik bu dosyada kullanilmaz (Task 4 siler).

- [ ] **Step 4: Testleri calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate 2>&1 | grep -E "^Ran|^OK|FAILED|FAIL:|ERROR:"`
Expected: `OK`. Eski `RetranslateSaglayiciTests` testlerinden `test_hicbir_saglayici_yoksa_durur` `stopped` beklentisiyle hala gecmeli (Gemini varsayilan kapali).

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran|^OK|FAILED"`
Expected: `OK` (236 − 4 silinen + 17 yeni = 249 civari).

- [ ] **Step 5: Commit**

```bash
git add news/retranslate.py news/tests/test_retranslate.py
git commit -m "feat: retranslate bekleyenleri once Gemini ile cevirsin, yukseltme yalniz Gemini

- bekleyenler: kayit duzeyinde Gemini, cevrilemezse LibreTranslate zinciri
- yukseltme: libretranslate -> gemini, butce bitince stopped_reason=gemini_budget
- RETRANSLATE_UPGRADE_BATCH 5 -> 40; by_provider {gemini, libretranslate}

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 4: Google'i kaldir (kod, bagimlilik, testler)

**Files:**
- Modify: `news/translation_utils.py`, `news/translation_providers.py`, `news/test_runner.py`, `requirements.txt`, `news/retranslate.py` (yalniz docstring temizligi gerekiyorsa), `news/tests/test_translation.py`, `news/tests/test_translation_chain.py`, `news/tests/test_translation_providers.py`
- Delete: `news/tests/test_google_gtx.py`
- Test: mevcut paket

**Interfaces:**
- Produces: `tp.SAGLAYICILAR == (LibreTranslateProvider(),)`; `tu` icinde artik `GtxTranslator`, `_make_translator`, `_translate_via_google`, `ERROR_KEYWORDS`, `RETRY_DELAYS`, `MIN_INTERVAL`, `COOLDOWN_SECONDS`, `_gate`, `_get_gate`, `yalnizca_saglayicilar`, `_saglayici_kisiti` yok. `tu._RedisGate`, `tu._LocalGate`, `tu.MIN_RATIO`, `tu.verify_translation`, `tu.kayit_saglayicisi`, `tu.saglayicilar`, `tu.herhangi_saglayici_hazir` kalir.
- `TranslationGateMixin.use_translator(translator)` ayni imzayla kalir ama zincire `SahteSaglayici('libretranslate', ...)` takar.

- [ ] **Step 1: Test tarafini once degistir (RED)**

`news/tests/test_google_gtx.py` dosyasini sil: `git rm news/tests/test_google_gtx.py`

`news/tests/test_translation.py`:

1. Dosya docstring'ini degistir:

```python
"""
Ceviri dayanikliligi testleri.

Cekim aninda tek saglayici LibreTranslate'tir (Google 2026-09-15'te kaldirildi). Bu testler
su davranislari korur:
  - Saglayici erisilemez/hata verirse metin orijinal kalir ve basarisizlik sayilir
  - Basarisiz ceviriler sayilir; task kaydi `needs_translation` olarak isaretler
  - Isaretli kayitlar sonraki cekimde tekrar islenir (skip_existing onlari atlamaz)
  - Aralik kapisi ve devre kesici Redis uzerinden tum worker process'lerince paylasilir

Dis servisler icin sahte cevirmen kullanilir; Redis ve DB gercektir.
"""
```

2. Import'lara ekle: `from news import translation_providers as tp` ve `from news.tests.saglayici_yardimcilari import SahteSaglayici`.
3. `TranslationGateMixin`'i su hale getir:

```python
class TranslationGateMixin:
    """Her testte temiz, tek-process kapi; zincirde sahte LibreTranslate."""

    def setUp(self):
        super().setUp()
        yama = mock.patch.object(tp, '_lt_gate', tu._LocalGate())
        yama.start()
        self.addCleanup(yama.stop)
        tu.consume_translation_failures()
        tu.consume_translation_providers()

    def use_translator(self, translator):
        """FakeTranslator'i zincirdeki tek saglayici (libretranslate) olarak takar.

        FakeTranslator sozlesmesi korunur: bilinmeyen metne ERROR_PAGE (=> saglayici
        erisilemedi, None), Exception degerine istisna (zincir yakalar, orijinal kalir).
        """
        def cevap(protected):
            yanit = translator.translate(protected)
            return None if yanit == ERROR_PAGE else yanit

        yama = mock.patch.object(tp, 'SAGLAYICILAR', (SahteSaglayici('libretranslate', cevap),))
        yama.start()
        self.addCleanup(yama.stop)
        return translator
```

4. `TranslateTextResilienceTests` icinden **sil**: `test_blocked_google_returns_original_text_after_retries_and_records_failure`, `test_transient_error_recovers_on_retry`, `test_exhausted_retries_open_cooldown_and_skip_google_entirely`, `test_cooldown_expires_and_translation_resumes`. Yerine ekle:

```python
    def test_saglayici_erisilemezse_orijinal_doner_ve_basarisizlik_sayilir(self):
        self.use_translator(FakeTranslator())  # her metne hata sayfasi => erisilemedi
        self.assertEqual(tu.translate_text('Farmers adopt new sensors'), 'Farmers adopt new sensors')
        self.assertEqual(tu.consume_translation_failures(), 1)

    def test_saglayici_istisnasi_orijinal_birakir(self):
        self.use_translator(FakeTranslator({'Farmers adopt new sensors': RuntimeError('patladi')}))
        self.assertEqual(tu.translate_text('Farmers adopt new sensors'), 'Farmers adopt new sensors')
        self.assertEqual(tu.consume_translation_failures(), 1)
```

5. `RedisGateTests` icinden `test_django_environment_uses_shared_redis_gate` testini sil (`_get_gate` kalkiyor); `_RedisGate`'i dogrudan kuran diger iki test kalir.
6. `SequenceTranslator` sinifini kullanan test kalmadiysa sinifi sil (`grep -n SequenceTranslator news/tests/*.py`).

`news/tests/test_retranslate.py`: `test_bekleyen_kayit_feede_bakmadan_cevrilir` artik zincirden `libretranslate` gorur: `by_provider` beklentisini `{'gemini': 0, 'libretranslate': 1}`, `translation_provider` beklentisini `'libretranslate'` yap. `_google` yardimci fonksiyonu ve `SahteSaglayici('google', ...)` kullanan kalan testler zincirin ad-bagimsizligini dogrular; adlari `'birinci'`/`'ikinci'` gibi temsili adlara cevirmek zorunlu degil.

`news/tests/test_translation_chain.py`: `test_yalnizca_google_kisiti` testini sil. Sahte saglayici adi olarak `'google'` kullanan testler zincirin adlardan bagimsiz oldugunu dogruluyor; kalabilir ama sinif docstring'ine not ekle: `# Adlar temsili: zincir saglayici adindan bagimsizdir; canlida yalniz libretranslate var.`

`news/tests/test_translation_providers.py`: `SAGLAYICILAR` sirasini dogrulayan testte beklentiyi `['libretranslate']` yap; `GoogleProvider` / `_translate_via_google` mock'layan testleri sil (`grep -n "GoogleProvider\|_translate_via_google" news/tests/test_translation_providers.py`).

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation news.tests.test_translation_chain news.tests.test_translation_providers 2>&1 | grep -E "^Ran|FAILED|ERROR:|FAIL:" | head`
Expected: `SAGLAYICILAR` sira testi FAIL (`['google','libretranslate'] != ['libretranslate']`); digerleri gecer (mixin artik zincire takiyor, Google hic cagrilmiyor).

- [ ] **Step 2: Kodu temizle (GREEN)**

`news/translation_providers.py`:
- Docstring'deki "Google mantigi ... GoogleProvider ..." paragrafini kaldir; yerine: `Cekim aninda tek saglayici LibreTranslate'tir; Gemini yalniz retranslate'te kayit duzeyinde kullanilir (news/gemini.py).`
- `class GoogleProvider` blogunu sil.
- `SAGLAYICILAR = (LibreTranslateProvider(),)`

`news/translation_utils.py`:
- `from curl_cffi import requests  # ...` satirini sil.
- 255-266 arasi Google aciklama blogunu ve `MIN_INTERVAL`, `COOLDOWN_SECONDS`, `RETRY_DELAYS`, `ERROR_KEYWORDS` tanimlarini sil. Dogrulama esikleri blogunun ustune su yorumu koy:

```python
# ============================================================
# Dogrulama esikleri (spec 9.2, A3 plani netlestirme 3-7).
# Saglayici yanit verdi ama sonuc guvenilmezse metin orijinal kalir ve kayit
# needs_translation ile isaretlenir; yeniden deneme ve devre kesici UYGULANMAZ.
# ============================================================
```

- `_gate = None` ve `def _get_gate()` fonksiyonunu sil (`_LocalGate`, `_RedisGate` kalir; docstring'lerinde "Google" gecmiyor).
- `GTX_URL`, `GTX_TIMEOUT`, `class GtxTranslator`, `def _make_translator` bloklarini sil.
- `_saglayici_kisiti = None`, `def yalnizca_saglayicilar`, ve `saglayicilar()` icindeki kisit dalini sil:

```python
def saglayicilar() -> list:
    from . import translation_providers as tp
    return list(tp.SAGLAYICILAR)
```

- `def _translate_via_google` fonksiyonunu sil.
- `from contextlib import contextmanager` artik kullanilmiyorsa sil.
- `verify_translation` docstring'indeki "Google cevabinin" → "Saglayici cevabinin"; `translate_text` docstring'i zaten saglayici-bagimsiz.
- Saglayici zinciri yorumundaki `Google -> LibreTranslate -> orijinal metin` → `LibreTranslate -> orijinal metin (Gemini yalniz retranslate'te)`.
- `kayit_saglayicisi` degismez (eski `google` kayitlari icin ad hesabi kalir).

`news/test_runner.py`: `tu._gate = tu._LocalGate()` satirini sil; docstring'deki "Google canlida kisitliyken" ifadesini "LibreTranslate/Gemini devre kesicisi acikken" yap.

`requirements.txt`: `curl_cffi==0.16.3` satirini sil.

Google referansi kalmadigini dogrula: `grep -rn "google\|Google\|gtx\|curl_cffi" news/*.py cybernews/*.py requirements.txt | grep -v "kayit_saglayicisi\|'google'\|migrations" ` — kalan satirlar yalniz eski kayit etiketi (`'google'`) ve aciklayici yorumlar olmali; `import`/cagri kalmamali.

- [ ] **Step 3: Testleri calistir**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran|^OK|FAILED|FAIL:|ERROR:"`
Expected: `OK`. Python import'u da temiz: `docker compose exec -T teknoloji-api python -c "import news.translation_utils, news.translation_providers, news.retranslate; print('ok')"` → `ok`.

- [ ] **Step 4: Commit**

```bash
git add -A news/ requirements.txt
git commit -m "refactor: Google Translate yolunu kaldir — cekim aninda yalniz LibreTranslate

GtxTranslator, _translate_via_google, GoogleProvider, Google devre kesicisi,
yalnizca_saglayicilar ve curl_cffi bagimliligi silindi. Test mixin'i sahte
cevirmeni zincire libretranslate olarak takar; Google testleri kaldirildi.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 5: Frontend — `CeviriEtiketi`, dev proxy `/admin` + `/static`, `usePolling`

**Files:**
- Create: `frontend/src/components/CeviriEtiketi.jsx`
- Delete: `frontend/src/components/MakineCevirisiEtiketi.jsx`
- Modify: `AINewsComponent.jsx`, `CVEComponent.jsx`, `DevToolsComponent.jsx`, `KubernetesComponent.jsx`, `NewsComponent.jsx`, `SREComponent.jsx` (import + JSX adlari), `frontend/vite.config.js`

**Interfaces:**
- Produces: `CeviriEtiketi({ kayit, className })` (varsayilan export), `ceviriEtiketiHtml(kayit)`.

- [ ] **Step 1: Bileseni yaz**

`frontend/src/components/CeviriEtiketi.jsx`:

```jsx
import { Badge } from 'react-bootstrap'

// Her kayit hangi saglayiciyla cevrildigini gosterir (spec 2026-09-15, bolum 3.5).
// LibreTranslate dusuk kalitelidir ve anlam hatasi icerebilir: sari uyari.
// Gemini ve Google (eski kayitlar) notr gri bilgi rozeti. Bos/null: rozet yok.
const ROZETLER = {
  libretranslate: {
    metin: 'Makine çevirisi: LibreTranslate',
    bg: 'warning', text: 'dark', arka: '#ffc107', on: '#212529',
    aciklama: 'Yerel LibreTranslate ile çevrildi; anlam hatası olabilir, orijinal metne bakın. En geç 2 saat içinde Gemini ile iyileştirilir.',
  },
  gemini: {
    metin: 'Çeviri: Gemini',
    bg: 'secondary', text: 'light', arka: '#6c757d', on: '#ffffff',
    aciklama: 'Gemini (gemini-3.5-flash-lite) ile çevrildi.',
  },
  google: {
    metin: 'Çeviri: Google',
    bg: 'secondary', text: 'light', arka: '#6c757d', on: '#ffffff',
    aciklama: 'Google Translate ile çevrildi.',
  },
}

export default function CeviriEtiketi({ kayit, className = 'ms-2' }) {
  const rozet = ROZETLER[kayit?.translation_provider]
  if (!rozet) return null
  return (
    <Badge bg={rozet.bg} text={rozet.text} className={className} title={rozet.aciklama}>
      {rozet.metin}
    </Badge>
  )
}

export const ceviriEtiketiHtml = (kayit) => {
  const rozet = ROZETLER[kayit?.translation_provider]
  return rozet
    ? `<span class="badge" style="background:${rozet.arka};color:${rozet.on}" title="${rozet.aciklama}">${rozet.metin}</span>`
    : ''
}
```

- [ ] **Step 2: Kullanim noktalarini yeniden adlandir ve eski dosyayi sil**

Git Bash'te (proje kokunde):

```bash
sed -i "s/MakineCevirisiEtiketi/CeviriEtiketi/g; s/makineCevirisiHtml/ceviriEtiketiHtml/g" frontend/src/components/{AINews,CVE,DevTools,Kubernetes,News,SRE}Component.jsx
git rm -q frontend/src/components/MakineCevirisiEtiketi.jsx
grep -rn "MakineCevirisi\|makineCevirisi" frontend/src || echo "eski ad kalmadi"
grep -c "CeviriEtiketi" frontend/src/components/*Component.jsx
```

Expected: son satirda her bilesen icin 3 (import + 2 JSX), CVE icin 4 (`ceviriEtiketiHtml` dahil); "eski ad kalmadi".

- [ ] **Step 3: Vite: dev proxy ve usePolling**

`frontend/vite.config.js`:

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    // Windows Docker bind mount dosya olayi uretmez; HMR icin dosyalar taranir
    watch: { usePolling: true, interval: 1000 },
    proxy: {
      '/api': { target: 'http://teknoloji-api:8000', changeOrigin: true },
      // Django admin ve statikleri gelistirmede de ayni kapidan (prod nginx.conf ile ayni)
      '/admin': { target: 'http://teknoloji-api:8000', changeOrigin: true },
      '/static': { target: 'http://teknoloji-api:8000', changeOrigin: true },
    },
  },
})
```

- [ ] **Step 4: Derleme ve canli dogrulama (dev)**

```bash
docker compose exec -T teknoloji-frontend npm run build 2>&1 | tail -3
docker compose restart teknoloji-frontend
sleep 8
curl -s "http://localhost:3000/src/components/CeviriEtiketi.jsx" | grep -c "ROZETLER"
curl -s -o /dev/null -w "3000/admin/ -> %{http_code} %{redirect_url}\n" http://localhost:3000/admin/
curl -s -o /dev/null -w "3000/static/admin/css/base.css -> %{http_code}\n" http://localhost:3000/static/admin/css/base.css
```

Expected: build `✓ built`; `1`; `302 http://localhost:3000/admin/login/?next=/admin/` (Django admin'e gidiyor, React degil); `200`.

HMR dogrulamasi: `CeviriEtiketi.jsx`'te bir yoruma harf ekle, `docker compose logs --since 30s teknoloji-frontend | grep -i "hmr update"` satiri gorunsun, degisikligi geri al.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ frontend/vite.config.js
git commit -m "feat(frontend): saglayici bazli CeviriEtiketi (Gemini/LibreTranslate/Google); dev proxy /admin ve /static; HMR usePolling

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

---

### Task 6: Canli dagitim ve dogrulama

Kod yazmaz. **Canli sisteme dokunur** (ortam degiskeni, imaj, migration, gercek Gemini istekleri, konteyner yeniden olusturma). **Baslamadan once kullaniciya haber ver ve onay al.**

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Compose'a anahtari bagla**

`docker-compose.yml` — `teknoloji-api` (satir ~15) ve `teknoloji-worker` (satir ~90) `environment` listelerinde `LIBRETRANSLATE_URL=...` satirinin hemen altina:

```yaml
      - GEMINI_API_KEY=${GEMINI_API_KEY}
```

Scheduler'a **ekleme**. Dogrula: `docker compose config 2>/dev/null | grep -c "GEMINI_API_KEY"` → `2`; degerin dolu geldigini **degeri yazmadan** dogrula: `docker compose config 2>/dev/null | grep "GEMINI_API_KEY" | sed 's/=.*/=<gizli, uzunluk '"$(docker compose config 2>/dev/null | grep -m1 GEMINI_API_KEY | cut -d= -f2- | wc -c)"'>/'` → uzunluk > 20.

```bash
git add docker-compose.yml
git commit -m "feat(compose): GEMINI_API_KEY api ve worker'a .env'den

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
```

- [ ] **Step 2: Calisan is olmadigini dogrula ve yedek al**

```bash
docker compose exec -T teknoloji-worker celery -A cybernews inspect active 2>&1 | grep -E "empty|name"
docker compose exec -T teknoloji-api python -c "
import sqlite3
k = sqlite3.connect('/app/db.sqlite3'); h = sqlite3.connect('/tmp/db-yedek-gemini.sqlite3')
k.backup(h); h.close(); k.close()
print(sqlite3.connect('/tmp/db-yedek-gemini.sqlite3').execute('pragma integrity_check').fetchone()[0])"
docker cp teknoloji-api:/tmp/db-yedek-gemini.sqlite3 ../db-yedek-gemini-$(date +%Y%m%d-%H%M).sqlite3
docker tag teknoloji-haberleri-api:latest teknoloji-haberleri-api:geri-donus-$(date +%Y%m%d)-gemini
```

Expected: `- empty -`, `ok`, yedek git kokunun ust dizininde.

- [ ] **Step 3: Imaji yeniden kur (curl_cffi cikti), worker/scheduler'i durdur, migrate, yeniden olustur**

```bash
docker compose build teknoloji-api 2>&1 | grep -E "naming to|ERROR" | tail -2
docker compose stop teknoloji-worker teknoloji-scheduler
docker compose up -d --force-recreate teknoloji-api
sleep 6
docker compose exec -T teknoloji-api python manage.py migrate news 2>&1 | tail -2
docker compose up -d --force-recreate teknoloji-worker teknoloji-scheduler
sleep 8
docker compose ps --format "{{.Name}} {{.Status}}"
docker compose exec -T teknoloji-api python -c "import curl_cffi" 2>&1 | tail -1
docker compose exec -T teknoloji-api python manage.py check 2>&1 | tail -1
docker compose exec -T teknoloji-worker sh -c 'echo "GEMINI: ${GEMINI_API_KEY:+tanimli}${GEMINI_API_KEY:-YOK}"'
docker compose exec -T teknoloji-scheduler sh -c 'echo "scheduler GEMINI: ${GEMINI_API_KEY:-yok (dogru)}"'
```

Expected: `Applying news.0010_translation_provider_gemini... OK`; 6/6 Up; `ModuleNotFoundError: No module named 'curl_cffi'`; `no issues`; worker `tanimli`; scheduler `yok (dogru)`.

- [ ] **Step 4: Test paketini canli ortamda kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran|^OK|FAILED"`
Expected: `OK`. (Test calistiricisi anahtari bosalttigi icin canli konteynerde de Gemini'ye gidilmez.)

- [ ] **Step 5: Tek kayitlik gercek Gemini denemesi**

```bash
docker compose exec -T teknoloji-worker python manage.py shell -c "
from news import gemini
print('hazir:', gemini.hazir(), '| butce kullanimi:', gemini.butce_kullanimi())
s = gemini.kaydi_cevir({'title': 'Attackers exploit a new flaw in the parser',
                        'description': 'Unauthenticated attackers can execute arbitrary code remotely by sending a crafted request to the parse_array function in scenegraph/svg_attributes.c.'})
print(s)
print('butce kullanimi sonra:', gemini.butce_kullanimi())"
```

Expected: `hazir: True`; JSON sozluk iki Turkce alanla — `parse_array`, `scenegraph/svg_attributes.c` aynen; "kimliği doğrulanmamış saldırganlar" benzeri dogru terim; butce 1 artti. `hazir: False` veya `None` donerse **dur**, log satirini (`[Gemini] ...`) oku: HTTP 400/401/403 → anahtar/istek sorunu (kullaniciya sor); 429 → kota (AI Studio sayfasindan kontrol).

- [ ] **Step 6: Onceki durumu kaydet**

```bash
docker compose exec -T teknoloji-api python manage.py shell -c "
from news.models import *
from django.db.models import Count
prov={}; tb=0
for M in (CVEEntry, KubernetesEntry, NewsArticle, SREEntry, DevToolsEntry, AINewsEntry):
    tb += M.objects.filter(needs_translation=True).count()
    for p,c in M.objects.values_list('translation_provider').annotate(c=Count('id')).values_list('translation_provider','c'): prov[p or '(bos)']=prov.get(p or '(bos)',0)+c
print('bekleyen', tb, prov)"
```

- [ ] **Step 7: Retranslate'i calisan worker'da bir kez calistir ve izle**

```bash
docker compose exec -T teknoloji-worker python manage.py shell -c "
from news.tasks import retranslate_pending_task; print(retranslate_pending_task.apply_async().id)"
```

Sonra (gorev id'siyle) bitene kadar bekle:

```bash
until docker compose logs --since 40m teknoloji-worker 2>&1 | grep -q "retranslate_pending_task\[.*\] succeeded"; do sleep 20; done
docker compose logs --since 40m teknoloji-worker 2>&1 | grep -oE "retranslate_pending_task\[[^]]+\] succeeded in [0-9.]+s: \{.*" | tail -1 | cut -c1-600
docker compose logs --since 40m teknoloji-worker 2>&1 | grep -c "\[Gemini\]"
docker compose logs --since 40m teknoloji-worker 2>&1 | grep -oE "\[Gemini\] [a-z ]+(\([^)]*\))?" | sort | uniq -c | sort -rn | head
```

Expected: `by_provider.gemini > 0`, `upgraded > 0`, `stopped: False`; Gemini hata satirlari yoksa veya yalniz `dogrulama basarisiz` ise normal. `erisilemiyor (HTTP 429)` gorulurse RPM asilmis demektir: `GEMINI_MIN_INTERVAL` 5 → 8 yap (compose env), force-recreate, tekrar dene.

- [ ] **Step 8: Sonraki durum, butce ve Google'a giden istek**

Step 6'daki komutu tekrar calistir; `gemini` sayisi arttigini, `libretranslate` azaldigini gor.

```bash
docker compose exec -T teknoloji-api python manage.py shell -c "
from news import gemini; print('butce kullanimi:', gemini.butce_kullanimi(), '/', gemini.GEMINI_DAILY_BUDGET, '| anahtar:', gemini.butce_anahtari())"
docker compose exec -T teknoloji-api python manage.py shell -c "
import redis; from django.conf import settings
r = redis.Redis.from_url(settings.CELERY_RESULT_BACKEND)
print('gemini anahtarlari:', [k.decode() for k in r.scan_iter('gemini:*')])
print('translate:* (olu Google kapisi):', [k.decode() for k in r.scan_iter('translate:*')])"
docker compose logs --since 40m teknoloji-worker 2>&1 | grep -ci "google\|translate.googleapis\|/sorry/"
```

Expected: butce kullanimi = tur icinde atilan istek sayisi (upgraded + gemini ile cevrilen bekleyenler + basarisiz Gemini denemeleri); `gemini:budget:<tarih>` ve `gemini:slot` anahtarlari; Google satiri **0**. `translate:*` anahtari varsa (eski kapi) `r.delete(...)` ile temizle.

- [ ] **Step 9: Bir kac Gemini cevirisini gozle**

```bash
docker compose exec -T teknoloji-api python manage.py shell -c "
from news.models import CVEEntry, AINewsEntry, NewsArticle
for M in (CVEEntry, AINewsEntry, NewsArticle):
    for r in M.objects.filter(translation_provider='gemini').order_by('-updated_at')[:2]:
        print('==', M.__name__, r.id); print('EN:', r.original_description[:300].replace(chr(10),' | ')); print('TR:', r.turkish_description[:300].replace(chr(10),' | '))"
```

Expected: anlasilir Turkce, tanimlayicilar ve CVE/surum numaralari korunmus, satir yapisi korunmus. Ozel ad uydurma yok.

- [ ] **Step 10: API ve frontend**

```bash
TOKEN=$(docker compose exec -T teknoloji-api python manage.py shell -c "from rest_framework.authtoken.models import Token; print(Token.objects.get(user__username='entegrasyon').key)" | tail -1)
curl -s -H "Authorization: Token $TOKEN" "http://localhost:8000/api/v1/ai/?limit=200" | python -c "import sys,json; d=json.load(sys.stdin); import collections; print(collections.Counter(r['translation_provider'] for r in d['results']))"
curl -s "http://localhost:8000/api/ai/" | python -c "import sys,json; d=json.load(sys.stdin); print('provider alani:', 'translation_provider' in d['data'][0])"
```

Expected: `Counter({'gemini': n, 'libretranslate': m, ...})`; `True`. Tarayicida `http://localhost:3000/ai` ac (sayfayi bir kez yenile): listede gri "Çeviri: Gemini" ve sari "Makine çevirisi: LibreTranslate" rozetleri; detayda ayni; `http://localhost:3000/admin/` Django admin giris sayfasi.

- [ ] **Step 11: Gemini dusunce sistem calismaya devam ediyor mu**

```bash
docker compose exec -T teknoloji-worker python manage.py shell -c "
from news import gemini
from news.retranslate import retranslate_pending
gemini._get_gate().start_cooldown(120)   # 2 dk Gemini kapali
print('hazir:', gemini.hazir())
s = retranslate_pending(batch=3, upgrade_batch=3)
print({k: s[k] for k in ('translated','failed','upgraded','stopped','stopped_reason','by_provider')})
gemini._get_gate().start_cooldown(0)
print('hazir tekrar:', gemini.hazir())"
```

Expected: `hazir: False`; `stopped: False`, `upgraded: 0`, `stopped_reason: None` (devre kesici, butce degil), bekleyen varsa `by_provider.libretranslate > 0`; `hazir tekrar: True`.

- [ ] **Step 12: Son test ve push**

```bash
docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^Ran|^OK|FAILED"
git status --short
git push -u origin feat/gemini-yukseltme
```

PR ac (`gh pr create --base main`), CI yesil olunca merge; merge sonrasi `git checkout main && git pull --ff-only`. Kullaniciya 24 saat sonra bakilacak sayilari bildir: LibreTranslate kayit sayisi (Step 6 sonucu) ve `gemini:budget:*` (≤ 400).

---

### Task 7: Belgeler

**Files:**
- Modify: `README.md`, `docs/ADR-0004-Ceviri-Saglayici-Zinciri.md`, `docs/superpowers/specs/2026-09-15-gemini-yukseltme-design.md` (durum satiri), `docs/superpowers/specs/2026-09-14-ceviri-saglayici-zinciri-design.md` (durum satiri)

- [ ] **Step 1: README**

1. "Ceviri" satirini (satir ~135) su yap:
   `| **Ceviri** | Cekim aninda yerel LibreTranslate (aninda Turkce, rozetli); retranslate 2 saatte bir bekleyen ve LibreTranslate kayitlarini Gemini API (gemini-3.5-flash-lite, ucretsiz katman, kayit basina tek istek) ile yukseltir + merkezi post-processing |`
2. Ortam degiskenleri tablosuna (README'de `LIBRETRANSLATE_URL` nerede geciyorsa oraya; yoksa "Yapilandirma" bolumune yeni tablo) ekle:

| Degisken | Varsayilan | Anlam |
|---|---|---|
| `GEMINI_API_KEY` | (bos) | Google AI Studio anahtari; bos ise Gemini hic denenmez |
| `GEMINI_MODEL` | `gemini-3.5-flash-lite` | Model |
| `GEMINI_DAILY_BUDGET` | `400` | Gunluk istek butcesi (ucretsiz katman 500 RPD) |
| `GEMINI_MIN_INTERVAL` | `5` | Istekler arasi saniye (15 RPM'in altinda) |
| `GEMINI_COOLDOWN` | `600` | 429/5xx sonrasi bekleme (sn) |
| `GEMINI_TIMEOUT` | `60` | Istek zaman asimi (sn) |
| `RETRANSLATE_UPGRADE_BATCH` | `40` | Tur ve bolum basina yukseltme siniri |

3. Anahtar alma: "Google AI Studio (aistudio.google.com) → Get API key → Create API key; `cybersecurity_news/.env` icine `GEMINI_API_KEY=...` (gitignore'da). Kart gerekmez; kota asilirsa 429 doner, sistem LibreTranslate ile surer."
4. Rozetler: "Her kayit `translation_provider` tasir; arayuzde `Makine çevirisi: LibreTranslate` (sari), `Çeviri: Gemini`, `Çeviri: Google` (eski kayitlar)."
5. README'de `deep-translator`, `curl_cffi` veya "Google Translate" ile cekim anlatan cumle kaldiysa duzelt (`grep -n -i "deep-translator\|curl_cffi\|google" README.md`).

- [ ] **Step 2: ADR-0004 eki**

`docs/ADR-0004-Ceviri-Saglayici-Zinciri.md` — `## Consequences` bolumunden once:

```markdown
## Degisiklik (2026-09-15) — Google kaldirildi, Gemini yukseltme

Google Translate'in resmi olmayan uclari bu IP'den TLS parmak izi ve hacimle bloklandi (`/sorry/` CAPTCHA); `curl_cffi` ile acilan kapi hacimde yeniden kapandi. Kalici cozum: cekim aninda yalniz LibreTranslate; `retranslate` bekleyen ve LibreTranslate kayitlarini **Gemini API** (`gemini-3.5-flash-lite`, ucretsiz katman 500 RPD / 15 RPM) ile kayit basina tek istekle yukseltir; gunluk 400 istek butcesi + 5 sn aralik + devre kesici. `GoogleProvider`, `_translate_via_google`, `curl_cffi` silindi; `google` kayitlari etiketli kalir, yukseltilmez. Her kayit saglayici rozeti tasir. Tasarim: `superpowers/specs/2026-09-15-gemini-yukseltme-design.md`. Bu ADR'nin 3.1, 5 ve 7 numarali kararlari buna gore guncellenmistir; yerel LibreTranslate yedek olarak kalir.
```

- [ ] **Step 3: Spec durum satirlari**

- `2026-09-15-gemini-yukseltme-design.md`: durum satirini `- **Durum:** Uygulandi (<merge tarihi>, PR #<numara>). Onaylandi (2026-09-15).` bicimine getir; tarih ve PR numarasini Task 6'daki gercek degerlerle yaz.
- `2026-09-14-ceviri-saglayici-zinciri-design.md`: durum satirinin sonuna `Google yolu 2026-09-15'te kaldirildi; bkz. 2026-09-15-gemini-yukseltme-design.md.`

- [ ] **Step 4: Commit ve PR'a ekle**

```bash
git add README.md docs/
git commit -m "docs: README Gemini degiskenleri ve rozetler; ADR-0004 eki; spec durumlari

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push
```

(Task 6'nin PR'i henuz merge edilmediyse ayni PR'a girer; edildiyse `docs/gemini-belgeler` dalinda ayri kucuk PR.)

## Bitis Kriterleri

- [ ] `retranslate` turunda `by_provider.gemini > 0` ve `upgraded > 0`; Gemini cevirileri anlasilir, tanimlayicilar korunmus (Task 6 Step 7-9)
- [ ] Gemini gunluk butcesi hicbir gun 400'u asmadi (`gemini:budget:*`); RPM asimi (429) yok
- [ ] Google'a giden istek 0; `curl_cffi` ve `deep_translator` imajda yok
- [ ] Gemini kapaliyken (anahtar yok / devre kesici / butce) sistem LibreTranslate ile calismaya devam ediyor, Turkce kesilmiyor (Task 6 Step 11 + testler)
- [ ] Her kayitta dogru rozet: LibreTranslate sari, Gemini/Google gri, bos rozet yok; v1 `translation_provider` `gemini` donuyor
- [ ] `localhost:3000/admin/` Django admin'e gidiyor; frontend degisikligi HMR ile yansiyor
- [ ] Hicbir test gercek Gemini/LibreTranslate/Google'a gitmiyor; test paketi yesil
- [ ] Bekleyen sayisi ve LibreTranslate kayit sayisi 24 saat icinde belirgin dususte (978 → birkac gunde ~0)

## Sonrasi

- **A4:** `FetchRun.by_provider` (`gemini`, `libretranslate`); `/api/v1/status/` icinde `gemini: {budget_used, budget_limit, circuit_open}` ve retranslate son turu (`stopped_reason` dahil). A4 migration icerir: worker/scheduler durdurma adimi planda acikca yer almali.
- **A5:** README entegrasyon bolumu (v1), drf-spectacular, ornek istemci; `GEMINI_*` zaten README'de.
- **Faz B:** Helm secret'a `GEMINI_API_KEY`, configmap'e `GEMINI_*`.
- Gozlem: LibreTranslate yolu artik yalniz "ilk 2 saat" icin; ilerde Gemini yeterince guvenilirse cekim aninda Gemini (kayit duzeyi, butce kontrollu) dusunulebilir — kapsam disi.
