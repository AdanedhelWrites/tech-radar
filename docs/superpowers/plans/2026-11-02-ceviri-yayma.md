# Ceviri Kapasitesi: Gemini'yi Tam ve Dogru Yaymak — Uygulama Plani

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gemini'nin ucretsiz kotasini onem sinifina gore onceleyip gun icine yaymak, kayitlari toplu cevirmek ve ucretsiz yedek saglayicilar eklemek.

**Architecture:**
- Uc PR halinde ilerler.
- **PR-A** `news/retranslate.py` yukseltme asamasini imlecsiz bir "en yeni N aday" sorgusuna cevirir, CVE icin onem suzgeci ekler ve bolum sirasini degistirir. Ayrica bir tur payi nesnesi (`_Tur`) ile Gemini harcamasini sinirlar. `news/gemini.py`'den CVE rezervi kalkar.
- **PR-B** `gemini.paket_cevir` ekler; yukseltme asamasi adaylari karakter/kayit sinirina gore paketler.
- **PR-C** saglayici siniflarini (`news/kayit_cevirmenleri.py`) ekler: Gemini birincil/ikinci model, OpenRouter `:free`, DeepL Free. Retranslate bunlari sirayla dener.

**Tech Stack:** Django 4.2, Celery 5.3 (Beat crontab), django-redis, requests, React 18 + Vitest. Yeni pip/npm bagimliligi yok.

**Spec:** `docs/superpowers/specs/2026-11-02-ceviri-yayma-design.md` — once onu oku. Onceki: `2026-09-15-gemini-yukseltme-design.md`, ADR-0004 (saglayici zinciri), ADR-0005 (CVE rezervi; bu plan rezervi kaldirir).

## Global Constraints

- **Test kurallari:**
  - Hicbir test gercek Gemini/OpenRouter/DeepL/LibreTranslate'e gitmez. HTTP `mock.patch('news.<modul>.requests.post')` ile taklit edilir. `GuvenliTestRunner` anahtarlari bosaltir.
  - Redis'e yazan testler benzersiz onek kullanir (`news.tests.base.test_redis_client()` + `uuid4().hex`). `FLUSHDB` yasak.
  - Hicbir Celery isi kuyruga atilmaz; fonksiyonlar dogrudan cagrilir.
- **Calisma yeri ve testler:**
  - Canli checkout bind mount ile canli koddur; uygulama ayri bir worktree'de yapilir: `CyberNews/wt-ceviri-yayma`.
  - Testler worktree'den kosar: `scripts/pg_test.sh test news --noinput` (tek kullanimlik PG+Redis; canli yigina dokunmaz).
  - Frontend testleri worktree'nin `frontend/` dizini, `teknoloji-frontend` konteynerinin `/tmp/feN` kopyasina alinarak kosar (bkz. memory `vitest-konteyner-tmp`).
- **Sabit degerler (spec):**
  - `GEMINI_DAILY_BUDGET=450`
  - CVE Gemini adayi: `cvss_score >= 7.0` VEYA `kev_added_date` dolu
  - `GEMINI_BATCH_CHARS=10000`, `GEMINI_BATCH_MAX=15`
  - DeepL aylik tavan 450.000 karakter
  - OpenRouter model adi `:free` ile bitmeli
