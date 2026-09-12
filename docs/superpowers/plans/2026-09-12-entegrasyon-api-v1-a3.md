# Entegrasyon API v1 — A3 Uygulama Plani (Ceviri Dogrulugu ve Cache)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** "Cevrildi" gorunen her kaydin gercekten ve eksiksiz Turkceye cevrildiginden emin olmak, cevrilemeyen kayitlarin sonsuza kadar askida kalmasini onlemek ve fetch task'larindaki cache israfini kaldirmak — frontend'in cekim sirasinda kayitlari akis halinde gostermesini bozmadan.

**Architecture:** `translation_utils.translate_text` Google'dan donen metni geri koymadan once onarir, sonra dogrular (eksik yer tutucu, yanki, kirpilma, kalinti); dogrulanamayan metin orijinal kalir ve basarisizlik sayacina islenir. Yeni `news/retranslate.py` ceviri bekleyen kayitlari feed'e bakmadan, bolum basina Redis imleciyle sirayla yeniden cevirir ve iki saatte bir Beat ile calisir. Yeni `news/cache_utils.py` alti fetch task'inin cache kurmasini tek yerde toplar. Mevcut bozuk kayitlar icin bir management komutu eklenir.

**Tech Stack:** Django 4.2.7, Celery 5.3.4 (beat: `PersistentScheduler`), django-redis 5.4.0, deep-translator 1.11.4. **Yeni pip bagimliligi ve yeni migration yok.**

**Spec:** `docs/superpowers/specs/2026-09-12-entegrasyon-api-v1-design.md` — bolum 9 ve 10. Bu plan spec'ten 13 noktada ayrilir; hepsi asagida "Spec'e Gore Netlestirmeler" altinda gerekceleriyle.

