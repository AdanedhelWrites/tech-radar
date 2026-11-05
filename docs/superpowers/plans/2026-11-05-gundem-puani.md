# Gundem Puani — Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ana sayfa Gundem kartini, bes bolumden (CVE haric) ayni olayi yazan farkli kaynak sayisina gore puanlanmis buyuk olaylarla doldurmak.

**Architecture:**
- **Saf fonksiyonlar:** `news/gundem.py` icinde, veritabanina dokunmadan olay gruplama (orijinal baslik ozel adlari + benzerlik, union-find) ve puan.
- **Uc:** `views.get_gundem`, 72 saatlik kayitlari bes modelden okur, `gundem.olaylari_sec` ile 6 oge secer ve 120 sn onbellekler.
- **Frontend:** `Gundem.jsx` "N kaynak" rozetini gosterir; `GenelBakis.jsx` bes liste ucu yerine `/api/gundem/` cagirir.

**Tech Stack:** Django 5.2 + DRF, Python stdlib (`re`, `math`); React 18 + Vitest. Yeni bagimlilik yok.

**Spec:** `docs/superpowers/specs/2026-11-05-gundem-puani-design.md` — once onu oku (§2 G1–G5, §5 kabul ornekleri, §7 netlesenler).

## Global Constraints

- **Bolumler:** `news` (NewsArticle, tarih alani `date`), `kubernetes`, `sre`, `devtools`, `ai` (tarih alani `published_date`). CVE Gundem'e girmez.
- **Pencere:** `created_at` son 72 saat VE yayin tarihi `simdi`'nin yerel tarihinden en fazla 4 takvim gunu once. Yayin tarihi bossa yalniz `created_at` yeter.
- **Puan:** `puan = (farkli_kaynak + 0.5*(makale_sayisi - farkli_kaynak) + etki) * 0.5 ** (yas_saat / 24)`.
  - `etki` = 1.5 eger olayin herhangi bir orijinal basliginda etki sozcugu varsa, degilse 0.
  - `yas_saat` = `simdi` − olaydaki en yeni `created_at`.
- **Kaynak karsilastirmasi:** `source.strip().casefold()`.
- **Secim:** 6 oge.
  - Once `farkli_kaynak >= 2` olaylar `puan` azalan sirada; esitlikte `son` azalan, sonra temsilci `(bolum, id)`.
  - Kalan yerler tek kaynakli en yeni kayitlarla dolar (`created_at` azalan, sonra `id`).
- **Temsilci kayit:**
  - Ceviri sirasi: gemini > openrouter = deepl > google > libretranslate > bos.
  - `turkish_title` bossa en sona duser.
  - Esitlikte en erken `created_at`, sonra en kucuk `id`.
- **Yanit:** `GET /api/gundem/` (AllowAny) → `{success: True, olaylar: [...], hesaplandi: iso}`.
  - Her olay: `{bolum, kayit (bolumun mevcut serilestiricisiyle), kaynak_sayisi, kaynaklar: [orijinal adlar, alfabetik], makale_sayisi, bolumler: [sirali benzersiz], puan (2 ondalik), ilk, son}`.
  - Tek kaynakli dolgu ogeleri ayni bicimdedir: `kaynak_sayisi 1`, `makale_sayisi 1`.