- **Bolum sirasi (spec G3):** `cve, news, ai, sre, devtools, kubernetes`.
- **Retranslate Beat:** anahtar `retranslate-pending-hourly`, `crontab(minute=5, hour='1-5,7-11,13-17,19-23')`, yani gunde 20 tur. 00/06/12/18 cekim saatleridir.
- **Kod stili:** yorumlar ve adlar aksansiz ASCII Turkce, mevcut dosyalarin uslubunda. Modele giden talimat ve kullaniciya gorunen metin duzgun Turkce karakterlerle yazilir.
- **Commit ve PR:**
  - Commit mesaji Turkce, aksansiz; sonu `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
  - Dallar: `feat/ceviri-yayma-a` (spec+plan+PR-A), `feat/ceviri-yayma-b` (A'nin ustune), `feat/ceviri-yayma-c` (B'nin ustune).
  - Her PR `main`'e; merge yalniz kullanicinin acik onayiyla.
- **Canliya alma:** her PR merge'den sonra canli checkout `main`'e cekilir, worker/beat/api yeniden baslatilir. PR-C'de migration once uygulanir (repo kurali: once sema, sonra kod).
- **Anahtarlar:** `.env` repoda degil. `OPENROUTER_API_KEY` ve `DEEPL_API_KEY` degerlerini kullanici kendisi girer. Hicbir anahtar loga, API yanitina ya da teste gercek degerle yazilmaz.

## Review Focus

1. **Paket yanitinda kimlik karismasi:** model `k1`'in cevirisini `k0`'a koyarsa ya da bir kimligi dusururse yalniz o kayit reddedilir, digerleri yazilir. → Task B2 `test_eksik_kimlik_yalniz_o_kaydi_reddeder`.
2. **Tur payi bittiginde yedek tetiklenmez:** pay 0 iken Gemini hazir olsa bile istek atilmaz ve OpenRouter/DeepL cagrilmaz. → Task A2 `test_tur_payi_bitince_gemini_cagrilmaz`, Task C3 `test_tur_payi_bitince_yedek_cagrilmaz`.
3. **Orta/dusuk CVE hicbir ucretsiz saglayiciya gitmez:** bekleyen asamada da, yedek zincirde de. → Task A1 `test_orta_cve_bekleyende_gemini_almaz`, Task C3 `test_orta_cve_yedege_gitmez`.
4. **Gun donumu ve tur sayisi:** Pasifik gece yarisina 30 dk kala `kalan_tur_sayisi` en az 1 doner, pay sonsuza/negatife kacmaz. → Task A2 `test_kalan_tur_en_az_bir`.
5. **Ust uste binen tur:** onceki tur kilidi tutarken ikinci cagri sessizce cikar. Kilit, sahibi olmayan tur tarafindan silinmez. → Task A3 `test_kilit_tutuluyken_ikinci_tur_atlar`.

---

## PR-A: Sira ve yayma

### Task A0: Hazirlik

- [ ] **Step 1:** Canli checkout'u `main`'e dondur.
  - Spec commit'i `feat/ceviri-yayma`'da duruyor.
  - Komutlar: `git switch main && git pull --ff-only && git branch -m feat/ceviri-yayma feat/ceviri-yayma-a && git worktree add ../wt-ceviri-yayma feat/ceviri-yayma-a`
  - Not: `git branch -m` dal checkout'ta degilken calisir; once `main`'e gecilir.
- [ ] **Step 2:** Plan dosyasini worktree'de commit et (`docs/superpowers/plans/2026-11-02-ceviri-yayma.md`).
- [ ] **Step 3:** Taban test kosusu: `scripts/pg_test.sh test news --noinput`
  - Beklenen: tamami gecer (README'ye gore 603 test). Gecmeyen varsa dur.

### Task A1: Onem sinifi, yeni-once yukseltme, bolum sirasi, rezervin kaldirilmasi

**Files:**
- Modify: `news/gemini.py` (GEMINI_CVE_RESERVE, ONCELIKLI_BOLUM, butce_tavani(bolum) kalkar; butce 450)
- Modify: `news/retranslate.py` (BOLUMLER sirasi, `_gemini_adayi_mi`, `_yukselt` sorgusu)
- Modify: `news/tests/test_gemini.py` (ButcePayiTests silinir, yerine tek tavan testi)
- Modify: `news/tests/test_retranslate.py`:
  - ButcePayiRetranslateTests silinir
  - imlec temelli yukseltme testleri yeni davranisa cevrilir
  - BolumOncelikTests yeni sira
- Modify: `docker-compose.yml` (iki `GEMINI_CVE_RESERVE` satiri silinir)
- Modify: `helm/tech-radar/templates/configmap.yaml`, `helm/tech-radar/values.yaml` (geminiCveReserve silinir, geminiDailyBudget "450")
- Modify: `README.md` (ortam degiskeni tablosu)

**Interfaces:**
- Produces:
  - `gemini.butce_tavani() -> int` (parametresiz; `GEMINI_DAILY_BUDGET`)
  - `gemini.hazir() -> bool`, `gemini.butce_var() -> bool`
  - `gemini.kaydi_cevir(alanlar, bolum=None)`: `bolum` yalniz log icin
  - `retranslate.CVE_GEMINI_ESIGI = 7.0`
  - `retranslate._gemini_adayi_mi(ad: str, kayit) -> bool`
  - `retranslate._yukseltme_adaylari(ad, model, sinir) -> list`

- [ ] **Step 1: Failing testleri yaz** (`test_retranslate.py`, yeni sinif `OnemSinifiTests(GeminiSahteMixin, SaglayiciZinciriMixin, RetranslateTestBase)`)

```python
def test_orta_cve_yukseltilmez(self):           # cvss 6.5, libretranslate -> _calistir sonrasi provider hala 'libretranslate', gemini cagri sayisi 0
def test_yuksek_cve_yukseltilir(self):          # cvss 7.0 -> 'gemini'
def test_kev_orta_cve_yukseltilir(self):        # cvss 5.0 + kev_added_date -> 'gemini'
def test_skorsuz_cve_yukseltilmez(self):        # cvss None, kev yok -> 'libretranslate'
def test_orta_cve_bekleyende_gemini_almaz(self):# needs_translation=True, cvss 4.0 -> zincirle (LIBRE) cevrilir, gemini cagri 0
def test_yukseltme_en_yeniden_baslar(self):     # 3 libre AI kaydi farkli created_at, upgrade_batch=1 -> en yeni olan 'gemini'
def test_reddedilen_yukseltme_deneme_sayar(self):# gemini None doner -> translation_attempts 1; 5 turdan sonra aday degil (gemini cagrisi 6. turda yok)
def test_cok_uzun_kayit_yukseltmede_deneme_sayar(self)  # GEMINI_MAX_CHARS ustu -> attempts +1
```

`BolumOncelikTests.test_bolum_sirasi_beklendigi_gibi`: `[ad for ad, *_ in BOLUMLER] == ['cve','news','ai','sre','devtools','kubernetes']`.
`test_gemini.py` yeni: `test_tek_tavan_tum_bolumler_icin` → `gemini.butce_tavani() == 450` ve `GEMINI_DAILY_BUDGET == 450`.

- [ ] **Step 2: Kos, basarisiz oldugunu gor.**
  Komut: `scripts/pg_test.sh test news.tests.test_retranslate news.tests.test_gemini --noinput`
  Beklenen: yeni testler FAIL.

- [ ] **Step 3: Uygula.**
  - `gemini.py`: rezerv sabitleri ve dallanma silinir; `kaydi_cevir`'deki tavan kontrolu `butce_tavani()` olur.
  - `retranslate.py`:
    - `_gemini_adayi_mi`: CVE icin `(cvss_score or 0) >= 7.0 or kev_added_date is not None`; diger bolumler `True`.
    - `_gemini_ile_cevir` aday degilse `None` doner (istek yok).
    - `_yukselt`: imlec kullanilmaz, `{prefix}:upgrade-cursor:*` anahtarlari artik okunmaz/yazilmaz. Sorgu:
      `filter(needs_translation=False, translation_provider='libretranslate', translation_attempts__lt=RETRANSLATE_MAX_ATTEMPTS)`.
      CVE ise ek olarak `Q(cvss_score__gte=7.0) | Q(kev_added_date__isnull=False)`. Sira `order_by('-created_at', '-id')[:sinir]`.
    - Hata ayrimi:
      - Icerik hatasi (`_gemini_alanlari` bos ya da kaydi_cevir None iken Gemini hala hazir) → `_basarisiz_say`.
      - Hazir degilse (istek/kota hatasi) → sayac artmaz, asama durur.
  - Bekleyen asama (`_bekleyenler`) imlecli ve artan sirali kalir; yalniz Gemini adaylik kontrolu eklenir.
    Spec G2'nin bekleyen kismindan sapma: spec dosyasindaki ilgili cumle bu task'ta "bekleyen asamasi bugunku imlec sirasini korur (bekleyen kayit nadirdir, sira etkisizdir)" olarak duzeltilir.

- [ ] **Step 4:** Eski testleri yeni davranisa uyarla:
  - Silinecekler:
    - `test_transport_hatasinda_yukseltme_imleci_ilerlemez` → yerine `test_transport_hatasinda_yukseltme_deneme_saymaz`
    - `test_butce_asama_ortasinda_bitince_imlec_ilerlemez` → yerine `test_butce_bitince_kalanlar_sonraki_tura_kalir`
    - ButcePayi* siniflari
  - Tum dosya kos: `scripts/pg_test.sh test news --noinput` → hepsi PASS.
- [ ] **Step 5:** Config temizligi (compose, helm, README), `helm template` ile dogrulama:
  `docker run --rm -v "$PWD/helm:/helm" alpine/helm:3 template /helm/tech-radar >/dev/null`. Beklenen cikis kodu 0. CI'daki "Helm / Compose dogrulama" isi ayni seyi yapar.
- [ ] **Step 6: Commit**: `feat(ceviri): onem sinifi, yeni-once yukseltme, CVE rezervi kalkti`

### Task A2: Tur payi (gun icine yayma)

**Files:**
- Modify: `news/retranslate.py` (`_Tur`, `kalan_tur_sayisi`, `tur_payi`; `retranslate_pending` payi kurar)
- Modify: `cybernews/settings.py` (Beat anahtari ve saatleri)
- Test: `news/tests/test_retranslate.py` (`TurPayiTests`, `RetranslateGoreviTests` guncellenir)

**Interfaces:**
- Consumes: `gemini.butce_kullanimi() -> int`, `gemini.butce_tavani() -> int`, `gemini.PASIFIK`
- Produces:
  - `retranslate.kalan_tur_sayisi(simdi: datetime) -> int`. Su andan sonraki Pasifik gece yarisina kadar Beat'in `retranslate-pending-hourly` girdisinin calisacagi an sayisi. `simdi - 30 dk` sonrasindaki ilk an (simdiki tur) dahildir. En az 1.
  - `retranslate.tur_payi(simdi: datetime) -> int` = `ceil(max(0, butce_tavani() - butce_kullanimi()) / kalan_tur_sayisi(simdi))`
  - `class _Tur: pay: int; baslangic: int; def kalan(self) -> int`. Kalan = `pay - (butce_kullanimi() - baslangic)`, en az 0.
  - `sonuc['stopped_reason']` yeni deger: `'gemini_tur_payi'`
  - `sonuc['gemini_tur_payi']`: turun payi (int)

- [ ] **Step 1: Failing testler**

```python
def test_kalan_tur_sayisi_gun_basinda_20(self):     # simdi = Pasifik 00:10 karsiligi Istanbul saati -> 20 civari; tam deger: takvimdeki 01-05,07-11,13-17,19-23 saatlerinin o an ile Pasifik gece yarisi arasindaki :05 anlari (testte elle sayilan beklenen degerle karsilastir)
def test_kalan_tur_en_az_bir(self):                 # Pasifik 23:45 -> 1
def test_tur_payi_kalan_butceyi_bolustirir(self):  # kullanim 250, kalan_tur 10 -> ceil(200/10) = 20
def test_tur_payi_butce_bittiyse_sifir(self):      # kullanim 450 -> 0
def test_tur_payi_bitince_gemini_cagrilmaz(self):  # pay=1, 3 aday AI kaydi -> kaydi_cevir tam 1 kez cagrilir; stopped_reason 'gemini_tur_payi'
def test_tur_payi_bitince_bekleyen_zincirle_cevrilir(self) # pay 0, needs_translation kaydi -> LIBRE ile yazilir
def test_oncelik_kati_cve_once(self):              # pay=2, 2 yuksek CVE + 2 AI libre -> CVE'ler gemini, AI'lar libre kalir
```

`RetranslateGoreviTests`:
- `test_beat_takvimi_saatlik_cekim_saatleri_haric`: minute `{5}`, hour = `set(range(24)) - {0,6,12,18}`, anahtar `retranslate-pending-hourly`.
- `test_cekim_saatleriyle_cakismaz` yeni anahtarla aynen kalir.

- [ ] **Step 2: Kos → FAIL.**
- [ ] **Step 3: Uygula.**
  - `kalan_tur_sayisi`, `settings.CELERY_BEAT_SCHEDULE['retranslate-pending-hourly']['schedule']` crontab'inin `hour`/`minute` kumelerinden saat saat yururuk sayar. Saat dilimi crontab `tz`'si, yani Istanbul.
  - `retranslate_pending(..., tur: _Tur = None)`: `None` ise `_Tur(pay=tur_payi(timezone.now()), baslangic=gemini.butce_kullanimi())` kurulur. Testler `tur=` ile sabit pay verir.
  - `_gemini_ile_cevir` ve `_yukselt`'teki her `gemini.hazir()` kontrolu `gemini.hazir() and tur.kalan() > 0` olur.
  - Pay bitince:
    - yukseltme asamasi durur, `stopped_reason='gemini_tur_payi'` (gunluk butce bittiyse `'gemini_budget'` onceliklidir)
    - bekleyen asamasi zincirle (Libre) devam eder
- [ ] **Step 4: Kos → PASS** (tum `news`).
- [ ] **Step 5: Commit**: `feat(ceviri): gunluk butce saatlik turlara yayiliyor (450/gun, 20 tur)`

### Task A3: Tekil calisma kilidi

**Files:**
- Modify: `news/tasks.py` (`retranslate_pending_task`)
- Test: `news/tests/test_retranslate.py` (`RetranslateGoreviTests`)

**Interfaces:**
- Produces: Redis anahtari `retranslate:kilit`. Deger rastgele jeton, `ex = RETRANSLATE_TIME_BUDGET + 600`. Kilit alinamazsa gorev `{'skipped': 'locked'}` doner ve `retranslate_pending` cagrilmaz.

- [ ] **Step 1: Failing testler**:
  - `test_kilit_tutuluyken_ikinci_tur_atlar`: anahtar onceden baska jetonla set → donus `{'skipped': 'locked'}`, sahte `retranslate_pending` cagrilmadi, anahtarin degeri degismedi.
  - `test_tur_bitince_kilit_birakilir`
  - `test_tur_istisnayla_bitse_de_kilit_birakilir`
  - Redis: test istemcisi; anahtar adini `mock.patch.object(tasks, 'RETRANSLATE_KILIT_ANAHTARI', f'{onek}:kilit')` ile benzersizlestir.
- [ ] **Step 2: Kos → FAIL.** **Step 3: Uygula.**
  - `set(nx=True, ex=...)`.
  - `finally` icinde yalniz jeton eslesirse sil (kucuk Lua betigi ya da `get`+`delete`; tek worker sureci icin `get`+`delete` yeterli, yorumla belirt).
  - Mevcut `test_gorev_retranslate_pending_cagirir` kilit yokken aynen gecer.
- [ ] **Step 4: Kos → PASS.** **Step 5: Commit**: `feat(ceviri): retranslate turu tekil kilitle korunuyor`

### Task A4: Saglik ucunda butce ve vazgecilen yukseltmeler, seritte gosterim

**Files:**
- Modify: `news/gemini.py` (`butce_ozeti() -> dict`)
- Modify: `news/views.py:get_saglik` (`translation_budget` alani)
- Modify: `news/fetch_runs.py:bolum_ozetleri` (`upgrade_given_up`)
- Modify: `frontend/src/components/SaglikSeridi.jsx`, `frontend/src/components/CeviriEtiketi.jsx` (Libre aciklama metni)
- Test: `news/tests/test_saglik.py`, `frontend/src/components/SaglikSeridi.test.jsx`, `frontend/src/components/CeviriEtiketi.test.jsx`

**Interfaces:**
- Produces:
  - `gemini.butce_ozeti() -> {'used': int, 'limit': int, 'period': 'day', 'available': bool, 'cooldown': bool}`
  - `/api/saglik/` → `translation_budget: {'gemini': <butce_ozeti>}`. PR-C ayni sozluge `openrouter`/`deepl` ekler.
  - `sections[<ad>].upgrade_given_up: int`: `translation_provider='libretranslate'`, `needs_translation=False`, `translation_attempts >= RETRANSLATE_MAX_ATTEMPTS` olan kayit sayisi.

- [ ] **Step 1: Failing testler:**
  - Django: `test_saglik_gemini_butcesini_gosterir`
    - butce sayaci 57'ye getirilir → `translation_budget.gemini == {'used': 57, 'limit': 450, 'period': 'day', ...}`
    - yanitta `key`/`api` iceren hicbir alan yok
  - Django: `test_saglik_vazgecilen_yukseltmeleri_sayar`
  - Vitest: `SaglikSeridi` → `translation_budget.gemini.used=57` ile "Gemini 57/450" metni gorunur; alan yoksa hic gorunmez.
  - Vitest: `CeviriEtiketi` libretranslate `title` metni "En geç 2 saat içinde" icermez.
- [ ] **Step 2: Kos → FAIL.**
- [ ] **Step 3: Uygula.**
  - Seritte "Çeviri kuyruğu" ogesinden sonra yeni oge: `<strong>Gemini</strong> {used}/{limit}`. `cooldown` true ise `rozet uyari` "beklemede".
  - Libre rozet aciklamasi su metin olur: `'Yerel LibreTranslate ile çevrildi; anlam hatası olabilir, orijinal metne bakın. Haberler ile kritik ve yüksek zafiyetler gün içinde Gemini ile iyileştirilir.'`
- [ ] **Step 4: Kos → PASS** (Django `news`, Vitest tum dosyalar, `npm run lint`).
- [ ] **Step 5: Commit**: `feat(saglik): Gemini butcesi ve vazgecilen yukseltmeler gorunuyor`

### Task A5: PR-A'yi ac ve canliya al

- [ ] README'deki "Ceviri Sistemi" bolumunu guncelle:
  - onem sinifi
  - saatlik tur
  - 450 butce
  - rezervin kalkmasi
  - test sayilari
- [ ] ADR-0005'e "2026-11-02: CVE rezervi bu tasarimla kaldirildi" notunu dus.
- [ ] Push, PR ac (govde: ozet, olcum tablosu, test kosusu). CI'yi bekle. **Merge icin kullanicidan onay iste.**
- [ ] Merge sonrasi: canli checkout `git pull --ff-only`, `docker compose restart teknoloji-worker teknoloji-scheduler teknoloji-api`.
- [ ] Ilk saatlik turdan sonra dogrula:
  - FetchRun `retranslate` satiri basarili
  - `/api/saglik/` `translation_budget.gemini.used` artti
  - en yeni 20 haberin cogu `gemini`
  - CVSS<7 CVE'lerde yeni `gemini` yok

---

## PR-B: Toplu ceviri

### Task B1: Gemini paket istemcisi

**Files:**
- Modify: `news/gemini.py`:
  - `_istek_at(govde: dict) -> Optional[requests.Response]`: butce artir, kapi, post, 429/5xx devre kesici, 4xx geri alma. `kaydi_cevir` de bunu kullanir.
  - `PaketSonucu` ve `paket_cevir`
  - talimata paket kurali
- Test: `news/tests/test_gemini.py` (`GeminiPaketTests`)

**Interfaces:**
- Produces:
  - `GEMINI_BATCH_CHARS = int(env, '10000')`, `GEMINI_BATCH_MAX = int(env, '15')`
  - `@dataclass class PaketSonucu`:
    - `ceviriler: Dict[str, Dict[str, str]]`
    - `reddedilen: Set[str]`
    - `istek_hatasi: bool = False`
    - `kesildi: bool = False`
  - `paket_cevir(kayitlar: Dict[str, Dict[str, str]], bolum: Optional[str] = None) -> PaketSonucu`. Anahtarlar kimlik (`'k0'`, `'k1'`…), degerler `{'title': ..., 'description': ...}`. Tek istek atar.
  - Istek govdesi:
    - kullanici metni `json.dumps(kayitlar)`
    - `responseSchema`: her kimlik icin ic ice OBJECT, alanlari `required`
  - Talimata eklenecek kural (duzgun Turkce): `"- Girdi, kimlik anahtarlı kayıtlardan oluşan bir JSON nesnesidir; her kaydı ayrı çevir, aynı kimlik ve alan anahtarlarıyla döndür. Kayıtları birleştirme, sırasını ya da kimliğini değiştirme."`

- [ ] **Step 1: Failing testler:**

```python
def test_paket_tek_istekte_gider(self):            # 3 kayit -> requests.post 1 kez, butce +1
def test_paket_basarili_kayitlari_dondurur(self):  # ceviriler 3 kimlik, reddedilen bos
def test_bozuk_kayit_yalniz_kendini_dusurur(self): # k1 yanki -> reddedilen {'k1'}, ceviriler {'k0','k2'}
def test_eksik_kimlik_yalniz_o_kaydi_reddeder(self): # yanitta k2 yok -> reddedilen {'k2'}
def test_alanlardan_biri_bozuksa_kayit_reddedilir(self): # k0 title ok, description bos -> 'k0' reddedilen
def test_max_tokens_kesildi_isaretler(self):       # finishReason MAX_TOKENS -> kesildi True, ceviriler bos, reddedilen bos
def test_429_istek_hatasi(self):                   # istek_hatasi True, reddedilen bos, devre kesici acik
def test_hazir_degilse_istek_yok(self):            # istek_hatasi True, post cagrilmadi
def test_talimat_paket_kuralini_icerir(self):
```

- [ ] **Step 2: Kos → FAIL.**
- [ ] **Step 3: Uygula.**
  - Kayit dogrulamasi icin mevcut `_alan_sorunu` her alana uygulanir.
  - `kaydi_cevir`'in davranisi ve testleri degismez; yalniz HTTP kismi `_istek_at`'a tasinir.
- [ ] **Step 4: Kos → PASS** (tum `news`). **Step 5: Commit**: `feat(gemini): paket cevirisi (bir istekte birden cok kayit)`

### Task B2: Yukseltme asamasinda paketleme

**Files:**
- Modify: `news/retranslate.py` (`_paketle`, `_yukselt` paketli dongu)
- Test: `news/tests/test_retranslate.py` (`PaketliYukseltmeTests`)

**Interfaces:**
- Consumes: `gemini.paket_cevir`, `PaketSonucu`, `GEMINI_BATCH_CHARS`, `GEMINI_BATCH_MAX`, `_Tur.kalan()`
- Produces: `retranslate._paketle(adaylar: List[Tuple[kayit, Dict[str,str]]], karakter: int, adet: int) -> List[List[Tuple[kayit, Dict[str,str]]]]`. Sirayi korur ve acgozlu doldurur. Tek basina sinirdan buyuk kayit kendi paketinde gider (GEMINI_MAX_CHARS'i zaten gecmistir).

- [ ] **Step 1: Failing testler:**

```python
def test_paketle_karakter_ve_adet_siniri(self):        # 20 x 900 kr, 10000/15 -> [11, 9]; 20 x 100 kr -> [15, 5]
def test_yukseltme_tek_istekte_bes_kayit(self):         # 5 AI libre -> paket_cevir 1 kez, 5 kayit 'gemini'
def test_paketteki_reddedilen_deneme_sayar_digerleri_yazilir(self)
def test_istek_hatasinda_hicbir_kayit_deneme_saymaz(self)  # istek_hatasi -> attempts hep 0, asama durur
def test_kesilen_paket_ikiye_bolunup_ayni_turda_denenir(self) # ilk cagri kesildi (4 kayit), sonra 2+2 basarili -> 3 cagri, 4 kayit gemini
def test_tek_kayit_kesilirse_icerik_hatasi(self)
def test_k8s_yapisal_changelog_paketlenmez(self)       # ===SECTION: kaydi -> kaydi_cevir ile tek gider; diger k8s kaydi paket_cevir ile
def test_tur_payi_paket_basina_sayilir(self)            # pay=1, 5 aday -> 1 paket gider, 5'i de gemini
```

- [ ] **Step 2: Kos → FAIL.**
- [ ] **Step 3: Uygula.**
  - `_yukselt` adaylari `_gemini_alanlari` ile hazirlar.
  - Yapisal K8s kayitlari mevcut tekil yoldan gider.
  - Kalanlar `_paketle` ile paketlenir.
  - Her paketten once `gemini.hazir() and tur.kalan() > 0` kontrol edilir. Paket kuyrugu bir `deque` ile tutulur; `kesildi` olan paket ikiye bolunup basa eklenir.
  - Kimlikler `f'k{i}'` (paket ici sira).
  - Bekleyen asamasi tekil kalir. Bu benim kararim: bekleyen kayit nadir, plan notu olarak PR'a yazilir.
- [ ] **Step 4: Kos → PASS.** **Step 5: Commit**: `feat(ceviri): yukseltme asamasi paketli`

### Task B3: PR-B'yi ac ve canliya al

- [ ] `GEMINI_BATCH_CHARS`/`GEMINI_BATCH_MAX` README tablosu, compose ve helm values'a (`geminiBatchChars`, `geminiBatchMax`).
- [ ] Gercek Gemini ile kuru deneme (memory dersi: "canli kuru calistirma"), canliya almadan once:
  - worktree'deki kodla `docker compose run --rm -v "<worktree>:/app" teknoloji-api python manage.py shell` icinde 5 gercek Libre AI kaydi `paket_cevir`'e verilir, yalniz sonuc yazdirilir (DB'ye yazilmaz)
  - 1 istek harcanir
  - beklenen: 5 kayit da dogrulamadan gecer
- [ ] PR, CI, **merge onayi**, canliya alma, 24 saat sonra spec §6 basari olcutlerini olc ve kullaniciya raporla.

---

## PR-C: Ucretsiz yedek zincir

### Task C1: Saglayici siniflari ve migration

**Files:**
- Create: `news/kayit_cevirmenleri.py` (kayit duzeyi LLM/DeepL cevirmenleri ve `ZINCIR`)
- Modify: `news/gemini.py`:
  - modul fonksiyonlari `GeminiCevirmen(model, onek)` sinifinin ince sarmalayicisi olur
  - birincil `onek='gemini'` (mevcut Redis anahtarlari korunur)
  - ikinci model `onek='gemini2'`
- Modify: `news/models.py` (alti modelde `choices`'a `('openrouter','OpenRouter')`, `('deepl','DeepL')`)
- Create: `news/migrations/0017_translation_provider_yedekler.py` (`makemigrations news -n translation_provider_yedekler`)
- Modify: `cybernews/settings.py` (`OPENROUTER_API_KEY`, `DEEPL_API_KEY` env'den, bos varsayilan; `GuvenliTestRunner` bunlari da bosaltir: `news/test_runner.py`)
- Test: `news/tests/test_kayit_cevirmenleri.py`

**Interfaces:**
- Produces (her cevirmen ayni arayuz):
  - `name: str`: DB degeri (`'gemini'` iki model icin de, `'openrouter'`, `'deepl'`)
  - `hazir() -> bool`: anahtar dolu, devre kesici kapali, sayac tavanin altinda
  - `paket_cevir(kayitlar, bolum=None) -> PaketSonucu`
  - `kaydi_cevir(alanlar, bolum=None) -> Optional[Dict[str,str]]`
  - `butce_ozeti() -> dict`
- `OpenRouterCevirmen`:
  - `POST https://openrouter.ai/api/v1/chat/completions`, `Authorization: Bearer`
  - `response_format={'type':'json_object'}`; ayni `SISTEM_TALIMATI` + paket kurali
  - gunluk istek sayaci (`OPENROUTER_DAILY_BUDGET`, varsayilan uygulama aninda belgeden; hesap durumuna gore), aralik kapisi (`OPENROUTER_MIN_INTERVAL`)
  - `OPENROUTER_MODEL` `:free` ile bitmiyorsa `hazir()` False ve bir kez uyari logu
