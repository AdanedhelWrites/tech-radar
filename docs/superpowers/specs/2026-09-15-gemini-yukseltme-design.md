# Gemini ile Kayit Duzeyinde Ceviri Yukseltme — Tasarim Dokumani

- **Tarih:** 2026-09-15
- **Durum:** Onaylandi (2026-09-15, tasarim sohbette onaylandi; uygulama bekliyor)
- **Kapsam:** Google Translate kazima yolunun kaldirilmasi; cekim aninda yalniz LibreTranslate; `retranslate_pending`'in bekleyen ve LibreTranslate kayitlarini Gemini API ile kayit duzeyinde (tek istek) yukseltmesi; her kayitta saglayici rozeti
- **Kapsam disi:** Cekim aninda Gemini; `google` kayitlarinin yukseltilmesi; Helm/Kubernetes (Faz B); ucretli katman
- **Iliskili:** [ADR-0004](../../ADR-0004-Ceviri-Saglayici-Zinciri.md) (saglayici zinciri), `2026-09-14-ceviri-saglayici-zinciri-design.md` (retranslate iki asama), A3 plani (dogrulama)
- **Siralama:** A4'ten once uygulanir (A4'un `FetchRun.by_provider` alani saglayici seti netlesince anlamli)

## 1. Amac

Haberlerin **anlasilir** Turkce gelmesi. 2026-09-14/15 bulgulari:

- LibreTranslate (argos en→tr) cikti kirpmiyor ama anlam bozuyor: eksik kelime ("A security vulnerability has been detected" → "tespit edilmistir"), uydurma ozel ad (RouterOS → "KLMOS"), yer tutuculu parcayi yari Ingilizce birakma. Parcalama ve terim korumasi elendi; sorun modelin kendisi. 1305 kaydin 978'i (%75) bu kalitede.
- Google Translate'in resmi olmayan uclari (`/m`, `translate_a/single`) bu IP'den once TLS parmak iziyle, sonra hacimle (`/sorry/` CAPTCHA) bloklaniyor. `curl_cffi` ile kapi aciliyor ama 150 istek/3.5 dk'da yeniden kapaniyor; devre kesici her 20 dk'da 3 istekle blogu tazeliyor. Surdurulebilir degil, kaynak sayisi arttikca kotulesir.
- Resmi ucretsiz NMT katmanlari hacmi kaldirmiyor (gunluk ~213k karakter, ~6.4M/ay; DeepL/Google Cloud 500k, Azure 2M/ay).

Cozum: **Gemini API ucretsiz katmani** — karakter degil istek sinirli, LLM cevirisi baglami anladigi icin ozel ad ve guvenlik terimlerini korur.

### 1.1 Kota gercegi (kullanicinin AI Studio hesabi, 2026-09-15)

| Model | RPM | TPM | RPD |
|---|---|---|---|
| `gemini-3.5-flash-lite` | 15 | 250K | **500** |
| `gemini-3.6-flash` | 5 | 250K | 20 |

Gunluk ~170 kayit geliyor. Metin basina istek (baslik + aciklama ayri) 340+ istek/gun ile sinira dayanir; **kayit basina tek istek** zorunludur. Bu, Gemini'yi alti scraper'in metin bazli zincirine sokmak yerine yalnizca `retranslate`'te kayit duzeyinde kullanma kararini dogurdu.

### 1.2 Basari kriterleri

1. Yeni kayit cekim aninda Turkce gorunur (LibreTranslate, rozetli); en gec 2 saat icinde Gemini kalitesine yukselir.
2. 978 LibreTranslate kaydi birkac gun icinde Gemini ile yeniden cevrilir; LibreTranslate'in yer tutucu dusurdugu icin bekleyen kalan kayitlar kapanir.
3. Gemini kotasi hicbir kosulda asilmaz; kota/servis dusunce sistem LibreTranslate ile calismaya devam eder, Turkce kesilmez.
4. Google'a bir daha hicbir istek gitmez.
5. Kullanici her kayitta hangi saglayicinin cevirdigini gorur.

## 2. Secilen Yaklasim