- **Onbellek:** anahtar `gundem_ozeti`, 120 sn. Hata durumunda 500 degil `{success: False, olaylar: []}` ve 200 (ana sayfa bozulmaz).
- **Determinizm:** ayni veri ve ayni `simdi` her zaman ayni sonucu verir; kume ve sozluk sirasina bagli olmaz.
- **LLM ve dis istek yok.**
- **Testler ve stil:**
  - Django: `bash scripts/pg_test.sh test news --noinput` (tek kullanimlik PG+Redis).
  - Vitest: frontend'i `teknoloji-frontend` konteynerinin `/tmp/<dizin>`'ine kopyalayip orada `npx vitest run` ve `npx eslint src`.
  - ruff: CI gibi.
  - Kod ASCII Turkce ad ve yorumlarla. Kullanici metni: rozet "{n} kaynak", ipucu kaynak adlari ", " ile.
  - Commit mesaji Turkce, aksansiz; sonu `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - Dal: `feat/gundem-puani` (worktree `CyberNews/wt-gundem`). Merge yalniz kullanici onayiyla.

## Review Focus

1. **Genel ad tek basina birlestirmez:** "Microsoft" ya da "Google" gecen ilgisiz iki baslik ayri kalir. → Task 1 `test_genel_ad_tek_basina_birlestirmez` (fiksturden gercek cift).
2. **Ayni kaynagin tekrarlari cok kaynak sayilmaz:** ayni satici surum notlari (`GitHub Releases` x3) `farkli_kaynak = 1` kalir ve cok kaynakli bolume girmez. → Task 1 `test_ayni_kaynak_tekrari_tek_kaynak`.
3. **Yeni eklenen kaynagin eski yazilari:** `created_at` yeni ama yayin tarihi 10 gun once olan kayitlar pencereye girmez. → Task 2 `test_eski_yayin_tarihli_kayit_pencere_disi`.
4. **Hesap hatasi ana sayfayi bozmaz:** `olaylari_sec` istisna atarsa uc 200 + `success: False`; frontend karti "Gündem bilgisi alınamadı." gosterir. → Task 2 `test_hesap_hatasinda_200_ve_bos`, Task 3 `gundem_hatasi_karta_yansir`.
5. **Determinizm:** ayni girdi iki kez → ayni cikti; girdi sirasi karistirilinca ayni cikti. → Task 1 `test_sira_bagimsiz_ve_deterministik`.

---

### Task 1: Saf gruplama ve puan (`news/gundem.py`) + gercek veri fikstur testleri

**Files:**
- Create: `news/gundem.py`
- Create: `news/tests/fixtures/gundem_basliklari.json` (canli DB'den YALNIZ OKUYARAK aktarilir)
- Test: `news/tests/test_gundem.py`

**Interfaces:**
- Produces:
  - `@dataclass Ogeler`: `bolum: str, id: int, source: str, baslik: str, created_at: datetime, yayin: Optional[date], ceviri: str, tr_baslik: str`. `baslik` orijinal Ingilizce; `ceviri` = translation_provider.
  - `olaylari_grupla(ogeler: List[Ogeler]) -> List[List[Ogeler]]`
  - `olay_puani(olay: List[Ogeler], simdi: datetime) -> float`
  - `temsilci(olay: List[Ogeler]) -> Ogeler`
  - `olaylari_sec(ogeler: List[Ogeler], simdi: datetime, adet: int = 6) -> List[dict]`. Dict anahtarlari: `temsilci: Ogeler, kaynak_sayisi, kaynaklar, makale_sayisi, bolumler, puan, ilk, son`.
  - `penceredeki(ogeler, simdi) -> List[Ogeler]`: 72 sa + 4 takvim gunu kurali.

- [ ] **Step 1: Fikstur.**
  - Canli konteynerde, yazma olmadan, su gunlerin bes bolum kayitlarini JSON'a aktar: 2026-09-28..10-03, 10-18..10-23, 10-27..11-03. Alanlar `bolum, id, source, original_title, turkish_title, translation_provider, created_at (UTC ISO), yayin`.
  - Komut ornegi: `MSYS_NO_PATHCONV=1 docker exec -i teknoloji-api python manage.py shell < /path/to/aktar.py > fikstur.json`; betik scratchpad'de.
  - Dosyayi `news/tests/fixtures/gundem_basliklari.json`'a koy.
- [ ] **Step 2: Failing testler** (`SimpleTestCase`; fikstur yukleyici yardimci; `simdi` Istanbul saatiyle verilir):

```python
def test_binance_30_ekim_birinci(self):          # simdi 2026-10-30 20:00 -> secim[0] basliklarinda 'Binance', kaynak_sayisi >= 5
def test_binance_2_kasim_ilk_uc_ve_tek_satir(self): # simdi 2026-11-02 12:00 -> Binance ilk 3'te; 'Binance' iceren tek oge
def test_php2shell_21_ekim_birinci(self):        # simdi 2026-10-21 20:00 -> secim[0] 'PHP' ve kaynak_sayisi >= 6
def test_gemini_argon_ilk_uc_bolumler_arasi(self): # simdi 2026-10-01 20:00 -> ilk 3'te; bolumler {'ai','news'} alt kumesi
def test_genel_ad_tek_basina_birlestirmez(self):  # fiksturden 'Microsoft' (ya da 'Google') gecen ilgisiz iki gercek baslik ayri olaylarda
def test_ayni_kaynak_tekrari_tek_kaynak(self):    # 3 sentetik 'GitHub Releases' kubernetes ogesi ortak ad -> kaynak_sayisi 1, cok kaynakli secimde degil
def test_cok_kaynak_yoksa_en_yeni_ile_dolar(self): # yalniz tek kaynakli ogeler -> 6 oge, created_at azalan
def test_temsilci_en_iyi_ceviri_sonra_en_erken(self)
def test_puan_formulu(self):                      # 3 kaynak 4 makale etkisiz yas 0 -> 3.5; ayni yas 24 -> 1.75; etki varsa +1.5
def test_pencere_72_saat_ve_4_gun(self)
def test_sira_bagimsiz_ve_deterministik(self)
```

- [ ] **Step 3:** Kos `bash scripts/pg_test.sh test news.tests.test_gundem --noinput` → FAIL.
- [ ] **Step 4: Uygula** `news/gundem.py`.
  - Gruplama ozel adlar (penceredeki belge sikligi dusuk, buyuk harfli ya da harf-rakam karisik sozcukler) ve durak sozcuksuz baslik benzerligi ile yapilir.
  - Esikler fiksture gore ayarlanir.
  - Kararlar ve esikler modul docstring'ine yazilir (neden bu esik, hangi ornek).
- [ ] **Step 5:** Kos → PASS. Tum `news` suiti + ruff.
- [ ] **Step 6: Commit:** `feat(gundem): cok kaynakli olay gruplama ve puan (saf fonksiyonlar)`

### Task 2: `/api/gundem/` ucu

**Files:**
- Modify: `news/views.py` (`get_gundem`), `news/urls.py` (`path('api/gundem/', views.get_gundem, name='get_gundem')`)
- Test: `news/tests/test_gundem_ucu.py`

**Interfaces:**
- Consumes: Task 1 `Ogeler`, `penceredeki`, `olaylari_sec`.
- Produces: Global Constraints'teki yanit. `kayit` = bolumun mevcut serilestiricisi (`NewsArticleSerializer`, `KubernetesEntrySerializer`, `SREEntrySerializer`, `DevToolsEntrySerializer`, `AINewsEntrySerializer`).

- [ ] **Step 1: Failing testler** (`TestCase` + `APIClient`, onbellek LOCMEM):
  - `test_yanit_bicimi`
  - `test_cve_girmez`
  - `test_eski_yayin_tarihli_kayit_pencere_disi`
  - `test_onbellek_120_sn`: ikinci cagri hesap fonksiyonunu cagirmaz (mock sayaci)
  - `test_hesap_hatasinda_200_ve_bos`: `olaylari_sec` istisna → 200, `success False`, `olaylar []`
  - `test_anonim_erisim`
  - `test_kayit_bolum_serilestiricisiyle`: `turkish_title`, `translation_provider`, `created_at` alanlari var
- [ ] **Step 2:** FAIL. **Step 3:** Uygula. Bes modelden `created_at >= simdi-72sa` sorgusu tek seferde, `values()` ile `Ogeler`'e cevrilir; secilen temsilciler icin serilestirici. **Step 4:** PASS + tum suit + ruff.
- [ ] **Step 5: Commit:** `feat(api): /api/gundem/ ucu`

### Task 3: Frontend Gundem karti

**Files:**
- Modify: `frontend/src/components/genel/Gundem.jsx`, `frontend/src/components/genel/GenelBakis.jsx`, `frontend/src/services/api.js` (`gundemApi.getGundem()`), `frontend/src/styles/tema.css` (rozet)
- Remove or keep: `frontend/src/utils/gundem.js` + testi. Kullanilmiyorsa silinir.
- Test: `GenelBakis.test.jsx`, yeni `Gundem.test.jsx`

**Interfaces:**
- Consumes: Task 2 yaniti.
- Produces: `Gundem({ olaylar, hata, onSec })`. `olaylar` = API `olaylar` dizisi.

- [ ] **Step 1: Failing testler:**
  - `cok_kaynakli_olayda_rozet`: `kaynak_sayisi 6` → "6 kaynak" metni, `title` = kaynak adlari ", " ile.
  - `tek_kaynakta_rozet_yok`
  - `alt_satir_bolum_kaynak_zaman`: zaman olayin `son`'u.
  - `tiklama_temsilciyi_okuma_panelinde_acar`: `haberOkumaKaydi(kayit, bolum)`.
  - `gundem_hatasi_karta_yansir`: `success False` ya da istek hatasi → "Gündem bilgisi alınamadı.".
  - `genel_bakis_gundem_ucunu_cagirir`: bes liste ucu artik Gundem icin cagrilmaz.
  - `son_ziyaret_olay_son_zamanini_kullanir`.
- [ ] **Step 2:** FAIL. **Step 3:** Uygula. **Step 4:** Vitest + eslint PASS.
- [ ] **Step 5: Commit:** `feat(arayuz): gundem karti olay ve kaynak rozetiyle`

### Task 4: Belgeler, PR, canliya alma

- [ ] README:
  - API bolumu: `/api/gundem/`.
  - Ozellikler: Gundem olcusu.
  - Test sayilari.
- [ ] Spec "Durum": uygulandi.
- [ ] Push, PR (govdede kabul orneklerinin sonuclari). CI. **Merge kullanici onayiyla.**
- [ ] Merge sonrasi:
  - Canli checkout `git pull --ff-only`, `teknoloji-api` yeniden baslat.
  - Tarayicida ana sayfa Gundem kartini dogrula: rozetler, tiklama, son 72 saatin buyuk olaylari.