**Onceki planlar:** A1 ve A2 (ikisi de tamamlandi, `main`'de, canlida dogrulandi).

## Global Constraints

- **Hicbir test gercek Google'a gitmez.** Ceviri testleri `news.tests.test_translation` icindeki `TranslationGateMixin` + `FakeTranslator` ile yazilir veya `tu._translate_via_google` patch'lenir. `FakeTranslator` bilinmeyen metne **hata sayfasi** doner ve bu devre kesiciyi acar — basari bekleyen testte cevrilecek her metnin (terimler korunmus haliyle) cevabi verilmelidir.
- **Hicbir test gercek Celery isi kuyruga atmaz.** Retranslate testleri fonksiyonu dogrudan cagirir.
- **Redis kullanan testler benzersiz onek kullanir ve kendi anahtarlarini siler.** `FLUSHDB`/`FLUSHALL` yasak; db 0 canli cache.
- **Cache yazan testler `@override_settings(CACHES=LOCMEM_CACHE)` kullanir** ve `setUp`'ta `cache.clear()` cagirir.
- **Bu planda migration yoktur.** Bilincli bir karar (bkz. netlestirme 8); modellere alan eklenmez.
- **`news/views.py` degistirilmez.** Cache surumleme (C3) ayar uzerinden yapilir.
- **`translate_text`'in dis sozlesmesi korunur:** cevrilemeyen metin orijinal haliyle doner ve `consume_translation_failures()` sayaci artar. Task'lar ve scraper'lar buna guveniyor.
- **Kod yorumlari ve kullanici mesajlari Turkce, aksansiz.**
- **Testler konteyner icinde:** `docker compose exec -T teknoloji-api python manage.py test ...`
- **Her task kendi commit'ini atar**; mesaj sonu `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` (uygulayan model neyse o).
- **Calisma dali:** `feat/entegrasyon-api-v1-a3`, guncel `main`'den acilir (`git checkout main && git pull --ff-only`).

## Ortam Notlari

| Konu | Deger |
|---|---|
| Proje / git koku | `cybersecurity_news/` |
| Konteynerlar | `teknoloji-api` (gunicorn), `teknoloji-worker` (celery), `teknoloji-scheduler` (celery beat, `PersistentScheduler`), `teknoloji-redis` |
| **Kod yeniden yukleme yok** | Canli dogrulamadan once `docker compose restart teknoloji-api teknoloji-worker teknoloji-scheduler`. Yeni Beat girdisi de ancak scheduler yeniden baslayinca gorunur. |
| Mevcut test sayisi | 103, ~3 sn |
| Ceviri durumu (2026-09-12) | 831 kaydin 384'u `needs_translation=True`; ucretsiz Google ucu kisitlamali, devre kesici sik aciliyor |
| Yer tutucu formati | `XTRM0001X` (4 hane, 1'den baslar, olusturulma sirasiyla artar) |

## A2 Sonrasi Tespit Edilen Gercek Hatalar

**H5 — Ic ice yer tutucu geri konmuyor.** `_protect_terms` sonraki adimlarda (URL deseni gibi) zaten yer tutucu iceren metni tekrar tarar; `https://example.com/XTRM0001X` butun olarak `XTRM0002X`'in degeri olur. `_restore_terms` esit uzunluktaki kodlari olusturulma sirasiyla geri koydugu icin once `XTRM0001X`'i arar (metinde yok), sonra `XTRM0002X`'i acar ve icinden cikan `XTRM0001X` metinde kalir. Olcum: canli 651 CVE aciklamasindan 4'unde ic ice yer tutucu var; Google'siz kimlik cevirisinde bu 4'u bozuk cikiyor, ters sirali geri koyma ile 0.

**H6 — Bozuk yer tutucu geri koymadan SONRA onariliyor.** Google yer tutucuyu `xtrm 0001x` gibi dondurebilir. `translate_text` once `_restore_terms` cagiriyor (bozuk kodu bulamaz), sonra `turkish_post_process` bozuk kodu `XTRM0001X`'e onariyor — artik hic geri konamaz ve **basarili sayilir**. Google'siz deterministik olarak yeniden uretildi: `'The Kubernetes scheduler crashed…'` → cikti `'The XTRM0001X scheduler crashed…'`, basarisizlik sayilmadi.

**Canlidaki etkisi:** 19 CVE kaydi `needs_translation=False` iken Turkce aciklamasinda ham `XTRM` kodu tasiyor. 4'u H5, 15'i H6 ile uyumlu. Ornek `CVE-2026-11746`: 30 satirlik bir Java kod blogu yerine metinde `XTRM0021X` yaziyor.

**Elenen hipotez:** `k8s_scraper._translate_structured_changelog` metni kendisi korumaya alip `translate_long_text`'e veriyor (cift koruma). Iki katman da 0001'den saydigi icin carpisma supheliydi. Olculdu: 5 gercek changelog kaydinda kimlik cevirisinde terim sayilari birebir korundu — dis katman butun desenleri aldigi icin ic katman degistirecek bir sey bulmuyor. **Duzeltme gerekmez**, ama dogrulama bu yolu kirmamalidir (bkz. netlestirme 7).

## Spec'e Gore Netlestirmeler

1. **Yer tutucu formati `XTRM0001X`'tir.** Spec 9.2 `__TERM_n__` diyordu; yanlisti.
2. **H5 ve H6 kapsama eklendi** (Task 1). Spec'te yoktu; canli veride 19 bozuk kayit uretmisler.
3. **Yanki kelime sayisi yer tutucular cikarilarak hesaplanir.** `'kubectl apply on Windows nodes'` korunmus haliyle `'XTRM… apply on XTRM… XTRM…'`; cevrilecek 2 kelime var. Terimler sayilsaydi mesru olarak degismeyen terim agirlikli metinler yanlis alarm verirdi.
4. **Kirpilma kontrolu yalnizca >= 80 karakterlik metinlerde uygulanir.** Kisa metinlerde Turkce karsilik mesru olarak cok kisa olabilir (`'The fix is available now for all users.'` 39 karakter → `'Duzeltme hazir.'` 15 karakter).
5. **Yeni kontrol: eksik yer tutucu.** Google bir yer tutucuyu dusururse korunan terim (veya koca bir kod blogu) Turkce metinden sessizce kaybolur. Kalinti kontrolunun ikizidir.
6. **Dogrulama basarisizligi yeniden deneme ve devre kesici tetiklemez.** Sorun erisim degil icerik; ayni metni hemen tekrar gondermek kotayi yakar, devre kesici acmak tum cevirileri 20 dk durdururdu. Kayit `needs_translation` ile isaretlenir, retranslate daha sonra dener.
7. **Eksik yer tutucu ve kalinti kontrolleri yalnizca o cagrinin kendi urettigi kodlara bakar.** K8s dis katmani `translate_long_text`'e zaten `XTRM` kodu iceren metin verir; o kodlar ic cagrinin eslemesinde yoktur ve dis katman tarafindan geri konacaktir. Hepsine bakilsaydi her yapisal changelog basarisiz sayilirdi.
8. **Retranslate siralamasi: bolum basina Redis imleci, migration yok.** Spec "en eskiden baslayarak 50 kayit" diyordu. Salt en-eski-once siralamada hep basarisiz olan kayitlar kuyrugun onunu kalici olarak tikar (her tur ayni kayitlari dener). Imlec basarisiz kaydi gecer; sona gelince bastan baslar. Basarisiz denemede kayda yazilmaz, boylece `updated_at` ilerlemez ve tuketicinin delta akisina degismemis kayit dusmez. Alternatif (modele `translation_attempted_at` alani) migration gerektirirdi; 2026-09-12'deki migration regresyonundan sonra bilincli olarak kacinildi. A1'in imlec kodu (`api_v1/cursor.py`) yeniden kullanilir.
9. **`RETRANSLATE_BATCH` bolum basinadir, varsayilan 8** (tur basina en fazla 48). Tek bir toplam sinir, en kalabalik bolumun (CVE: 159 bekleyen) diger bolumleri ac birakmasina yol acardi.
10. **Beat saati `crontab(minute=5, hour='1-23/2')`** — tek saatler. Spec `hour='*/2'` diyordu; bu 00/06/12/18'i de kapsar ve o saatler alti fetch task'inin calistigi saatlerdir. Tek saatler hic cakismaz.
11. **C1: cache her kayitta degil, her 10 kayitta bir ve cekim sonunda kurulur.** Spec "dongu bitince bir kez" diyordu. Frontend alti bolumun bes bileseninde listeyi 5 sn'de bir yeniden istiyor ve cekim surerken yeni kayitlarin ekrana akmasina dayaniyor. Yalnizca sonda yazilsaydi ekran ilk anlik goruntude donar, cekim bitince birden atlardi. Her 10 kayitta bir yazmak olculen israfin (~60 ms × kayit sayisi) yaklasik %90'ini kaldirir ve akisi korur.
12. **C3: surumleme `CACHES['default']['VERSION'] = 2` ile yapilir.** Anahtar adlarini `views.py` ve `tasks.py`'de tek tek degistirmek yerine Django'nun yerlesik cache surumu kullanilir; serializer sekli degistiginde bu sayi artirilir. Yan etkisi: DRF throttle sayaclari da yeni surume gecer (bir kez sifirlanir) — zararsiz.
13. **C4 spec'teki gibi calismiyor, duzeltildi.** Spec "C1 sonrasi ya eski tam liste ya yeni tam liste doner" diyordu. Gercekte fetch view'i cache'i siler, frontend'in bir sonraki istegi veritabanindan o anki kismi listeyi alip **1 saatligine** cache'ler. Cekim sirasinda gorulen liste zaten kismidir; bu kabul edilebilir cunku veritabanindaki gercek durumdur. Onemli olan eski kismi anlik goruntunun uzun sure kalmamasidir; bunu periyodik yeniden kurma (netlestirme 11) saglar.
14. **Yeni: `bozuk_cevirileri_isaretle` management komutu** (Task 6). H5/H6 duzeltmesi yeni cevirileri korur ama mevcut 19 bozuk kayit `needs_translation=False` oldugu icin retranslate onlari hic almaz.

## Dosya Yapisi

**Olusturulacak:**

| Dosya | Sorumluluk |
|---|---|
| `news/cache_utils.py` | `/api/*` liste cache'lerinin tek noktadan kurulmasi; C1, C5 |
| `news/retranslate.py` | Bekleyen kayitlari feed'siz, imlecli, bolum bolum yeniden cevirme |
| `news/management/__init__.py`, `news/management/commands/__init__.py` | Bos paket isaretcileri |
| `news/management/commands/bozuk_cevirileri_isaretle.py` | Mevcut bozuk cevirileri isaretleme |
| `news/tests/test_translation_verify.py` | H5, H6 ve dogrulama kurallari |
| `news/tests/test_cache.py` | C1, C2, C3, C5 |
| `news/tests/test_retranslate.py` | Retranslate, Celery gorevi, Beat takvimi, komut |

**Degistirilecek:**

| Dosya | Degisiklik |
|---|---|
| `news/translation_utils.py` | `_restore_terms` sirasi, `_repair_placeholders`, `verify_translation`, `translate_text` akisi |
| `news/tasks.py` | Cache yazimi `cache_utils`'e; `retranslate_pending_task` |
| `cybernews/settings.py` | `CACHES` surumu; Beat girdisi |

---

### Task 1: Yer tutucu geri koyma hatalari (H5, H6)

**Files:**
- Modify: `news/translation_utils.py`
- Create: `news/tests/test_translation_verify.py`

**Interfaces:**
- Consumes: yok
- Produces:
  - `_PLACEHOLDER_RE: re.Pattern` — `XTRM\d{4}X`
  - `_repair_placeholders(text: str) -> str` — `xtrm 0001x` gibi bozuk kodlari `XTRM0001X`'e cevirir
  - `_restore_terms(text, replacements)` — imza ayni; artik en son olusturulan koddan ilkine dogru geri koyar
  - `translate_text` Google cevabini geri koymadan once onarir

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_translation_verify.py`:

```python
"""Ceviri dogrulugu testleri (spec bolum 9, A3 plani H5/H6).

2026-09-12'de 19 CVE kaydi 'cevrildi' isaretliyken Turkce aciklamasinda ham
XTRM yer tutucusu tasiyordu. Bu testler o iki hatayi ve yeni dogrulama
kurallarini korur. Google hicbir testte cagrilmaz.
"""
import re
from unittest import mock

from django.test import SimpleTestCase, TestCase

from news import translation_utils as tu
from news.tests.test_translation import FakeTranslator, TranslationGateMixin

KALINTI = re.compile(r'XTRM\d{4}X')


class YerTutucuGeriKoymaTests(SimpleTestCase):

    def setUp(self):
        tu.consume_translation_failures()

    def test_ic_ice_yer_tutucu_tamamen_geri_konur(self):
        """URL deseni onceden korunmus bir kod parcasinin yer tutucusunu yutabilir (H5)."""
        metin = 'Update the image at https://example.com/`v1.2` before rollout.'
        korunmus, esleme = tu._protect_terms(metin)
        self.assertTrue(any(KALINTI.search(deger) for deger in esleme.values()),
                        'On kosul: bu girdi ic ice yer tutucu uretmeli')

        self.assertEqual(tu._restore_terms(korunmus, esleme), metin)

    def test_bozuk_donen_yer_tutucu_onarilip_geri_konur(self):
        """Google 'xtrm 0001x' dondurebilir; onarma geri koymadan ONCE yapilmali (H6)."""
        metin = 'The Kubernetes scheduler crashed today.'
        with mock.patch.object(tu, '_translate_via_google',
                               return_value='xtrm 0001x zamanlayıcısı bugün çöktü.'):
            sonuc = tu.translate_text(metin)

        self.assertEqual(sonuc, 'Kubernetes zamanlayıcısı bugün çöktü.')
        self.assertIsNone(KALINTI.search(sonuc))
        self.assertEqual(tu.consume_translation_failures(), 0)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_verify -v 2 2>&1 | tail -20`
Expected: iki test de FAIL — ilki `'Update the image at https://example.com/XTRM0001X before rollout.' != ...`, ikincisi `'XTRM0001X zamanlayıcısı bugün çöktü.' != 'Kubernetes zamanlayıcısı bugün çöktü.'`

- [ ] **Step 3: Duzeltmeyi yaz**

`news/translation_utils.py` — "2. TERIM KORUMA MEKANIZMASI" basligi altinda, `_protect_terms` fonksiyonundan **once** ekle:

```python
_PLACEHOLDER_RE = re.compile(r'XTRM\d{4}X')
# Google yer tutucuyu bosluklu veya kucuk harfli dondurebilir: 'xtrm 0001x', 'X TRM0001 X'
_BROKEN_PLACEHOLDER_RE = re.compile(r'[Xx]\s*[Tt]\s*[Rr]\s*[Mm]\s*(\d{4})\s*[Xx]')


def _repair_placeholders(text: str) -> str:
    """Google'in bozdugu yer tutuculari standart bicime getirir.

    Geri koymadan ONCE cagrilmalidir; sonra cagrilirsa onarilan kod artik hic
    geri konamaz ve ceviride ham 'XTRM0001X' kalir.
    """
    return _BROKEN_PLACEHOLDER_RE.sub(r'XTRM\1X', text)
```

`_restore_terms` fonksiyonunu tamamen su hale getir:

```python
def _restore_terms(text: str, replacements: Dict[str, str]) -> str:
    """Placeholder'lari orijinal terimlerle geri degistirir.

    Sira onemlidir: bir yer tutucunun degeri yalnizca kendisinden ONCE
    olusturulmus yer tutuculari icerebilir (orn. URL deseni onceden korunmus bir
    kod parcasinin kodunu yutar). Bu yuzden en son olusturulandan ilkine dogru
    geri konur; boylece ic ice kodlar da acilir.
    """
    result = text
    for ph in sorted(replacements, key=lambda kod: int(kod[4:8]), reverse=True):
        result = result.replace(ph, replacements[ph])
    return result
```

`translate_text` icinde su satiri:

```python
        restored = _restore_terms(translated, replacements)
```

su iki satirla degistir:

```python
        # Google yer tutucuyu 'xtrm 0001x' gibi bozabilir; geri koymadan ONCE onarilmali
        translated = _repair_placeholders(translated)
        restored = _restore_terms(translated, replacements)
```

`turkish_post_process` icindeki "1. Bozuk placeholder'lari onar" adimina **dokunma**; zararsizdir ve baska cagiranlar (`k8s_scraper`) ona guvenebilir.

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_verify -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 2 tests`, `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 105 tests`, `OK`

- [ ] **Step 6: Duzeltmenin canli veride etkisini olc (Google'siz)**

```bash
docker compose exec -T teknoloji-api python - <<'PY'
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybernews.settings')
django.setup()
from news import translation_utils as tu
from news.models import CVEEntry
bozuk = 0
for o in CVEEntry.objects.only('original_description'):
    metin = o.original_description or ''
    korunmus, esleme = tu._protect_terms(metin)
    if tu._restore_terms(korunmus, esleme) != metin:
        bozuk += 1
print('kimlik cevirisinde bozulan CVE aciklamasi:', bozuk)
PY
```

Expected: `0` (duzeltmeden once 4 idi).

- [ ] **Step 7: Commit**

```bash
git add news/translation_utils.py news/tests/test_translation_verify.py
git commit -m "$(cat <<'MSG'
fix: ceviride ham XTRM yer tutucusu kalmasina yol acan iki hata

Ic ice yer tutucu: _protect_terms URL gibi desenleri zaten yer tutucu
iceren metin uzerinde calistirdigi icin bir kodun degeri baska bir kodu
icerebiliyordu. _restore_terms esit uzunluktaki kodlari olusturulma
sirasiyla geri koydugu icin ic kod metinde kaliyordu. Artik en son
olusturulandan ilkine dogru geri konuyor.

Onarma sirasi: Google yer tutucuyu 'xtrm 0001x' gibi dondurdugunde
translate_text once geri koymaya calisip bulamiyor, turkish_post_process
ise kodu sonradan onariyordu; sonuc ham XTRM0001X iceriyor ve basarili
sayiliyordu. Onarma artik geri koymadan once yapiliyor.

Canlida 19 CVE kaydi bu yuzden Turkce aciklamasinda XTRM kodu tasiyor
(4'u ic ice, 15'i onarma sirasi ile uyumlu).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: Ceviri dogrulamasi

**Files:**
- Modify: `news/translation_utils.py`
- Modify: `news/tests/test_translation_verify.py`

**Interfaces:**
- Consumes: `_PLACEHOLDER_RE`, `_repair_placeholders`, `_restore_terms` (Task 1)
- Produces:
  - Sabitler: `MIN_RATIO: float` (env `TRANSLATE_MIN_RATIO`, varsayilan 0.4), `ECHO_MIN_WORDS = 4`, `TRUNCATION_MIN_CHARS = 80`
  - `verify_translation(protected: str, translated: str, placeholders: Iterable[str]) -> Optional[str]` — sorun yoksa `None`, varsa kisa sebep: `'eksik yer tutucu (n)'`, `'yanki'`, `'kirpilma'`. `translated`, onarilmis ama henuz geri konmamis Google cevabidir.
  - `translate_text`: dogrulama basarisizsa orijinal metni doner, sayaci artirir, **yeniden denemez ve devre kesici acmaz**

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_translation_verify.py` sonuna ekle:

```python
UZUN_METIN = ('The researchers published a detailed report describing how the '
              'vulnerability can be exploited remotely.')  # 103 karakter


class CeviriDogrulamaTests(TranslationGateMixin, TestCase):
    """Guvenilmez ceviri: metin orijinal kalir, sayac artar, Google'a tekrar
    gidilmez ve devre kesici acilmaz."""

    def _cevir(self, metin, google_cevabi):
        cevirmen = self.use_translator(FakeTranslator(default=google_cevabi))
        return tu.translate_text(metin), cevirmen

    def _basarisiz_sayildi(self, sonuc, metin, cevirmen):
        self.assertEqual(sonuc, metin)
        self.assertEqual(tu.consume_translation_failures(), 1)
        self.assertEqual(len(cevirmen.calls), 1, 'Dogrulama hatasi yeniden deneme tetiklememeli')
        self.assertFalse(tu._gate.cooldown_active(), 'Dogrulama hatasi devre kesiciyi acmamali')

    def test_yanki_basarisiz_sayilir(self):
        metin = 'Attackers exploited the flaw to steal session cookies.'
        sonuc, cevirmen = self._cevir(metin, metin)
        self._basarisiz_sayildi(sonuc, metin, cevirmen)

    def test_yanki_bosluk_ve_buyuk_harf_farkini_yok_sayar(self):
        metin = 'Attackers exploited the flaw to steal session cookies.'
        sonuc, cevirmen = self._cevir(metin, '  ' + metin.upper() + ' ')
        self._basarisiz_sayildi(sonuc, metin, cevirmen)

    def test_dort_kelimeden_kisa_yanki_basari_sayilir(self):
        sonuc, _ = self._cevir('Security patch released', 'Security patch released')
        self.assertEqual(sonuc, 'Security patch released')
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_terimlerden_olusan_yanki_basari_sayilir(self):
        """Yer tutucular kelime sayilmaz: 'Kubernetes v1.31.0' cevrilecek kelime icermez."""
        metin = 'Kubernetes v1.31.0'
        korunmus, _ = tu._protect_terms(metin)
        sonuc, _ = self._cevir(metin, korunmus)
        self.assertEqual(sonuc, 'Kubernetes v1.31.0')
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_terim_agirlikli_metin_yanki_basari_sayilir(self):
        metin = 'kubectl apply on Windows nodes'  # cevrilecek kelime: apply, on
        korunmus, _ = tu._protect_terms(metin)
        self._cevir(metin, korunmus)
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_kirpilma_basarisiz_sayilir(self):
        sonuc, cevirmen = self._cevir(UZUN_METIN, 'Araştırmacılar rapor yayımladı.')
        self._basarisiz_sayildi(sonuc, UZUN_METIN, cevirmen)

    def test_kisa_metinde_kisalma_basari_sayilir(self):
        sonuc, _ = self._cevir('The fix is available now for all users.', 'Düzeltme hazır.')
        self.assertEqual(sonuc, 'Düzeltme hazır.')
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_normal_uzun_ceviri_basari_sayilir(self):
        ceviri = ('Araştırmacılar, güvenlik açığının uzaktan nasıl istismar '
                  'edilebileceğini anlatan ayrıntılı bir rapor yayımladı.')
        sonuc, _ = self._cevir(UZUN_METIN, ceviri)
        self.assertEqual(sonuc, ceviri)
        self.assertEqual(tu.consume_translation_failures(), 0)

    def test_eksik_yer_tutucu_basarisiz_sayilir(self):
        """Google bir yer tutucuyu dusururse korunan terim Turkce metinden sessizce kaybolurdu."""
        metin = 'Upgrade Kubernetes before applying the Helm chart changes.'
        _, esleme = tu._protect_terms(metin)
        kube = next(kod for kod, deger in esleme.items() if deger == 'Kubernetes')
        sonuc, cevirmen = self._cevir(
            metin, f'Grafik değişikliklerini uygulamadan önce {kube} sürümünü yükseltin.')
        self._basarisiz_sayildi(sonuc, metin, cevirmen)

    def test_geri_konamayan_yer_tutucu_basarisiz_sayilir(self):
        """Son emniyet kontrolu: geri koyma herhangi bir sebeple eksik kalirsa kayit 'cevrildi' sayilmaz."""
        metin = 'Upgrade Kubernetes before applying the Helm chart changes.'
        korunmus, esleme = tu._protect_terms(metin)
        google = korunmus.replace('Upgrade', 'Yükseltin:').replace('before applying the', 'önce').replace('chart changes', 'değişiklikleri')
        with mock.patch.object(tu, '_restore_terms', side_effect=lambda metin_, esleme_: metin_):
            sonuc, _ = self._cevir(metin, google)
        self.assertEqual(sonuc, metin)
        self.assertEqual(tu.consume_translation_failures(), 1)

    def test_dis_katmanin_yer_tutuculari_kalinti_sayilmaz(self):
        """k8s_scraper metni kendisi korumaya alip verir; o kodlari dis katman geri koyar."""
        metin = 'XTRM0007X crashes when XTRM0008X is restarted on the host machine.'
        ceviri = 'XTRM0007X, ana makinede XTRM0008X yeniden başlatıldığında çöküyor.'
        sonuc, _ = self._cevir(metin, ceviri)
        self.assertEqual(sonuc, ceviri)
        self.assertEqual(tu.consume_translation_failures(), 0)


class VerifyTranslationTests(SimpleTestCase):
    """Saf fonksiyon: sebep metinleri loglarda gorunur, sozlesmenin parcasidir."""

    def test_sebepler(self):
        self.assertIsNone(tu.verify_translation('Hello world', 'Merhaba dünya', []))
        self.assertEqual(tu.verify_translation('a XTRM0001X b', 'a b', ['XTRM0001X']), 'eksik yer tutucu (1)')
        self.assertEqual(tu.verify_translation('one two three four', 'One two three four', []), 'yanki')
        self.assertEqual(tu.verify_translation(UZUN_METIN, 'Kısa.', []), 'kirpilma')
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_verify -v 2 2>&1 | tail -30`
Expected: yanki, kirpilma, eksik yer tutucu ve geri konamayan yer tutucu testleri FAIL; `VerifyTranslationTests` ERROR (`has no attribute 'verify_translation'`). Basari bekleyen testlerin bir kismi zaten gecebilir — bu beklenir.

- [ ] **Step 3: Dogrulamayi yaz**

`news/translation_utils.py` — import satirini genislet:

```python
from typing import Dict, Iterable, List, Optional, Tuple
```

"3. GOOGLE TRANSLATE CEVIRI" bolumunde `ERROR_KEYWORDS` tanimindan hemen sonra ekle:

```python
# Dogrulama esikleri (spec 9.2, A3 plani netlestirme 3-7).
# Google yanit verdi ama sonuc guvenilmezse metin orijinal kalir ve kayit
# needs_translation ile isaretlenir. Erisim hatasindan farkli olarak yeniden
# deneme ve devre kesici UYGULANMAZ: sorun icerik, ayni metni tekrar gondermek
# kotayi yakar.
MIN_RATIO = float(os.environ.get('TRANSLATE_MIN_RATIO', '0.4'))
# 'Kubernetes 1.31', 'CVE-2026-1234' gibi kisa metinler mesru olarak ayni kalir
ECHO_MIN_WORDS = 4
# Kisa metinlerin Turkce karsiligi mesru olarak cok kisa olabilir
TRUNCATION_MIN_CHARS = 80


def _normalize_for_echo(text: str) -> str:
    return re.sub(r'\s+', ' ', text).strip().casefold()


def _translatable_word_count(protected: str) -> int:
    """Yer tutucular cikarildiktan sonra kalan, en az iki harfli kelime sayisi."""
    return len(re.findall(r'[^\W\d_]{2,}', _PLACEHOLDER_RE.sub(' ', protected)))


def verify_translation(protected: str, translated: str,
                       placeholders: Iterable[str]) -> Optional[str]:
    """Google cevabinin guvenilir olup olmadigini soyler.

    protected: Google'a gonderilen, terimleri korunmus metin.
    translated: Onarilmis ama henuz geri konmamis Google cevabi.
    placeholders: Bu cagrinin urettigi kodlar. Metinde bunlarin disinda kod
    olabilir (k8s_scraper dis katmani); onlar burada denetlenmez.

    Sorun yoksa None, varsa kisa bir sebep dondurur.
    """
    eksik = [kod for kod in placeholders if kod not in translated]
    if eksik:
        return f'eksik yer tutucu ({len(eksik)})'
    if (_normalize_for_echo(translated) == _normalize_for_echo(protected)
            and _translatable_word_count(protected) >= ECHO_MIN_WORDS):
        return 'yanki'
    if len(protected) >= TRUNCATION_MIN_CHARS and len(translated) < MIN_RATIO * len(protected):
        return 'kirpilma'
    return None
```

`translate_text` fonksiyonunun `try` blogunu tamamen su hale getir:

```python
    try:
        protected, replacements = _protect_terms(text)
        translated = _translate_via_google(protected)
        if translated is None:
            _failure_count += 1
            return text

        # Google yer tutucuyu 'xtrm 0001x' gibi bozabilir; geri koymadan ONCE onarilmali
        translated = _repair_placeholders(translated)
        sorun = verify_translation(protected, translated, replacements)
        if sorun is None:
            restored = _restore_terms(translated, replacements)
            if any(kod in restored for kod in replacements):
                sorun = 'yer tutucu kalintisi'
        if sorun:
            print(f"  [Ceviri] Dogrulama basarisiz ({sorun}); metin orijinal haliyle birakildi.")
            _failure_count += 1
            return text

        return turkish_post_process(restored)
    except Exception as e:
        print(f"  [Ceviri] Hata: {e}")
        _failure_count += 1
        return text
```

Fonksiyonun docstring'ine su satiri ekle: `Google cevabi dogrulanamazsa da (bkz. verify_translation) orijinal metin doner.`

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_translation_verify -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 14 tests`, `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 117 tests`, `OK`. **`test_translation.py` icindeki mevcut 12 testten biri duserse durma, sebebini bildir:** o testin `FakeTranslator` cevabi yeni kurallara gore gercekten guvenilmez bir ceviri mi (o zaman test verisi yanlistir), yoksa kural yanlis alarm mi veriyor (o zaman kural yanlistir). Planlama sirasinda 12 testin girdileri incelendi; hicbiri yanki, kirpilma veya eksik yer tutucu senaryosu kullanmiyor.

- [ ] **Step 6: Commit**

```bash
git add news/translation_utils.py news/tests/test_translation_verify.py
git commit -m "$(cat <<'MSG'
feat: Google cevabini geri koymadan once dogrula

Dort kontrol: eksik yer tutucu (korunan terim veya kod blogu sessizce
kaybolmasin), yanki (>= 4 cevrilecek kelime; yer tutucular sayilmaz),
kirpilma (>= 80 karakterlik metinde cikti girdinin %40'indan kisaysa)
ve geri koyma sonrasi yer tutucu kalintisi.

Dogrulanamayan metin orijinal kalir ve basarisizlik sayacina islenir;
kayit needs_translation ile isaretlenir. Erisim hatasindan farkli olarak
yeniden deneme ve devre kesici uygulanmaz: sorun icerik, ayni metni tekrar
gondermek ucretsiz kotayi yakar.

Kontroller yalnizca o cagrinin urettigi kodlara bakar; k8s_scraper'in dis
katmanindan gelen kodlar denetlenmez.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: Cache duzeltmeleri (C1, C3, C5)

**Files:**
- Create: `news/cache_utils.py`, `news/tests/test_cache.py`
- Modify: `news/tasks.py`, `cybernews/settings.py`

**Interfaces:**
- Consumes: yok
- Produces (`news/cache_utils.py`):
  - `CACHE_LISTE_SINIRI = 100`, `CACHE_SURESI = 3600`, `CACHE_YENILEME_ARALIGI = 10`
  - `cache_yenile(bolum: str) -> None` — `bolum` ∈ `news, cve, kubernetes, sre, devtools, ai`; o bolumun `/api/*` liste cache'ini ve son guncelleme zamanini yeniden kurar. Anahtar adlari degismez (`cve_entries`, `cve_last_update` ...).
- `settings.CACHES['default']['VERSION'] == 2`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_cache.py`:

```python
"""Cache testleri (spec bolum 10, A3 plani netlestirme 11-13)."""
from datetime import date
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from news import tasks
from news.models import AINewsEntry
from news.tests.base import LOCMEM_CACHE, V1TestCase
from news.tests.test_translation import FakeTranslator, TranslationGateMixin


@override_settings(CACHES=LOCMEM_CACHE)
class FetchCacheYenilemeTests(TranslationGateMixin, TestCase):
    """C1: cache her kayitta degil, her 10 kayitta bir ve cekim sonunda kurulur."""

    def setUp(self):
        super().setUp()
        cache.clear()
        # Bilinmeyen metne hata sayfasi: ilk cagrida devre kesici acilir, test hizli kalir
        self.use_translator(FakeTranslator())

    def _cek(self, adet):
        girdiler = [{
            'title': f'Cache test haberi {i}', 'description': f'Cache test govdesi {i}.',
            'link': f'https://ornek.test/cache/{i}', 'date': date.today().strftime('%Y-%m-%d'),
            'source': 'MIT Tech Review AI',
        } for i in range(adet)]
        from news import cache_utils
        with mock.patch.object(tasks.MultiAINewsScraper, 'fetch_all', return_value=girdiler), \
             mock.patch('news.tasks.cache_yenile', wraps=cache_utils.cache_yenile) as casus:
            sonuc = tasks.fetch_ai_news_task(days=30)
        return sonuc, casus

    def test_25_kayitta_cache_uc_kez_kurulur(self):
        sonuc, casus = self._cek(25)
        self.assertEqual(sonuc, {'success': True, 'count': 25})
        self.assertEqual(casus.call_count, 3)  # 10. kayit, 20. kayit, cekim sonu
        self.assertTrue(all(cagri.args == ('ai',) for cagri in casus.call_args_list))

    def test_cekim_sonunda_cache_tum_kayitlari_icerir(self):
        self._cek(25)
        self.assertEqual(len(cache.get('ai_entries')), 25)
        self.assertIsNotNone(cache.get('ai_last_update'))


@override_settings(CACHES=LOCMEM_CACHE)
class CacheYenileTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_liste_cache_en_yeni_100_kayitla_sinirlidir(self):
        """C5: bilincli sinir. Veritabanindaki fazlasi kayip degildir; v1 hepsini verir."""
        from news.cache_utils import CACHE_LISTE_SINIRI, cache_yenile
        for i in range(CACHE_LISTE_SINIRI + 5):
            AINewsEntry.objects.create(
                source='Test', original_title=f'Baslik {i}', original_description='X',
                link=f'https://ornek.test/sinir/{i}', published_date=date(2026, 9, 12))
        cache_yenile('ai')
        self.assertEqual(len(cache.get('ai_entries')), CACHE_LISTE_SINIRI)

    def test_bilinmeyen_bolum_reddedilir(self):
        from news.cache_utils import cache_yenile
        with self.assertRaises(KeyError):
            cache_yenile('olmayan')


class CacheSurumuTests(SimpleTestCase):

    def test_cache_anahtarlari_surumlu(self):
        """C3: serializer sekli degisince bu sayi artirilir; eski bloblar okunmaz."""
        self.assertEqual(settings.CACHES['default'].get('VERSION'), 2)


class V1CacheBagimsizligiTests(V1TestCase):
    """C2: v1 liste cache'ini okumaz. A1'de saglandi; bu test onu kilitler (ilk kosuda da gecer)."""

    def test_v1_cache_icerigini_kullanmaz(self):
        kayit = AINewsEntry.objects.create(
            source='Test', original_title='Gercek kayit', original_description='X',
            link='https://ornek.test/v1-cache', published_date=date(2026, 9, 12))
        cache.set('ai_entries', [{'id': 999999, 'sahte': True}], 3600)

        govde = self.client.get('/api/v1/ai/', **self.token_basligi()).json()

        self.assertEqual([k['id'] for k in govde['results']], [kayit.id])
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_cache -v 2 2>&1 | tail -25`
Expected: `FetchCacheYenilemeTests` ERROR (`news.tasks` icinde `cache_yenile` yok / `news.cache_utils` yok), `CacheYenileTests` ERROR, `CacheSurumuTests` FAIL (`None != 2`). `V1CacheBagimsizligiTests` gecer.

- [ ] **Step 3: `cache_utils.py`'yi yaz**

```python
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
```

- [ ] **Step 4: `tasks.py`'yi guncelle**

`news/tasks.py` dosyasini **tamamen** asagidakiyle degistir. Tek fark: her task'ta dongu icindeki dort satirlik cache yazimi `cache_yenile` cagrisina donustu ve cekim sonunda bir kez daha cagriliyor; artik kullanilmayan `datetime` ve serializer importlari kaldirildi. Diger her satir mevcut dosyayla aynidir.

```python
# Celery tasks
from celery import shared_task
from django.core.cache import cache
from datetime import timedelta, date

from .models import NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry
from .translation_utils import consume_translation_failures
from .cache_utils import CACHE_YENILEME_ARALIGI, cache_yenile

from scraper_multi import MultiSourceScraper
from .cve_scraper import MultiCVEScraper
from .k8s_scraper import MultiK8sScraper
from .sre_scraper import MultiSREScraper
from .devtools_scraper import MultiDevToolsScraper
from .ai_scraper import MultiAINewsScraper


def _drop_existing(entries, model, field, key='link'):
    """Veritabaninda zaten cevrilmis olan kayitlari listeden cikarir (tekrar cevrilmesin diye).
    Ceviri bekleyen (needs_translation) kayitlar listede kalir ve yeniden islenir.
    Ucretsiz Google Translate kotasini korumak icin kullanilir."""
    keys = [e.get(key) for e in entries if e.get(key)]
    existing = set(model.objects.filter(**{f'{field}__in': keys}, needs_translation=False)
                   .values_list(field, flat=True))
    return [e for e in entries if e.get(key) not in existing]


# Not: `needs_translation` degeri, generator kaydi cevirip yield ettikten sonra
# okunur; consume_translation_failures() sayaci her kayitta sifirlar.
#
# Cache: her CACHE_YENILEME_ARALIGI kayitta bir ve cekim sonunda yeniden kurulur
# (bkz. news/cache_utils.py).

@shared_task
def fetch_news_task(days=7, selected_sources=None, clear_existing=False, skip_existing=True):
    try:
        # Eski cache ve gun araliginin disindaki kayitlari temizle
        cache.delete('cybersecurity_news')
        cache.delete('last_update')
        cutoff = date.today() - timedelta(days=days)
        NewsArticle.objects.filter(date__lt=cutoff).delete()

        scraper = MultiSourceScraper()
        articles = scraper.fetch_all_news(days=days, selected_sources=selected_sources)
        if skip_existing:
            articles = _drop_existing(articles, NewsArticle, 'link')
        if articles:
            saved_count = 0
            consume_translation_failures()
            for article in scraper.process_news(articles):
                NewsArticle.objects.update_or_create(
                    link=article['link'],
                    defaults={
                        'source': article['source'],
                        'original_title': article['original_title'],
                        'turkish_title': article['turkish_title'],
                        'original_description': article.get('original_description', ''),
                        'turkish_description': article.get('turkish_description', ''),
                        'turkish_summary': article.get('turkish_summary', ''),
                        'date': article['date'],
                        'original_date': article.get('original_date', ''),
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('news')
            cache_yenile('news')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_cve_task(days=7, selected_sources=None, skip_existing=True):
    try:
        cache.delete('cve_entries')
        cache.delete('cve_last_update')
        cutoff = date.today() - timedelta(days=days)
        CVEEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiCVEScraper()
        cves = scraper.fetch_all_cves(days=days, selected_sources=selected_sources)
        if skip_existing:
            cves = _drop_existing(cves, CVEEntry, 'cve_id', key='cve_id')
        if cves:
            saved_count = 0
            consume_translation_failures()
            for cve in scraper.process_cves(cves):
                CVEEntry.objects.update_or_create(
                    cve_id=cve['cve_id'],
                    defaults={
                        'source': cve['source'],
                        'original_title': cve['original_title'],
                        'turkish_title': cve.get('turkish_title', ''),
                        'original_description': cve.get('original_description', ''),
                        'turkish_description': cve.get('turkish_description', ''),
                        'severity': cve.get('severity', 'Bilinmiyor'),
                        'cvss_score': cve.get('cvss_score'),
                        'published_date': cve.get('published_date'),
                        'modified_date': cve.get('modified_date'),
                        'link': cve.get('link', ''),
                        'cwe_ids': cve.get('cwe_ids', []),
                        'references': cve.get('references', []),
                        'affected_products': cve.get('affected_products', ''),
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('cve')
            cache_yenile('cve')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_k8s_task(days=30, selected_sources=None, skip_existing=True):
    try:
        cache.delete('k8s_entries')
        cache.delete('k8s_last_update')
        cutoff = date.today() - timedelta(days=days)
        KubernetesEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiK8sScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        if skip_existing:
            entries = _drop_existing(entries, KubernetesEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            for entry in scraper.process_entries(entries):
                KubernetesEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'category': entry.get('category', 'blog'),
                        'version': entry.get('version', ''),
                        'published_date': entry['published_date'],
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('kubernetes')
            cache_yenile('kubernetes')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_sre_task(days=30, selected_sources=None, skip_existing=True):
    try:
        cache.delete('sre_entries')
        cache.delete('sre_last_update')
        cutoff = date.today() - timedelta(days=days)
        SREEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiSREScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        if skip_existing:
            entries = _drop_existing(entries, SREEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            for entry in scraper.process_entries(entries):
                SREEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'published_date': entry['published_date'],
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('sre')
            cache_yenile('sre')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_devtools_task(days=30, selected_sources=None, skip_existing=True):
    try:
        cache.delete('devtools_entries')
        cache.delete('devtools_last_update')
        cutoff = date.today() - timedelta(days=days)
        DevToolsEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiDevToolsScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        if skip_existing:
            entries = _drop_existing(entries, DevToolsEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            for entry in scraper.process_entries(entries):
                DevToolsEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'version': entry.get('version', ''),
                        'entry_type': entry.get('entry_type', 'release'),
                        'published_date': entry['published_date'],
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('devtools')
            cache_yenile('devtools')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@shared_task
def fetch_ai_news_task(days=30, selected_sources=None, skip_existing=True):
    try:
        cache.delete('ai_entries')
        cache.delete('ai_last_update')
        cutoff = date.today() - timedelta(days=days)
        AINewsEntry.objects.filter(published_date__lt=cutoff).delete()

        scraper = MultiAINewsScraper()
        entries = scraper.fetch_all(days=days, selected_sources=selected_sources)
        if skip_existing:
            entries = _drop_existing(entries, AINewsEntry, 'link')
        if entries:
            saved_count = 0
            consume_translation_failures()
            for entry in scraper.process_entries(entries):
                AINewsEntry.objects.update_or_create(
                    link=entry['link'],
                    defaults={
                        'source': entry['source'],
                        'original_title': entry['original_title'],
                        'turkish_title': entry.get('turkish_title', ''),
                        'original_description': entry.get('original_description', ''),
                        'turkish_description': entry.get('turkish_description', ''),
                        'published_date': entry.get('published_date') or entry.get('date'),
                        'needs_translation': consume_translation_failures() > 0,
                    }
                )
                saved_count += 1
                if saved_count % CACHE_YENILEME_ARALIGI == 0:
                    cache_yenile('ai')
            cache_yenile('ai')
            return {'success': True, 'count': saved_count}
        return {'success': False, 'count': 0}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

**Yapistirmadan once** dosyanin plan yazildigindan beri degismedigini dogrula:

Run: `git log --format=%h -1 -- news/tasks.py`
Expected: `ae3180a`. Farkli bir hash cikarsa bu blogu yapistirma; yalnizca her task'taki dongu icindeki dort cache satirini `cache_yenile` cagrisina donustur ve importlari guncelle. (Planlama sirasinda blok mevcut dosyayla karsilastirildi; tek farklar importlar ve cache yorumu.)

- [ ] **Step 5: Cache surumunu ekle**

`cybernews/settings.py` — `CACHES` sozlugunde `"LOCATION"` satirinin hemen altina ekle:

```python
        # Cache blob sekli (serializer alanlari) degistiginde artirilir; eski
        # surumdeki bloblar okunmaz ve 1 saat icinde kendiliginden duser.
        # DRF throttle sayaclari da bu surume tabidir (artirinca bir kez sifirlanir).
        "VERSION": 2,
```

- [ ] **Step 6: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_cache -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 6 tests`, `OK`

- [ ] **Step 7: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 123 tests`, `OK`

- [ ] **Step 8: Commit**

```bash
git add news/cache_utils.py news/tasks.py news/tests/test_cache.py cybernews/settings.py
git commit -m "$(cat <<'MSG'
perf: fetch task'larinda cache'i her kayit yerine her 10 kayitta kur

Alti task liste cache'ini her kayittan sonra yeniden kuruyordu (adim
basina ~60 ms; 135 kayitlik AI cekiminde 8.2 sn, 275 kayitlik CVE
cekiminde ~17 sn). Artik her 10 kayitta bir ve cekim sonunda kuruluyor.
Tamamen sona birakilmadi: frontend listeyi 5 sn'de bir istiyor ve cekim
surerken yeni kayitlarin ekrana akmasina dayaniyor.

Cache kurma news/cache_utils.py'de tek yerde toplandi; 100 kayit siniri
bilincli bir sinir olarak belgelendi. CACHES VERSION=2 ile cache
anahtarlari surumlendi; views.py degismedi.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: `retranslate_pending` — bekleyen kayitlari feed'siz yeniden cevir

**Files:**
- Create: `news/retranslate.py`, `news/tests/test_retranslate.py`

**Interfaces:**
- Consumes: `translate_text`, `translate_long_text`, `consume_translation_failures`, `_get_gate` (`translation_utils`); `apply_cursor`, `decode_cursor`, `encode_cursor`, `InvalidCursor` (`api_v1/cursor.py`, A1); `cache_yenile` (Task 3); `MultiK8sScraper._translate_structured_changelog`
- Produces:
  - `RETRANSLATE_BATCH: int` (env, varsayilan 8, bolum basina)
  - `BOLUMLER: tuple[(ad, model, cevirici), ...]`
  - `retranslate_pending(redis_client=None, prefix='retranslate', batch=None) -> dict` — donus: `{'translated': int, 'failed': int, 'stopped_by_cooldown': bool, 'sections': {ad: {'translated': int, 'failed': int}}}`
  - Redis anahtari: `{prefix}:cursor:{bolum}` — o bolumde son denenen kaydin deneme oncesi `(updated_at, id)` imleci

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_retranslate.py`:

```python
"""Retranslate testleri (spec 9.3, A3 plani netlestirme 8-10, 14).

Google sahte, Redis gercek (benzersiz onek), veritabani gercek. Hicbir Celery
isi kuyruga atilmaz; fonksiyon dogrudan cagrilir.
"""
import uuid
from datetime import date
from io import StringIO
from unittest import mock

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from news import translation_utils as tu
from news.models import AINewsEntry, CVEEntry, KubernetesEntry
from news.tests.base import LOCMEM_CACHE, test_redis_client
from news.tests.test_translation import FakeTranslator, TranslationGateMixin

CEVIRILER = {
    'Farmers adopt new sensors': 'Çiftçiler yeni sensörler benimsiyor',
    'Sensors measure soil moisture every hour.': 'Sensörler toprak nemini her saat ölçüyor.',
    'A remote attacker can read arbitrary files from the server.':
        'Uzaktaki bir saldırgan sunucudaki rastgele dosyaları okuyabilir.',
}
for _i in range(1, 6):
    CEVIRILER[f'Story number {_i} published'] = f'{_i} numaralı haber yayımlandı'
    CEVIRILER[f'Body text for story {_i}.'] = f'{_i}. haberin gövde metni.'

# Hep yanki donen (dogrulamadan gecemeyen) kayit
TAKILAN_BASLIK = 'Robots learn to sort laundry today'
TAKILAN_GOVDE = 'The team trained robots for many months.'


@override_settings(CACHES=LOCMEM_CACHE)
class RetranslateTestBase(TranslationGateMixin, TestCase):

    def setUp(self):
        super().setUp()
        cache.clear()
        self.redis = test_redis_client()
        self.prefix = f'test-retranslate-{uuid.uuid4().hex}'
        self.addCleanup(self._anahtarlari_sil)

    def _anahtarlari_sil(self):
        for anahtar in self.redis.scan_iter(f'{self.prefix}:*'):
            self.redis.delete(anahtar)

    def _calistir(self, batch=8):
        from news.retranslate import retranslate_pending
        return retranslate_pending(redis_client=self.redis, prefix=self.prefix, batch=batch)

    def _ai(self, baslik, govde, slug):
        return AINewsEntry.objects.create(
            source='MIT Tech Review AI', original_title=baslik, turkish_title=baslik,
            original_description=govde, turkish_description=govde,
            link=f'https://ornek.test/rt/{slug}', published_date=date(2026, 9, 12),
            needs_translation=True)


class RetranslatePendingTests(RetranslateTestBase):

    def test_bekleyen_kayit_feede_bakmadan_cevrilir(self):
        cevirmen = self.use_translator(FakeTranslator(CEVIRILER))
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'ciftci')
        once = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertFalse(kayit.needs_translation)
        self.assertEqual(kayit.turkish_title, 'Çiftçiler yeni sensörler benimsiyor')
        self.assertEqual(kayit.turkish_description, 'Sensörler toprak nemini her saat ölçüyor.')
        self.assertGreater(kayit.updated_at, once, 'Basarida updated_at ilerlemeli: delta akisina dusmeli')
        self.assertEqual(sonuc['translated'], 1)
        self.assertEqual(sonuc['sections']['ai'], {'translated': 1, 'failed': 0})
        self.assertEqual(len(cevirmen.calls), 2)

    def test_erisim_hatasinda_kayda_yazilmaz_ve_durur(self):
        self.use_translator(FakeTranslator())  # hata sayfasi -> devre kesici acilir
        kayit = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'erisim')
        once = kayit.updated_at

        sonuc = self._calistir()

        kayit.refresh_from_db()
        self.assertTrue(kayit.needs_translation)
        self.assertEqual(kayit.updated_at, once, 'Basarisiz deneme delta akisina degismemis kayit dusurmemeli')
        self.assertTrue(sonuc['stopped_by_cooldown'])
        self.assertEqual(sonuc['translated'], 0)
        self.assertFalse(self.redis.exists(f'{self.prefix}:cursor:ai'),
                         'Erisim hatasinda imlec ilerlememeli; kayit bir sonraki turda once denenmeli')

    def test_devre_kesici_acikken_googlea_gidilmez(self):
        cevirmen = self.use_translator(FakeTranslator(CEVIRILER))
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'kesici')
        tu._gate.start_cooldown(60)

        sonuc = self._calistir()

        self.assertEqual(cevirmen.calls, [])
        self.assertTrue(sonuc['stopped_by_cooldown'])

    def test_bolum_basina_batch_siniri(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        for i in range(1, 6):
            self._ai(f'Story number {i} published', f'Body text for story {i}.', f'batch-{i}')

        sonuc = self._calistir(batch=2)

        self.assertEqual(sonuc['translated'], 2)
        self.assertEqual(AINewsEntry.objects.filter(needs_translation=True).count(), 3)

    def test_hep_basarisiz_kayit_kuyrugu_tikamaz(self):
        """En-eski-once siralamada takilan kayit her turda ayni yeri isgal ederdi."""
        cevirmen = self.use_translator(FakeTranslator({
            **CEVIRILER, TAKILAN_BASLIK: TAKILAN_BASLIK, TAKILAN_GOVDE: TAKILAN_GOVDE}))
        takilan = self._ai(TAKILAN_BASLIK, TAKILAN_GOVDE, 'takilan')
        birinci = self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'birinci')
        ikinci = self._ai('Story number 2 published', 'Body text for story 2.', 'ikinci')

        for _ in range(3):
            self._calistir(batch=1)

        for kayit in (takilan, birinci, ikinci):
            kayit.refresh_from_db()
        self.assertTrue(takilan.needs_translation)
        self.assertFalse(birinci.needs_translation)
        self.assertFalse(ikinci.needs_translation)
        self.assertFalse(tu._gate.cooldown_active(), 'Yanki devre kesiciyi acmamali')

    def test_sona_gelince_imlec_silinir_ve_bastan_baslar(self):
        cevirmen = self.use_translator(FakeTranslator({
            TAKILAN_BASLIK: TAKILAN_BASLIK, TAKILAN_GOVDE: TAKILAN_GOVDE}))
        self._ai(TAKILAN_BASLIK, TAKILAN_GOVDE, 'tek')

        self._calistir(batch=1)                     # takilan denendi, imlec onun uzerinde
        self.assertTrue(self.redis.exists(f'{self.prefix}:cursor:ai'))
        self._calistir(batch=1)                     # imlecten sonra kayit yok -> imlec silinir
        self.assertFalse(self.redis.exists(f'{self.prefix}:cursor:ai'))
        cagri_sayisi = len(cevirmen.calls)
        self._calistir(batch=1)                     # bastan: takilan tekrar denenir
        self.assertGreater(len(cevirmen.calls), cagri_sayisi)

    def test_bozuk_imlec_yok_sayilip_bastan_baslanir(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'bozuk-imlec')
        self.redis.set(f'{self.prefix}:cursor:ai', 'bozuk!!')

        sonuc = self._calistir()

        self.assertEqual(sonuc['translated'], 1)

    def test_basarida_liste_cache_yenilenir(self):
        self.use_translator(FakeTranslator(CEVIRILER))
        self._ai('Farmers adopt new sensors', 'Sensors measure soil moisture every hour.', 'cache')

        self._calistir()

        self.assertEqual(cache.get('ai_entries')[0]['turkish_title'], 'Çiftçiler yeni sensörler benimsiyor')

    def test_bekleyen_kayit_yoksa_googlea_gidilmez(self):
        cevirmen = self.use_translator(FakeTranslator(CEVIRILER))
        sonuc = self._calistir()
        self.assertEqual(cevirmen.calls, [])
        self.assertEqual(sonuc['translated'], 0)
        self.assertFalse(sonuc['stopped_by_cooldown'])

    def test_cve_basligi_cevrilmez_kisa_olmayan_aciklama_cevrilir(self):
        """cve_scraper.process_cves ile ayni kural."""
        cevirmen = self.use_translator(FakeTranslator(CEVIRILER))
        cve = CVEEntry.objects.create(
            cve_id='CVE-2026-5000', source='NVD', original_title='CVE-2026-5000 - Guvenlik Acigi',
            original_description='A remote attacker can read arbitrary files from the server.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/5000', needs_translation=True)

        self._calistir()

        cve.refresh_from_db()
        self.assertFalse(cve.needs_translation)
        self.assertEqual(cve.turkish_title, 'CVE-2026-5000 - Guvenlik Acigi')
        self.assertEqual(cve.turkish_description, 'Uzaktaki bir saldırgan sunucudaki rastgele dosyaları okuyabilir.')
        self.assertEqual(len(cevirmen.calls), 1)

    def test_kubernetes_yapisal_changelog_ozel_yoldan_cevrilir(self):
        """k8s_scraper.process_entries ile ayni ayrim."""
        baslik = 'Kubernetes v1.32 released'
        korunmus_baslik, _ = tu._protect_terms(baslik)
        self.use_translator(FakeTranslator({korunmus_baslik: korunmus_baslik.replace('released', 'yayımlandı')}))
        k8s = KubernetesEntry.objects.create(
            source='GitHub Releases', original_title=baslik,
            original_description='===SECTION: Feature\n---ITEM---\nAdds a flag.',
            link='https://ornek.test/k8s/132', published_date=date(2026, 9, 12),
            category='release', needs_translation=True)

        from news.k8s_scraper import MultiK8sScraper
        with mock.patch.object(MultiK8sScraper, '_translate_structured_changelog',
                               return_value='YAPISAL CEVIRI') as yapisal:
            self._calistir()

        k8s.refresh_from_db()
        yapisal.assert_called_once()
        self.assertEqual(k8s.turkish_description, 'YAPISAL CEVIRI')
        self.assertEqual(k8s.turkish_title, 'Kubernetes v1.32 yayımlandı')
        self.assertFalse(k8s.needs_translation)
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate -v 2 2>&1 | tail -20`
Expected: ERROR — `ModuleNotFoundError: No module named 'news.retranslate'`

- [ ] **Step 3: `retranslate.py`'yi yaz**

```python
"""Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir (spec 9.3, H2).

Neden gerekli: fetch task'lari ceviri bekleyen bir kaydi yalnizca kaynak feed onu
hala donduruyorsa yeniden isler. Feed penceresinden cikan kayit bir daha hic
cevrilmezdi.

Siralama (A3 plani netlestirme 8): her bolum icin Redis'te bir imlec tutulur
({prefix}:cursor:{bolum}). Her tur imlecten sonraki RETRANSLATE_BATCH bekleyen
kaydi dener. Icerik yuzunden cevrilemeyen kayit sirada kalir ama imlec onu gecer;
boylece hep basarisiz olan birkac kayit kuyrugun onunu kalici olarak tikamaz.
Sona gelinince imlec silinir, bir sonraki tur bastan baslar.

Yazma kurallari:
  - Basarisiz denemede kayda yazilmaz: updated_at ilerlemez, tuketicinin delta
    akisina degismemis kayit dusmez.
  - Basarida Turkce alanlar yazilir, bayrak duser, updated_at ilerler; Turkce
    metin delta akisindan tuketiciye kendiliginden gider.
  - Devre kesici acikken Google'a hic gidilmez; erisim hatasinda imlec o kaydi
    gecmez, bir sonraki tur once onu dener.
"""
import os
from typing import Dict

from . import translation_utils as tu
from .api_v1.cursor import InvalidCursor, apply_cursor, decode_cursor, encode_cursor
from .cache_utils import cache_yenile
from .models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

# Bolum basina; alti bolumle tur basina en fazla 48 kayit.
RETRANSLATE_BATCH = int(os.environ.get('RETRANSLATE_BATCH', '8'))


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


def retranslate_pending(redis_client=None, prefix: str = 'retranslate', batch: int = None) -> Dict:
    redis_client = redis_client or _canli_redis()
    batch = RETRANSLATE_BATCH if batch is None else batch
    kapi = tu._get_gate()
    sonuc = {'translated': 0, 'failed': 0, 'stopped_by_cooldown': False, 'sections': {}}

    for ad, model, cevir in BOLUMLER:
        if kapi.cooldown_active():
            sonuc['stopped_by_cooldown'] = True
            break

        imlec_anahtari = f'{prefix}:cursor:{ad}'
        sorgu = model.objects.filter(needs_translation=True).order_by('updated_at', 'id')
        ham_imlec = redis_client.get(imlec_anahtari)
        if ham_imlec:
            try:
                sorgu = apply_cursor(sorgu, *decode_cursor(ham_imlec.decode('utf-8')))
            except InvalidCursor:
                redis_client.delete(imlec_anahtari)
        kayitlar = list(sorgu[:batch])

        cevrilen = basarisiz = 0
        yarida_kaldi = False
        for kayit in kayitlar:
            if kapi.cooldown_active():
                yarida_kaldi = True
                break

            deneme_oncesi = encode_cursor(kayit.updated_at, kayit.id)
            tu.consume_translation_failures()
            alanlar = cevir(kayit)

            if tu.consume_translation_failures() > 0:
                if kapi.cooldown_active():
                    # Erisim hatasi: imleci ilerletme, bir sonraki tur once bu kaydi denesin
                    yarida_kaldi = True
                    break
                basarisiz += 1  # icerik hatasi (dogrulama): imlec gecer, kayit sirada kalir
            else:
                for alan, deger in alanlar.items():
                    setattr(kayit, alan, deger)
                kayit.needs_translation = False
                kayit.save(update_fields=[*alanlar, 'needs_translation', 'updated_at'])
                cevrilen += 1
            redis_client.set(imlec_anahtari, deneme_oncesi)

        if yarida_kaldi:
            sonuc['stopped_by_cooldown'] = True
        elif len(kayitlar) < batch:
            redis_client.delete(imlec_anahtari)  # sona gelindi; bir sonraki tur bastan

        if cevrilen:
            cache_yenile(ad)
        sonuc['sections'][ad] = {'translated': cevrilen, 'failed': basarisiz}
        sonuc['translated'] += cevrilen
        sonuc['failed'] += basarisiz

        if yarida_kaldi:
            break

    return sonuc
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 11 tests`, `OK`

- [ ] **Step 5: Test anahtarlarinin kalmadigini dogrula**

Run: `docker compose exec -T teknoloji-redis redis-cli --scan --pattern 'test-retranslate-*' | wc -l`
Expected: `0`

- [ ] **Step 6: Commit**

```bash
git add news/retranslate.py news/tests/test_retranslate.py
git commit -m "$(cat <<'MSG'
feat: ceviri bekleyen kayitlari feed'e bakmadan yeniden cevir

Fetch task'lari bekleyen kaydi yalnizca kaynak feed onu hala
donduruyorsa yeniden isliyordu; feed penceresinden cikan kayit bir daha
hic cevrilmiyordu.

retranslate_pending bolum basina Redis imleciyle calisiyor: her tur
imlecten sonraki RETRANSLATE_BATCH kaydi dener, icerik yuzunden
cevrilemeyen kaydi gecer, sona gelince bastan baslar. Boylece hep
basarisiz olan kayitlar kuyrugu tikamiyor; migration gerekmiyor (A1
imlec kodu yeniden kullaniliyor).

Basarisiz denemede kayda yazilmiyor (updated_at ilerlemez, delta
akisina gurultu dusmez). Devre kesici acikken Google'a gidilmiyor;
erisim hatasinda imlec o kaydi gecmiyor. Her bolum scraper'daki
ceviri kuralini aynen izliyor (CVE basligi cevrilmez, K8s yapisal
changelog ozel yoldan).

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: Celery gorevi ve Beat takvimi

**Files:**
- Modify: `news/tasks.py`, `cybernews/settings.py`
- Modify: `news/tests/test_retranslate.py`

**Interfaces:**
- Consumes: `retranslate_pending` (Task 4)
- Produces: `news.tasks.retranslate_pending_task` (argumansiz); Beat girdisi `'retranslate-pending-every-2h'` → `crontab(minute=5, hour='1-23/2')`

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_retranslate.py` sonuna ekle:

```python
class RetranslateGoreviTests(SimpleTestCase):

    def test_gorev_retranslate_pending_cagirir(self):
        from news import tasks
        with mock.patch('news.retranslate.retranslate_pending',
                        return_value={'translated': 3}) as sahte:
            self.assertEqual(tasks.retranslate_pending_task(), {'translated': 3})
        sahte.assert_called_once_with()

    def test_beat_takvimi_tek_saatlerde_bes_gece(self):
        giris = settings.CELERY_BEAT_SCHEDULE['retranslate-pending-every-2h']
        self.assertEqual(giris['task'], 'news.tasks.retranslate_pending_task')
        self.assertEqual(giris['schedule'].minute, {5})
        self.assertEqual(giris['schedule'].hour, set(range(1, 24, 2)))

    def test_cekim_saatleriyle_cakismaz(self):
        """Fetch task'lari 00/06/12/18'de calisir; retranslate o saatlere dusmemeli."""
        cekim_saatleri = set()
        for giris in settings.CELERY_BEAT_SCHEDULE.values():
            if giris['task'].startswith('news.tasks.fetch_'):
                cekim_saatleri |= giris['schedule'].hour
        self.assertEqual(cekim_saatleri, {0, 6, 12, 18})
        retranslate_saatleri = settings.CELERY_BEAT_SCHEDULE['retranslate-pending-every-2h']['schedule'].hour
        self.assertEqual(cekim_saatleri & retranslate_saatleri, set())
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate.RetranslateGoreviTests -v 2 2>&1 | tail -15`
Expected: ERROR/FAIL — `news.tasks` icinde `retranslate_pending_task` yok, `KeyError: 'retranslate-pending-every-2h'`

- [ ] **Step 3: Gorevi ve takvimi ekle**

`news/tasks.py` sonuna ekle:

```python


@shared_task
def retranslate_pending_task():
    """Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir (bkz. news/retranslate.py)."""
    from .retranslate import retranslate_pending
    return retranslate_pending()
```

`cybernews/settings.py` — `CELERY_BEAT_SCHEDULE` sozlugunun sonuna (son fetch girdisinden sonra) ekle:

```python
    # Ceviri bekleyen kayitlari feed'e bakmadan yeniden cevirir. Tek saatlerde
    # calisir: fetch task'lari 00/06/12/18'de calistigi icin hic cakismaz.
    'retranslate-pending-every-2h': {
        'task': 'news.tasks.retranslate_pending_task',
        'schedule': crontab(minute=5, hour='1-23/2'),
    },
```

Sozlugun ustundeki yorum blogunu da guncelle: `# Celery Beat — tum bolumler 6 saatte bir otomatik cekilir.` satirinin altina `# Ceviri bekleyen kayitlar 2 saatte bir (tek saatlerde) yeniden cevrilir.` ekle.

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 14 tests`, `OK`

- [ ] **Step 5: Commit**

```bash
git add news/tasks.py cybernews/settings.py news/tests/test_retranslate.py
git commit -m "$(cat <<'MSG'
feat: retranslate_pending_task ve 2 saatlik Beat takvimi

Gorev tek saatlerde (01:05, 03:05, ...) calisiyor. Spec */2 diyordu;
bu 00/06/12/18'i de kapsar ve o saatlerde alti fetch task'i calisir.
Tek saatler hicbir fetch slotuyla cakismiyor.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: Mevcut bozuk cevirileri isaretleme komutu

**Files:**
- Create: `news/management/__init__.py`, `news/management/commands/__init__.py`, `news/management/commands/bozuk_cevirileri_isaretle.py`
- Modify: `news/tests/test_retranslate.py`

**Interfaces:**
- Consumes: modeller
- Produces: `python manage.py bozuk_cevirileri_isaretle [--uygula]`. Varsayilan yalnizca rapor. `--uygula` ile `needs_translation=False` olup Turkce alanlarinda (bozuk bicimler dahil) `XTRM` kalintisi olan kayitlar `needs_translation=True` yapilir; `updated_at` degismez. Cikti son satiri `TOPLAM: <n>`.

- [ ] **Step 1: Basarisiz testi yaz**

`news/tests/test_retranslate.py` sonuna ekle:

```python
class BozukCevirileriIsaretleTests(TestCase):

    def setUp(self):
        self.bozuk = CVEEntry.objects.create(
            cve_id='CVE-2026-7001', source='NVD', original_title='CVE-2026-7001',
            original_description='Uses `secret()` in code.', turkish_description='XTRM0021X kullanır.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/7001')
        self.bosluklu = AINewsEntry.objects.create(
            source='Test', original_title='T', turkish_title='xtrm 0003x modeli',
            original_description='D', turkish_description='Gövde',
            link='https://ornek.test/ai/7002', published_date=date(2026, 9, 12))
        self.temiz = CVEEntry.objects.create(
            cve_id='CVE-2026-7003', source='NVD', original_title='CVE-2026-7003',
            original_description='Clean.', turkish_description='Temiz çeviri.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/7003')
        self.zaten_bekleyen = CVEEntry.objects.create(
            cve_id='CVE-2026-7004', source='NVD', original_title='CVE-2026-7004',
            original_description='Pending.', turkish_description='XTRM0001X bekliyor.',
            published_date=date(2026, 9, 12), link='https://ornek.test/cve/7004', needs_translation=True)

    def _komut(self, *args):
        cikti = StringIO()
        call_command('bozuk_cevirileri_isaretle', *args, stdout=cikti)
        return cikti.getvalue()

    def test_varsayilan_yalnizca_raporlar(self):
        cikti = self._komut()
        self.assertIn('TOPLAM: 2', cikti)
        self.bozuk.refresh_from_db()
        self.assertFalse(self.bozuk.needs_translation)

    def test_uygula_yalnizca_bozuklari_isaretler(self):
        once = CVEEntry.objects.get(pk=self.bozuk.pk).updated_at

        cikti = self._komut('--uygula')

        self.assertIn('TOPLAM: 2', cikti)
        for kayit in (self.bozuk, self.bosluklu, self.temiz):
            kayit.refresh_from_db()
        self.assertTrue(self.bozuk.needs_translation)
        self.assertTrue(self.bosluklu.needs_translation, 'Bosluklu/kucuk harfli kalinti da bozuktur')
        self.assertFalse(self.temiz.needs_translation)
        self.assertEqual(self.bozuk.updated_at, once,
                         'Isaretleme updated_at ilerletmemeli; duzgun ceviri yazilinca ilerleyecek')

    def test_ikinci_calistirmada_bulunacak_bir_sey_kalmaz(self):
        self._komut('--uygula')
        self.assertIn('TOPLAM: 0', self._komut())
```

- [ ] **Step 2: Testin dustugunu dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate.BozukCevirileriIsaretleTests -v 2 2>&1 | tail -15`
Expected: ERROR — `CommandError: Unknown command: 'bozuk_cevirileri_isaretle'`

- [ ] **Step 3: Komutu yaz**

```bash
mkdir -p news/management/commands
printf '' > news/management/__init__.py
printf '' > news/management/commands/__init__.py
```

`news/management/commands/bozuk_cevirileri_isaretle.py`:

```python
"""Turkce metninde yer tutucu kalintisi olan ama 'cevrildi' gorunen kayitlari bulur.

2026-09-12'de iki hata (ic ice yer tutucunun geri konmamasi ve bozuk yer
tutucunun geri koymadan sonra onarilmasi) 19 CVE kaydinda ham XTRM kodu birakti.
Hatalar A3 Task 1'de duzeltildi; bu komut mevcut bozuk kayitlari
needs_translation=True yapar ki retranslate_pending_task onlari yeniden cevirsin.

Isaretleme updated_at'i ilerletmez (QuerySet.update): tuketiciye yeni bir sey
gitmez. Duzgun ceviri yazildiginda updated_at ilerler ve delta akisindan gider.
"""
import re

from django.core.management.base import BaseCommand

from news.models import (
    AINewsEntry, CVEEntry, DevToolsEntry, KubernetesEntry, NewsArticle, SREEntry,
)

# Bozuk bicimler dahil: 'XTRM0021X', 'xtrm 0003x', 'X TRM0001 X'
KALINTI = re.compile(r'[Xx]\s*[Tt]\s*[Rr]\s*[Mm]\s*\d{4}\s*[Xx]')
MODELLER = (NewsArticle, CVEEntry, KubernetesEntry, SREEntry, DevToolsEntry, AINewsEntry)
TURKCE_ALANLAR = ('turkish_title', 'turkish_description', 'turkish_summary')


class Command(BaseCommand):
    help = ("Turkce metninde XTRM yer tutucu kalintisi olan, cevrildi gorunen kayitlari "
            "bulur. Varsayilan olarak yalnizca raporlar; isaretlemek icin --uygula.")

    def add_arguments(self, parser):
        parser.add_argument('--uygula', action='store_true',
                            help='Bulunan kayitlari needs_translation=True yap.')

    def handle(self, *args, **options):
        toplam = 0
        for model in MODELLER:
            model_alanlari = {alan.name for alan in model._meta.get_fields()}
            alanlar = [alan for alan in TURKCE_ALANLAR if alan in model_alanlari]
            kimlikler = [
                kayit.pk
                for kayit in model.objects.filter(needs_translation=False).only('id', *alanlar).iterator()
                if any(KALINTI.search(getattr(kayit, alan) or '') for alan in alanlar)
            ]
            if options['uygula'] and kimlikler:
                model.objects.filter(pk__in=kimlikler).update(needs_translation=True)
            toplam += len(kimlikler)
            self.stdout.write(f'{model.__name__}: {len(kimlikler)}')

        if not options['uygula']:
            self.stdout.write('(yalnizca rapor; isaretlemek icin --uygula)')
        self.stdout.write(f'TOPLAM: {toplam}')
```

- [ ] **Step 4: Testin gectigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py test news.tests.test_retranslate -v 2 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 17 tests`, `OK`

- [ ] **Step 5: Tum testleri kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `Ran 140 tests`, `OK`

- [ ] **Step 6: Commit**

```bash
git add news/management/ news/tests/test_retranslate.py
git commit -m "$(cat <<'MSG'
feat: bozuk cevirileri isaretleme komutu

Task 1'deki duzeltme yeni cevirileri koruyor, ama mevcut 19 CVE kaydi
needs_translation=False oldugu icin retranslate onlari hic almiyordu.
bozuk_cevirileri_isaretle, Turkce alanlarinda (bozuk bicimler dahil)
XTRM kalintisi olan kayitlari bulur; --uygula ile yeniden ceviri icin
isaretler. Isaretleme updated_at'i ilerletmez.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
MSG
)"
```

---

### Task 7: Canli dogrulama ve A3 kapanisi

Kod yazmaz, kanit toplar. **Canli veriyi degistirir** (bozuk kayitlari isaretler) ve **ucretsiz Google ucuna gercek istek atabilir** (retranslate). Task 7'ye baslamadan once kullaniciya haber ver.

**Files:** degistirilmez

- [ ] **Step 1: Calisan is olmadigini dogrula**

Run: `docker compose exec -T teknoloji-worker celery -A cybernews inspect active 2>&1 | tail -5`
Expected: `- empty -`. Bos degilse bitmesini bekle.

- [ ] **Step 2: Surecleri yeni kodla yeniden baslat**

```bash
docker compose restart teknoloji-api teknoloji-worker teknoloji-scheduler
```

Run: `docker compose logs --since 1m teknoloji-worker 2>&1 | grep -E "ready|ERROR" | tail -3`
Expected: `celery@... ready.`; `ERROR` yok.

- [ ] **Step 3: Worker'in yeni gorevi tanidigini dogrula**

Run: `docker compose exec -T teknoloji-worker celery -A cybernews inspect registered 2>&1 | grep -c retranslate_pending_task`
Expected: `1` veya daha fazla.

- [ ] **Step 4: Bozuk cevirileri raporla, sonra isaretle**

```bash
docker compose exec -T teknoloji-api python manage.py bozuk_cevirileri_isaretle
docker compose exec -T teknoloji-api python manage.py bozuk_cevirileri_isaretle --uygula
docker compose exec -T teknoloji-api python manage.py bozuk_cevirileri_isaretle
```

Expected: ilk iki calistirmada `CVEEntry` satiri **19 veya daha az** (CVE'ler 7 gunluk pencereden cikinca siliniyor), `TOPLAM` ayni sayi; ucuncu calistirmada `TOPLAM: 0`.

- [ ] **Step 5: Devre kesici durumunu kaydet**

Run: `docker compose exec -T teknoloji-redis redis-cli pttl translate:cooldown`
Beklenen iki durum: `-2` (kapali, Google denenebilir) veya pozitif milisaniye (acik). Degeri not et; Step 6'nin yorumunu belirler.

- [ ] **Step 6: Retranslate'i calisan worker'da bir kez calistir**

```bash
docker compose exec -T teknoloji-api python - <<'PY'
import os, time, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cybernews.settings')
django.setup()
from news.models import CVEEntry, AINewsEntry
from news.tasks import retranslate_pending_task
once = {m.__name__: m.objects.filter(needs_translation=True).count() for m in (CVEEntry, AINewsEntry)}
is_ = retranslate_pending_task.delay()
t = time.time()
sonuc = is_.get(timeout=1500)
print(f'sure: {time.time() - t:.0f} sn')
print('sonuc:', sonuc)
print('bekleyen once :', once)
print('bekleyen sonra:', {m.__name__: m.objects.filter(needs_translation=True).count() for m in (CVEEntry, AINewsEntry)})
PY
```

Expected — iki kabul edilebilir sonuc:
- **Devre kesici aciksa:** birkac saniyede biter, `stopped_by_cooldown: True`, `translated: 0`. Worker logunda bu is icin `[Ceviri]` satiri **olmamali** (Step 7).
- **Kapaliysa:** `translated` > 0 olabilir; bekleyen sayilari azalir. Google kisitlarsa is yarida `stopped_by_cooldown: True` ile durur — bu da dogru davranistir.

Her iki durumda da `sonuc` icinde bir istisna veya `error` olmamali.

- [ ] **Step 7: Loglarda dogrulama ve devre kesici davranisini gor**

```bash
docker compose logs --since 30m teknoloji-worker 2>&1 | grep -E "retranslate_pending_task|\[Ceviri\]" | tail -15
```

Expected: gorevin `received` ve `succeeded` satirlari. `[Ceviri] Dogrulama basarisiz (...)` satirlari gorulebilir — beklenen davranistir, dogrulamanin canlida calistigini gosterir. Devre kesici aciksa `[Ceviri]` satiri olmamali.

- [ ] **Step 8: "Cevrildi" gorunen kayitlarda kalinti kalmadigini dogrula**

Run: `docker compose exec -T teknoloji-api python manage.py bozuk_cevirileri_isaretle | tail -1`
Expected: `TOPLAM: 0`

- [ ] **Step 9: Cache surumunun canlida gectigini dogrula**

```bash
curl -s -o /dev/null -w "eski /api/ai/ -> %{http_code}\n" http://localhost:8000/api/ai/
docker compose exec -T teknoloji-redis redis-cli --scan --pattern ':2:ai_entries'
```

Expected: `200` ve `:2:ai_entries` satiri.

- [ ] **Step 10: Frontend ve v1'in bozulmadigini dogrula**

```bash
TOKEN=$(docker compose exec -T teknoloji-api python -c "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','cybernews.settings');django.setup();from rest_framework.authtoken.models import Token;print(Token.objects.get(user__username='entegrasyon').key)" | tr -d '\r')
curl -s -o /dev/null -w "v1 ai   -> %{http_code}\n" -H "Authorization: Token $TOKEN" http://localhost:8000/api/v1/ai/
curl -s -o /dev/null -w "frontend -> %{http_code}\n" http://localhost:3000/
```

Expected: ikisi de `200`.

- [ ] **Step 11: Tum test paketini son kez kos**

Run: `docker compose exec -T teknoloji-api python manage.py test news 2>&1 | grep -E "^(Ran|OK|FAILED)"`
Expected: `OK`

- [ ] **Step 12: Dali push et**

```bash
git push -u origin feat/entegrasyon-api-v1-a3
```

---

## A3 Bitis Kriterleri

- [ ] Ic ice ve bozuk donen yer tutucular eksiksiz geri konuyor; kimlik cevirisinde bozulan CVE aciklamasi 0 (Task 1 Step 6)
- [ ] Yanki, kirpilma, eksik yer tutucu ve kalinti "cevrildi" sayilmiyor; bu durumlar yeniden deneme ve devre kesici tetiklemiyor
- [ ] Ceviri bekleyen kayitlar feed'siz, sirali ve takilmadan yeniden cevriliyor; Beat tek saatlerde calistiriyor
- [ ] Mevcut bozuk ceviriler isaretlendi; "cevrildi" gorunen kayitlarda kalinti yok (Task 7 Step 8)
- [ ] Fetch task'lari cache'i her 10 kayitta bir ve sonda kuruyor; cache anahtarlari surum 2
- [ ] Hicbir test Google'a gitmedi, is kuyruga atmadi, canli Redis'te anahtar birakmadi
- [ ] Frontend, `/api/*` ve `/api/v1/*` calisiyor; test paketi yesil

## A3 Sonrasi

- **A4:** `FetchRun` modeli, `GET /api/v1/status/`, `health` ayrintisi, admin duzeltmeleri (spec bolum 11). A4 migration icerir — **migration sonrasi api/worker/scheduler yeniden baslatma adimi planda acikca yer almalidir.**
- **A5'e not:** README'ye `TRANSLATE_MIN_RATIO`, `RETRANSLATE_BATCH`, Beat'teki yeni gorev ve `bozuk_cevirileri_isaretle` komutu eklenecek; spec 9.2 (yer tutucu formati) ve 9.3 (siralama, batch, saat) bu plandaki netlestirmelere gore guncellenecek.
- **Kapsam disi gozlem:** `turkish_post_process` cumle basini buyuttugu icin `kubectl` gibi kucuk harfle baslayan komutlar `Kubectl` olarak yaziliyor. A3'te dokunulmadi.