**Cekim aninda LibreTranslate, `retranslate`'te Gemini.** Scraper'lara dokunulmaz; Gemini tek yerde (`news/gemini.py`) ve tek cagri noktasinda (`news/retranslate.py`) yasar.

Elenen alternatifler:

| Alternatif | Neden elendi |
|---|---|
| Gemini'yi metin bazli `SAGLAYICILAR` zincirine eklemek | Kayit basina 2+ istek → 500 RPD'ye sigmaz; alti scraper'in cagri yapisi degismeden kayit duzeyinde paketleme yapilamaz |
| Google gtx → Gemini → LT | Google yolu blok dongusunu ve `curl_cffi` bagimliligini geri getirir; Gemini zaten Google kalitesinde |
| Yerel LLM (Ollama) | GPU yok; CPU'da gunluk ~3-4 saat islemci. Kullanici buyuk yapi istemedi |
| Daha buyuk yerel NMT (NLLB, MADLAD) | Kalite Google/LLM seviyesine cikmaz; ayni ozel ad/anlam sorunlari azalir ama bitmez |

## 3. Bilesenler

### 3.1 `news/translation_providers.py` ve `news/translation_utils.py` (degisir)

- `SAGLAYICILAR = (LibreTranslateProvider(),)`. `GoogleProvider` silinir.
- `translation_utils`: `GtxTranslator`, `_make_translator`, `_translate_via_google`, `ERROR_KEYWORDS`, `RETRY_DELAYS`, `MIN_INTERVAL`, `COOLDOWN_SECONDS`, Google devre kesicisi (`_gate`, `_get_gate`) ve `yalnizca_saglayicilar` kaldirilir. `_RedisGate` / `_LocalGate` siniflari kalir (LibreTranslate ve Gemini kullanir).
- `translate_text` zinciri, terim korumasi, onarma, A3 dogrulamasi, `consume_translation_failures/providers`, `kayit_saglayicisi`, `translate_long_text` **degismez**.
- `requirements.txt`: `curl_cffi` cikar. Yeni pip bagimliligi yok (`requests` yeterli).

### 3.2 `news/gemini.py` (yeni)

Tek genel fonksiyon:

```python
def kaydi_cevir(alanlar: Dict[str, str]) -> Optional[Dict[str, str]]
```