- `DeepLCevirmen`:
  - `POST https://api-free.deepl.com/v2/translate`, `Authorization: DeepL-Auth-Key`
  - `source_lang=EN`, `target_lang=TR`, cok `text` parametresi (paket = tek istek)
  - aylik karakter sayaci (`DEEPL_MONTHLY_CHARS=450000`, anahtar `deepl:budget:YYYY-MM`), istekten once karakter kadar artar
  - Terim koruma: `translation_utils._protect_terms` / `_restore_terms`. XTRM yer tutucular `tag_handling=xml` + `<x>` etiketi ve `ignore_tags=x` ile sarilir. Uygulayici canli denemede yer tutucu kaybini olcer; kayip varsa yalniz XTRM yolunu kullanir.
- `ZINCIR` sirasi: `GeminiCevirmen(GEMINI_MODEL,'gemini')`, `GeminiCevirmen(GEMINI_FALLBACK_MODEL,'gemini2')` (model bossa atlanir), `OpenRouterCevirmen`, `DeepLCevirmen`.
- `ZINCIR[0]` disindakiler "yedek"tir.

- [ ] **Step 1: Failing testler** (her saglayici icin HTTP mock'lu):
  - `test_anahtar_yoksa_hazir_degil`
  - `test_openrouter_ucretli_model_reddedilir`
  - `test_openrouter_paket_istek_sekli`: url, model, json_object
  - `test_openrouter_bozuk_kayit_yalniz_kendini_dusurur`
  - `test_deepl_aylik_karakter_tavani`
  - `test_deepl_terimler_korunur`: `CVE-2026-1234` ve `libxml2` aynen doner
  - `test_gemini2_ayri_sayac_kullanir`
  - `test_saglik_anahtar_degeri_yanitta_yok`
  - `test_migration_yeni_degerleri_kabul_eder`: `CVEEntry(translation_provider='deepl').full_clean()` hata vermez
- [ ] **Step 2: Kos → FAIL. Step 3: Uygula. Step 4: Kos → PASS** (tum `news`).
- [ ] **Step 5: Commit**: `feat(ceviri): OpenRouter ve DeepL Free cevirmenleri, Gemini ikinci model`

### Task C2: Gercek modellerle secim (kullanicinin anahtarlariyla)

- [ ] Kullanicidan OpenRouter ve DeepL Free hesabini acip anahtarlari `.env`'e girmesini iste. Ajan anahtar degerini gormez ve yazmaz.
- [ ] OpenRouter'in guncel ucretsiz model listesini ve limitlerini, Gemini'nin ucretsiz modellerini ve DeepL Free limitlerini belgelerden dogrula. Bulgulari PR govdesine yaz.
- [ ] Kuru deneme (DB'ye yazmadan):
  - 10 gercek kayit (5 CVE, 5 haber), Gemini ikinci model adayi ve 2–3 OpenRouter `:free` modeli ile `paket_cevir`
  - DeepL ile ayni 10 kayit
  - Her biri icin dogrulamadan gecen kayit sayisi ve yer tutucu kaybi tabloya yazilir
  - En iyi model `GEMINI_FALLBACK_MODEL` / `OPENROUTER_MODEL` varsayilani olur

### Task C3: Retranslate'in zinciri kullanmasi

**Files:**
- Modify: `news/retranslate.py` (Gemini cagrilarinin yerini `_cevirmen_sec(tur, asama)` + secilenin `paket_cevir`/`kaydi_cevir`'i alir; yazilan `translation_provider` secilen `name`)
- Modify: `news/views.py` (`translation_budget` tum cevirmenlerin `butce_ozeti`'ni listeler)
- Modify: `frontend/src/components/CeviriEtiketi.jsx` (rozetler `openrouter`: "Çeviri: OpenRouter", `deepl`: "Çeviri: DeepL"; gri bilgi rozeti), `SaglikSeridi.jsx` (o gun `used > 0` olan yedekleri goster)
- Test: `news/tests/test_retranslate.py` (`YedekZincirTests`), Vitest

**Interfaces:**
- Produces: `retranslate._cevirmen_sec(tur: _Tur, asama: str) -> Optional[cevirmen]`
  - `ZINCIR[0].hazir()` ve `tur.kalan() > 0` ise birincil.
  - Birincil gunluk butceyi bitirmis ya da devre kesicisi acik ise (tur payinin bitmesi DEGIL) sirayla ilk hazir yedek.
  - Pay bitmis ama birincil hazirsa `None`: tur bekler.
  - `asama` `'bekleyen'` ya da `'yukseltme'`; iki asamada da ayni kural, bekleyende `None` → Libre zinciri.

- [ ] **Step 1: Failing testler:**

```python
def test_birincil_hazirsa_yedek_cagrilmaz(self)
def test_birincil_butcesi_bitince_openrouter_kullanilir(self)   # provider 'openrouter'
def test_openrouter_da_yoksa_deepl(self)                        # provider 'deepl'
def test_tur_payi_bitince_yedek_cagrilmaz(self)                 # pay 0, birincil hazir -> hicbir cevirmen cagrilmaz
def test_orta_cve_yedege_gitmez(self)                           # birincil kapali, cvss 5 -> yedekler cagrilmaz, libre kalir
def test_yedek_cevirisi_sonradan_yukseltilmez(self)             # provider 'openrouter' kaydi aday sorgusuna girmez
def test_yedegin_reddettigi_kayit_sonraki_yedege_gider(self)    # openrouter reddedilen {'k0'} -> ayni turda deepl'e
def test_anahtarsiz_kurulum_bugunku_gibi_calisir(self)          # yalniz birincil: A/B testleriyle ayni sonuc
```

- [ ] **Step 2: Kos → FAIL. Step 3: Uygula. Step 4: Kos → PASS** (Django + Vitest + lint).
- [ ] **Step 5: Commit**: `feat(ceviri): yedek zincir retranslate'e baglandi`

### Task C4: PR-C'yi ac ve canliya al

- [ ] Belgeler:
  - README ortam degiskenleri (`GEMINI_FALLBACK_MODEL`, `OPENROUTER_*`, `DEEPL_*`)
  - `.env.example` (bos degerler)
  - helm `secret.yaml`/`values.yaml` (`openrouterApiKey`, `deeplApiKey`, varsayilan bos)
  - ADR-0004'e ek not: yeni `translation_provider` degerleri, v1 tuketicisi icin eklemeli degisiklik
- [ ] PR, CI, **merge onayi**.
- [ ] Canliya alma sirasi: once `migrate` (canli DB), sonra kod (pull + restart).
- [ ] Dogrulama:
  - `/api/saglik/` `translation_budget` uc saglayiciyi listeler
  - Gemini anahtari gecici olarak bozulmadan yedege dusus kuru denemede gosterilir (canli kotaya dokunmadan, `paket_cevir` dogrudan)