`alanlar` ornegin `{'title': ..., 'description': ...}` (yalniz cevrilecek alanlar; CVE'de yalniz `description`). Donus: ayni anahtarlarla Turkce metinler; `None` = cevrilemedi (neden loglanir).

| Konu | Karar |
|---|---|
| Uc nokta | `POST https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent`, baslik `x-goog-api-key` |
| Model | `GEMINI_MODEL`, varsayilan `gemini-3.5-flash-lite` |
| Yanit bicimi | `generationConfig.responseMimeType = application/json` + `responseSchema` (girdi anahtarlariyla ayni string alanlar). Yanit `candidates[0].content.parts[0].text` → `json.loads` |
| Prompt | Sistem talimati: Ingilizce teknik haber metnini Turkceye cevir; teknik terimleri, urun/kutuphane/sirket/kisi adlarini, kod, dosya yollari, fonksiyon adlari, CVE/surum/commit numaralarini **aynen** birak; satir sonlarini, madde isaretlerini ve `===SECTION:` gibi yapisal isaretleri koru; ozetleme/ekleme yapma; yalniz JSON dondur. Kullanici mesaji: JSON girdi |
| Yer tutucu | **Yok.** `XTRM` korumasi LLM'de gereksiz; terimler prompt'la korunur |
| Dogrulama (alan basina) | Bos degil; uzunluk orani ≥ `TRANSLATE_MIN_RATIO` (0.4, mevcut ayar) ve ≤ 3.0; girdiyle (bosluk/buyuk-kucuk normalize) ayni degil — girdi ≥ 4 kelime ise. Herhangi bir alan gecemezse **tum kayit** `None` (hepsi-ya-da-hicbiri) |
| Post-process | `turkish_post_process` uygulanmaz (LLM ciktisi zaten duzgun; cumle basi buyutme `kubectl → Kubectl` sorununu tasimayalim) |
| Zaman asimi | `GEMINI_TIMEOUT`, varsayilan 60 sn |
| Hiz | Redis paylasimli aralik kapisi (`_RedisGate`, onek `gemini`): istekler arasi en az `GEMINI_MIN_INTERVAL` sn (varsayilan 5 → en fazla 12/dk < 15 RPM) |
| Gunluk butce | Redis sayaci `gemini:budget:<UTC tarih>` (TTL 48 sa), `GEMINI_DAILY_BUDGET` varsayilan **400** (< 500 RPD, Beat disi manuel kullanim icin pay). Her istek **oncesi** `INCR`; sinir asilmissa istek atilmaz, `butce_var() == False`. 4xx yanitta (istek Google tarafinda sayilmadi) `DECR` ile geri alinir |
| Hata siniflari | Baglanti hatasi / zaman asimi / **429** / 5xx → `None` + devre kesici `GEMINI_COOLDOWN` (varsayilan 600 sn). 4xx (400 gecersiz istek, 401/403 anahtar) → `None`, devre kesici **acilmaz**, hata govdesi loglanir (anahtar sorunu gorulur). JSON ayristirilamiyor / anahtar eksik / `finishReason` `SAFETY` vb. → `None`, devre kesici acilmaz |
| Hazirlik | `hazir()`: `GEMINI_API_KEY` dolu **ve** devre kesici kapali **ve** gunluk butce var |
| Dis sozlesme | Hicbir istisna disari cikmaz; `None` doner |

### 3.3 `news/retranslate.py` (degisir)

Bolum basina "Gemini alanlari" hazirlayan kucuk fonksiyonlar (mevcut `_cve`, `_kubernetes`, `_baslik_ve_uzun_aciklama` yaninda):

| Bolum | Gemini'ye giden alanlar | Not |
|---|---|---|
| news, sre, devtools, ai | `title`, `description` (orijinal bos ise alan gonderilmez — 2026-09-15 haber kurali) | |
| cve | yalniz `description`; 30 karakterden kisa ise Gemini'ye gitmez, kayit Gemini adayi degildir | baslik cevrilmez (mevcut kural) |
| kubernetes | `title`, `description` — `===SECTION:` yapili changelog tek metin olarak, yapiyi koru talimatiyla | `_translate_structured_changelog` LT yolunda kalir |

**Asama 1 — Bekleyenler** (`needs_translation=True`): kayit once `gemini.kaydi_cevir` ile denenir; basari → `_yaz(kayit, alanlar, 'gemini')`. `None` ise mevcut zincir (`cevir(kayit)` → LibreTranslate) ile bugunku gibi. Gemini `hazir()` degilse (anahtar yok / devre kesici / butce bitti) dogrudan zincire duser — asama durmaz.

**Asama 2 — Yukseltme** (`needs_translation=False, translation_provider='libretranslate'`): yalniz Gemini. `yalnizca_saglayicilar('google')` kaldirilir. Basari → `'gemini'`, `updated_at` ilerler (tuketici delta akisindan alir). `None` → kayda yazilmaz, imlec ilerler (bir sonraki turda sira baskasinda; tur sonunda bastan). Gemini `hazir()` degilse asama baslamaz; butce asama ortasinda biterse durur, imlec ilerletilmez. Bolum basina sinir `RETRANSLATE_UPGRADE_BATCH` **5 → 40** (6 bolum × 40 = 240 istek/tur tavani; gunluk butce asil sinir).

Donus degeri: `by_provider` `{'gemini': n, 'libretranslate': n}` (Google anahtari kalkar); `upgraded` Gemini yukseltmeleri; yeni `stopped_reason`: `None | 'no_provider' | 'gemini_budget'`. `stopped` anlamini korur (hicbir saglayici yok).

Beat takvimi degismez (`crontab(minute=5, hour='1-23/2')`). Butce 400/gun, 12 tur/gun → tur basina ~33 istek dogal ortalama; birikim ilk gunlerde butceyi doldurur, sonra gunluk ~170 yeni kayit + bekleyenler rahat siger.

### 3.4 Veri modeli ve API

- Alti modelde `translation_provider` `choices`'a `('gemini', 'Gemini')` eklenir → migration `0010_translation_provider_gemini` (yalniz `AlterField`, sema/veri degismez; worker durdurma gerekmez).
- v1 API ve `/api/*` serializer'lari alani zaten donduruyor; deger kumesi `null | google | libretranslate | gemini`. v1 sozlesmesi genisler, kirilmaz.
- Mevcut 256 `google` kaydi dokunulmaz; `google` etiketi kalir.

### 3.5 Frontend — `CeviriEtiketi`

`frontend/src/components/MakineCevirisiEtiketi.jsx` → `CeviriEtiketi.jsx` (ve `ceviriEtiketiHtml`). 18 kullanim noktasi ad degisikligiyle guncellenir; davranis:

| `translation_provider` | Rozet | Renk | Baslik (title) |
|---|---|---|---|
| `libretranslate` | "Makine çevirisi: LibreTranslate" | `warning` (sari) | "Yerel LibreTranslate ile çevrildi; anlam hatası olabilir. En geç 2 saat içinde Gemini ile iyileştirilir." |
| `gemini` | "Çeviri: Gemini" | `secondary` (gri) | "Gemini (gemini-3.5-flash-lite) ile çevrildi." |
| `google` | "Çeviri: Google" | `secondary` | "Google Translate ile çevrildi." |
| bos / null | rozet yok | — | (Ingilizce veya ceviri bekliyor) |

Frontend kullanici metinleri Turkce karakterli (mevcut kalip).

### 3.6 Gelistirme ortami (frontend, ayni iste)

Frontend'e zaten dokunuldugu icin iki kucuk gelistirme-ortami duzeltmesi bu ise dahildir (`frontend/vite.config.js`):

- **`/admin` dev'de calismiyor:** Vite proxy'si yalniz `/api`'yi backend'e geciriyor; `localhost:3000/admin` React'in bos sayfasina dusuyor (backend `localhost:8000/admin/` ve prod `nginx.conf` dogru). `/admin` ve `/static` proxy'ye eklenir.
- **HMR:** Windows Docker bind mount dosya olayi uretmedigi icin Vite degisiklikleri gormuyor; `server.watch.usePolling = true` eklenir (yalniz dev, kucuk CPU maliyeti).

### 3.7 Dagitim

- `docker-compose.yml`: `teknoloji-api` ve `teknoloji-worker` ortamina `GEMINI_API_KEY=${GEMINI_API_KEY}` (scheduler'a degil; ceviri yapmaz). Deger `cybersecurity_news/.env`'den okunur (gitignore'da; 2026-09-15'te yerine kondu). Anahtar repoya, loga, hata mesajina girmez.
- `requirements.txt`'ten `curl_cffi` cikar → imaj yeniden kurulur (`docker compose build`), api/worker/scheduler `--force-recreate` (ortam degiskeni degisiyor; `restart` yeni ortami almaz).
- Migration 0010 sema degistirmez; yine de alışkanlik olarak worker/scheduler durdurulup migrate edilir.
- Geri donus: onceki imaj etiketi + `git revert`; migration geri alma zararsiz.

### 3.8 Guvenlik ve veri

- Anahtar yalniz ortam degiskeni; `GuvenliTestRunner` testlerde `GEMINI_API_KEY`'i bosaltir ve Gemini devre kesicisini surec ici tutar.
- Gonderilen veri kamuya acik haber/CVE metni; ucretsiz katmanda Google verisi urun gelistirmede kullanabilir (kullanici kabul etti).
- Kota asimi maddi risk tasimaz (kart bagli degil).

## 4. Veri Akisi

```
Beat fetch (6 saatte bir)      → scraper → translate_text (LibreTranslate) → kayit 'libretranslate' (rozet sari)
                                                   cevrilemedi → orijinal, needs_translation=True

Beat retranslate (2 saatte bir, tek saatler :05)
  her bolum:
    asama 1 bekleyenler   → gemini.kaydi_cevir → ok: 'gemini' | None: LibreTranslate zinciri
    asama 2 libretranslate → gemini.kaydi_cevir → ok: 'gemini', updated_at ilerler | None: dokunma
  butce/devre kesici bitince: asama durur, stopped_reason yazilir, sonraki turda devam
```

## 5. Hata Durumlari

| Durum | Davranis |
|---|---|
| `GEMINI_API_KEY` yok | Gemini hic denenmez; sistem bugunku gibi (LibreTranslate) calisir |
| 429 / 5xx / ag / zaman asimi | 10 dk devre kesici; asama durur, LT zinciri bekleyenler icin devam eder |
| 401/403 (anahtar) | Loglanir, devre kesici acilmaz, kayit `None`; her turda 1 istekle fark edilir (butceden dusmez: sayac istek oncesi artar ama 4xx'te geri alinir) |
| Gunluk butce bitti | O gun Gemini kullanilmaz; ertesi UTC gun sayac sifirlanir |
| JSON bozuk / alan eksik / safety | `None`, imlec ilerler, kayit sonraki turda tekrar denenir |
| Dogrulama basarisiz | `None`; LibreTranslate'te kalan kayit rozetli kalir |

## 6. Test Plani

Hicbir test gercek Gemini'ye, LibreTranslate'e veya Redis'in canli anahtarlarina dokunmaz. Gemini HTTP'si `mock.patch('news.gemini.requests.post')` ile.

| Dosya | Kapsam |
|---|---|
| `test_gemini.py` (yeni) | Istek sekli (uc, baslik, model, JSON modu, girdi anahtarlari), yanit ayristirma, dogrulama (bos/oran/ayni), 429 → devre kesici, 401 → devre kesici acilmaz + butce geri alinir, butce sayaci ve gunluk anahtar, aralik kapisi, anahtar yoksa `hazir()` False, istisna sizmaz |
| `test_retranslate.py` (degisir) | Asama 1 Gemini-once/LT-yedek; asama 2 yalniz Gemini, hepsi-ya-da-hicbiri, `None`'da yazilmaz; butce bitince `stopped_reason='gemini_budget'` ve imlec korunur; `by_provider` yeni sekli; CVE kisa aciklama Gemini'ye gitmez; K8s `===SECTION:` metni tek alan olarak gider |
| `test_haber_aciklamasi.py` | Orijinal bos alan Gemini'ye gonderilmez |
| `test_translation_providers.py`, `test_translation_chain.py`, `test_translation.py` | Google'a dayanan testler silinir veya LT'ye uyarlanir; `FakeTranslator`/`_make_translator` mock noktasi kalkar |
| `test_google_gtx.py` | Silinir |
| Frontend | `CeviriEtiketi` uc saglayici + bos durum (Vite build yesil; birim test altyapisi yoksa eklenmez) |

## 7. Canli Dogrulama Hedefleri

1. Imaj yeniden kuruldu, `deep_translator`/`curl_cffi` yok, `check` temiz, testler yesil.
2. Worker'da `gemini.hazir() == True`; tek kayitlik elle deneme Gemini'den JSON dondu, dogrulamadan gecti.
3. Bir retranslate turunda `by_provider.gemini > 0`, `upgraded > 0`; Redis butce sayaci istek sayisiyla eslesiyor; Google'a giden istek 0.
4. Frontend'de uc rozet dogru; v1'de `translation_provider: "gemini"`.
5. 24 saat sonra: LibreTranslate kayit sayisi dususte, butce hic asilmadi (`gemini:budget:*` ≤ 400).

## 8. Kapsam Disi ve Sonraki Isler

- **A4:** `FetchRun.by_provider` `gemini`/`libretranslate`; `/api/v1/status/` icine `gemini: {budget_used, budget_limit, circuit_open}`.
- **A5:** README'ye `GEMINI_*` degiskenleri, kota ve rozetler; ADR-0004'e "Google kaldirildi, Gemini yukseltme" eki (ADR-0005 gerekmez, ayni kararin evrimi).
- Faz B: Helm secret'a `GEMINI_API_KEY`.
- `turkish_post_process`'in `kubectl → Kubectl` sorunu (A3'ten kalan) yalniz LT yolunda kalir; Gemini ciktisina uygulanmadigi icin etkisi azalir.
