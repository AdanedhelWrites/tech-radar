# Ceviri Saglayici Zinciri — Tasarim Dokumani

- **Tarih:** 2026-09-14
- **Durum:** Onaylandi (spec incelemesi bekliyor)
- **Kapsam:** Google Translate'in yanina yerel LibreTranslate servisini yedek saglayici olarak eklemek; kaydin hangi saglayiciyla cevrildigini saklamak ve Google acildiginda dusuk kaliteli cevirileri yukseltmek
- **Kapsam disi:** Helm chart (Faz B), Opus-MT gibi alternatif modeller, ucretli API'ler
- **Iliskili:** `2026-09-12-entegrasyon-api-v1-design.md` (bolum 9 — ceviri dogrulugu); A3 plani (`retranslate_pending`)
- **Siralama:** A3 ile A4 arasinda uygulanir

## 1. Amac

Haberlerin Turkce gelmesi bu projenin temel vaadi. 2026-09-12 ile 2026-09-14 arasinda bu vaat karsilanmadi:

| Olcum (2026-09-14) | Deger |
|---|---|
| Son 2 gunde eklenen kayit | 283 |
| Bunlardan cevrilen | 2 (%0.7) |
| Ceviri bekleyen kayit | 384 → 622 (1035 kaydin %60'i) |
| Google'in cevabi | "You made too many requests to the server" |
| Devre kesici acilma sayisi (2 gun) | 31 |
| `retranslate_pending_task` calismasi | 10, hepsinde 0 ceviri |

A3'teki mekanizmalar dogru calisiyor — Google'i zorlamiyor, bozuk ceviriyi kaydetmiyor — ama ucretsiz Google ucu bu IP icin fiilen kapali. Butce yok.

### 1.1 Basari kriterleri

1. Google kapaliyken yeni gelen haber, cekim sirasinda Turkceye cevrilir; `needs_translation` yalnizca hicbir saglayici calismadiginda isaretlenir.
2. Mevcut 622 bekleyen kayit, dagitimdan sonraki ilk birkac `retranslate_pending_task` calismasinda erir.
3. Her kaydin hangi saglayiciyla cevrildigi bilinir ve API'de, frontend'de gorunur.
4. Google yeniden erisilebilir oldugunda LibreTranslate cevirileri kendiliginden Google cevirileriyle degistirilir ve tuketiciye delta akisindan gider.
5. LibreTranslate servisi dustugunde sistem bugunku davranisa (yalniz Google) geriler; hicbir cekim veya API cagrisi bu yuzden basarisiz olmaz.

## 2. Deneme Bulgulari (2026-09-14)

Atilacak bir konteynerde `libretranslate/libretranslate:v1.9.6`, yalnizca `en,tr` modelleriyle calistirildi. Mevcut ceviri hatti (terim koruma, yer tutucu onarma, A3 dogrulamasi, Turkce duzeltmeler) degistirilmeden yalnizca Google'in yerine LibreTranslate konuldu.

### 2.1 Kaynak ve hiz

| Olcum | Deger |
|---|---|
| Sikistirilmis imaj (CPU) | ~0.2 GB; acildiginda 600 MB |
| Modeller | Imajda yok; ilk acilista iner, `/home/libretranslate/.local/share/argos-translate` altinda 258 MB |
| Acilis | ~26 sn (modeller dahil) |
| Bellek | Bosta 237 MB; 8 paralel uzun istekte en fazla 1.14 GB |
| CPU | 8 paralel istekte 12 cekirdegin tamamini doyurdu |
| Hiz | Tek istemci ~753 karakter/sn; 8 paralel ~3900 karakter/sn |
| Bekleyen birikim | ~1.0M karakter → tek istemciyle ~22 dk |

### 2.2 Yer tutucu korumasi

Ayni 60 gercek metin (en az 2 yer tutucu iceren basliklar ve aciklamalarin ilk 700 karakteri):

| Yontem | Kayip | Dogrulamaya takilan metin |
|---|---|---|
| `XTRM0001X`, bolmeden | 14 / 297 | 10 / 60 |
| Kisa kod `Z1Z` | 15 / 297 | 8 / 60 |
| Koruma yok (ham terim) | 103 / 297 terim | 24 / 60 |
| HTML `translate="no"` / `<code>` | terimler korundu | kalite cok kotu (cumle parcalaniyor, kelime tekrari) |
| Cumle sinirindan bolme | 16 / 297 | 10 / 60 |
| **`XTRM` + en fazla 160 karakterlik parcalar** | **4 / 297** | **4 / 60** |
| `XTRM` + en fazla 90 karakterlik parcalar | 4 / 297 | 4 / 60 |

Kayiplar uzun, noktalamasi zayif bolumlerde (orn. noktasiz "Table of Contents …" listeleri) toplaniyor. Parcalama bunu buyuk olcude kapatiyor.

### 2.3 Tanimlayici korumasi

LibreTranslate alt cizgiyi siliyor: `parse_array` → `parse array`, `tribe_events` → `tribe events`. CVE aciklamalari bu tur tanimlayicilarla dolu. Alt cizgili tanimlayicilar ve `ad()` / `A::b()` cagrilari yer tutucuyla korununca bir ornekte 0/3 → 3/3.

### 2.4 Kalite

8 gercek kayit, Google'in eski cevirileriyle yan yana karsilastirildi. Hicbiri A3 dogrulamasina takilmadi. Kalite Google'dan belirgin sekilde dusuk ve **anlam hatalari mekanik degil**, dogrulama bunlari yakalayamaz:

- Ozel adlar uyduruluyor: ayni haberde bir sirket adi iki farkli yanlis kelimeye donustu; bir kisi adi baska bir ada donustu.
- Guvenlik anlami bozuluyor: "unauthenticated attackers" → "terk edilmis saldirganlar"; "executed remotely" → "uzaktan idam edilebilir".
- Kisa ve basit metinler (SRE, DevTools, bazi CVE'ler) anlasilir.

Bu bulgu saglayici sirasi kararini degistirdi: LibreTranslate ana saglayici degil, **Google kapaliyken devreye giren yedek** olur ve urettigi ceviri etiketlenip sonradan yukseltilir.

## 3. Secilen Yaklasim

**`translation_utils` icinde sirali saglayici zinciri.** Her metin icin: Google → LibreTranslate → orijinal metin.

Elenen alternatifler:

- **Ayri ceviri servisi ve kuyrugu:** Yeni bir hareketli parca; mevcut Celery gorevleri zaten kuyruk.
- **Okuma aninda ceviri:** API gecikmesi artar, v1'in "kayit degisince `updated_at` ilerler" sozlesmesi bozulur.
- **LibreTranslate ana, Google yedek:** Ilk karar buydu; kalite bulgusu (2.4) sonrasi degistirildi.

## 4. Bilesenler

### 4.1 `news/translation_providers.py` (yeni)

Her saglayici ayni arayuzu uygular:

| Uye | Anlam |
|---|---|
| `name: str` | `'google'` veya `'libretranslate'` — veritabanina yazilan deger |
| `available() -> bool` | Simdi denenebilir mi (yapilandirilmis mi, devre kesicisi kapali mi) |
| `translate(protected: str) -> Optional[str]` | Terimleri korunmus metni cevirir; erisilemezse `None` |

**`GoogleProvider`** — Bugun `translation_utils` icindeki `_translate_via_google` mantigi aynen tasinir: Redis ortak hiz siniri (`MIN_INTERVAL`), `RETRY_DELAYS` ile yeniden deneme, `COOLDOWN_SECONDS` devre kesici, hata sayfasi anahtar kelimeleri. `available()` devre kesici kapaliysa `True`.

**`LibreTranslateProvider`**:

- `LIBRETRANSLATE_URL` ortam degiskeni tanimli degilse `available()` her zaman `False` (testler ve LibreTranslate'siz kurulumlar bugunku gibi calisir).
- Metni en fazla `LIBRETRANSLATE_CHUNK_CHARS` (varsayilan 160) karakterlik parcalara boler: once satirlara, her satiri cumle sonlarina, cumle hala uzunsa sinirdan onceki son virgul veya bosluktan. Bos olmayan tum parcalar tek bir `POST /translate` isteginde `q` listesi olarak gonderilir (`source=en`, `target=tr`, `format=text`).
- Birlestirme satir yapisini korur: ayni satirin parcalari tek boslukla, satirlar `\n` ile birlestirilir; bos satirlar cevrilmeden yerinde kalir. Donen liste uzunlugu gonderilenle eslesmezse cevap gecersiz sayilir (`None`, devre kesici acilmaz).
- Zaman asimi `LIBRETRANSLATE_TIMEOUT` (varsayilan 60 sn).
- Baglanti hatasi, zaman asimi veya 5xx: `None` doner ve kendi Redis devre kesicisini `LIBRETRANSLATE_COOLDOWN` (varsayilan 60 sn) boyunca acar. Yeniden deneme yapmaz; yerel servis dusmusse bekleyip tekrar denemek cekimi yavaslatir.
- Hiz siniri yoktur; eszamanlilik compose'daki CPU siniriyla dogal olarak sinirlanir.

### 4.2 `translation_utils.translate_text` (degisir)

```
korunmus, esleme = _protect_terms(metin)
her saglayici icin (sirayla):
    available() degilse atla
    ceviri = saglayici.translate(korunmus)
    None ise sonraki saglayiciya gec
    onar → dogrula (A3) → geri koy → kalinti kontrolu
    sorun varsa sonraki saglayiciya gec
    basari: saglayici adini kaydet, turkish_post_process(sonuc) dondur
hicbiri basarili olmadiysa: basarisizlik sayacini artir, orijinali dondur
```

- A3 sozlesmesi korunur: cevrilemeyen metin orijinal haliyle doner, `consume_translation_failures()` artar.
- A3'teki "dogrulama hatasi yeniden deneme ve devre kesici tetiklemez" kurali saglayici icinde gecerli kalir; zincirde yalnizca bir sonraki saglayiciya gecilir.
- Yeni: `consume_translation_providers() -> set[str]` — son cagridan beri basariyla kullanilan saglayici adlari; cagrilinca sifirlanir. Task'lar ve retranslate kayit duzeyindeki saglayiciyi bundan hesaplar.
- Yeni: `translate_text(metin, providers=None)` — `providers` verilirse yalnizca o isimdeki saglayicilar denenir (yukseltme asamasi `['google']` verir).

### 4.3 Terim korumasina tanimlayicilar

`_protect_terms` icine, surum numarasi adimindan once iki desen eklenir:

- `ad()`, `Sinif::metod()`, `a.b()` bicimindeki cagrilar
- En az bir alt cizgi iceren tanimlayicilar (`parse_array`, `tribe_events`, `pg_stat_lock`)

Bu Google cevirilerini de iyilestirir (Google da bu tanimlayicilari zaman zaman bolup cevirir).

### 4.4 Kayit duzeyinde saglayici

| Kaydin parcalarinda kullanilan saglayicilar | `translation_provider` |
|---|---|
| En az bir parca `libretranslate` | `'libretranslate'` |
| Yalnizca `google` | `'google'` |
| Hic ceviri basarili olmadi | `''` |

Kaydin en dusuk kaliteli parcasi belirleyicidir; yukseltme adayi olmasi icin bir parcanin LibreTranslate'le cevrilmis olmasi yeter.

`needs_translation` kurali degismez: kaydin herhangi bir parcasi cevrilemediyse `True`.

## 5. Veri Modeli

Alti modele:

```python
translation_provider = models.CharField(
    max_length=20, blank=True, default='',
    choices=[('google', 'Google'), ('libretranslate', 'LibreTranslate')],
    verbose_name='Ceviri Saglayicisi')
```

**Migration 0009** iki adimdir:

1. `AddField` (alti model)
2. Veri migration'i: `needs_translation=False` olan kayitlar `'google'` olarak isaretlenir. Gerekce: 2026-09-14'e kadar sistemdeki tek saglayici Google'di. `needs_translation=True` kayitlar `''` kalir. Geri alma islemi alani bosaltir. Bilinen kucuk yanlislik: aciklamasi 30 karakterden kisa oldugu icin hic cevrilmemis CVE'ler de `google` gorunur; bu kayitlarda cevrilecek metin olmadigi icin zararsizdir ve yukseltme adayi olmazlar.

Veri migration'i `QuerySet.update()` kullanir; `updated_at` ilerlemez, tuketicinin delta akisina 1035 kayit birden dusmez.

**Dagitim notu:** Migration sonrasi `teknoloji-api`, `teknoloji-worker` ve `teknoloji-scheduler` yeniden baslatilmadan hicbir Celery gorevi calismamalidir (2026-09-12 regresyonu). Plan bunu ayri bir adim olarak icerir.

## 6. Veri Akisi

### 6.1 Fetch task'lari

Degisiklik minimal: her kayittan once `consume_translation_providers()` sifirlanir, kayit yazilirken `defaults` icine hesaplanan `translation_provider` eklenir. `needs_translation` hesabi aynen kalir.

### 6.2 `retranslate_pending` — iki asama

Her calismada alti bolum icin sirasiyla:

**Asama 1 — Bekleyenler** (`needs_translation=True`)

- Tam zincirle cevrilir.
- Bolum basina sinir `RETRANSLATE_BATCH` varsayilani **8 → 100** (LibreTranslate hizli; 622 kayit ilk birkac calismada erir).
- **Durma kosulu degisir:** Artik Google devre kesicisi degil, **hicbir saglayicinin `available()` olmamasi**. Google kapali ama LibreTranslate aciksa gorev devam eder.
- Imlec kurallari A3'teki gibidir; "erisim hatasi" artik "hicbir saglayici yok" demektir.
- Basari: Turkce alanlar, `needs_translation=False`, `translation_provider`, `updated_at` yazilir.

**Asama 2 — Yukseltme** (`needs_translation=False` ve `translation_provider='libretranslate'`)

- Yalnizca Google `available()` ise calisir.
- Bolum basina sinir `RETRANSLATE_UPGRADE_BATCH` (varsayilan 5) — ucretsiz Google kotasini korumak icin.
- `translate_text(..., providers=['google'])` ile cevrilir. Kaydin **tum** parcalari Google'la cevrilebildiyse kayit guncellenir: Turkce alanlar, `translation_provider='google'`, `updated_at` ilerler → tuketici daha iyi ceviriyi delta akisindan alir.
- Herhangi bir parca basarisizsa kayda **hic yazilmaz**; LibreTranslate cevirisi yerinde kalir, `needs_translation` degismez.
- Google devre kesicisi asama ortasinda acilirsa asama durur.
- Kendi imleci vardir: `{prefix}:upgrade-cursor:{bolum}`.

Donus degeri genisler:

```python
{'translated': int, 'failed': int, 'upgraded': int,
 'stopped': bool,          # hicbir saglayici yoktu (A3'teki stopped_by_cooldown'un yerine)
 'by_provider': {'google': int, 'libretranslate': int},
 'sections': {bolum: {'translated': int, 'failed': int, 'upgraded': int}}}
```

### 6.3 Beat

Takvim degismez (`crontab(minute=5, hour='1-23/2')`).

## 7. API ve Frontend

### 7.1 v1

`BaseEntrySerializer.ORTAK_ALANLAR` listesine `translation_provider` eklenir. Deger `'google'`, `'libretranslate'` veya `null` (bos string `null`'a cevrilir). Ekleme mevcut tuketicileri kirmaz.

### 7.2 `/api/*`

Serializer'lar `fields = '__all__'` kullandigi icin alan otomatik gelir. Cache blob sekli degistigi icin `CACHES['default']['VERSION']` **2 → 3** yapilir (A3 netlestirme 12).

### 7.3 Frontend

Alti bilesende, `translation_provider === 'libretranslate'` olan kayitlarin listesinde ve detay modalinda kucuk bir react-bootstrap `Badge`:

- Metin: `Makine cevirisi`
- Stil: `bg="warning" text="dark"`
- `title` ozniteligi (uzerine gelince): `LibreTranslate ile cevrildi. Google erisilebilir oldugunda otomatik olarak iyilestirilecek; anlam hatasi olabilir, orijinal metne bakin.`

`CVEComponent` icindeki HTML disa aktarma sablonu da ayni etiketi tasir.

## 8. Dagitim

`docker-compose.yml` icine yeni servis:

| Ayar | Deger | Gerekce |
|---|---|---|
| Servis / konteyner adi | `teknoloji-translate` | Mevcut adlandirma |
| Imaj | `libretranslate/libretranslate:v1.9.6` | Surum sabit; `latest` degil |
| Ortam | `LT_LOAD_ONLY=en,tr`, `LT_UPDATE_MODELS=false` | Yalnizca gereken modeller; acilista model guncellemesi yok |
| Volume | `teknoloji-translate-models:/home/libretranslate/.local` | Modeller imajda yok; kalici volume olmazsa her yeniden olusturmada 258 MB iner ve internet yoksa servis acilmaz |
| Kaynak siniri | `cpus: '4'`, `mem_limit: 2g` | Denemede yuk altinda 12 cekirdegi doyurdu; diger servisleri ac birakmasin |
| Port | Disari acilmaz | Yalnizca ic ag; kimlik dogrulamasi yok |
| Healthcheck | `/languages` uc noktasi, 30 sn aralik, 120 sn baslangic payi | Ilk acilista model indirmesi |
| Ag | `teknoloji-network` | |

`teknoloji-api` ve `teknoloji-worker` ortamina `LIBRETRANSLATE_URL=http://teknoloji-translate:5000` eklenir. `depends_on` **eklenmez**: LibreTranslate yedek saglayicidir, acilmamis olmasi api veya worker'in baslamasini engellememelidir (basari kriteri 5).

**Helm:** Bu tasarimda degismez. Faz B notuna eklenir: LibreTranslate Deployment + Service + PVC (modeller) + kaynak sinirlari + `LIBRETRANSLATE_URL`.

## 9. Hata Durumlari

| Durum | Davranis |
|---|---|
| Google kapali, LibreTranslate acik | Cekimde LibreTranslate cevirir; kayit `libretranslate` etiketlenir |
| Ikisi de kapali | Bugunku davranis: orijinal metin, `needs_translation=True` |
| LibreTranslate yanit vermiyor / zaman asimi | 60 sn devre kesici; o sure boyunca zincir yalnizca Google'i dener |
| LibreTranslate yer tutucu kaybi | A3 dogrulamasi yakalar; zincirde sonraki saglayici yoksa kayit bekleyen olur |
| LibreTranslate anlam hatasi | Otomatik yakalanamaz. Etiket gorunur, orijinal metin her zaman API'de; Google acilinca yukseltilir |
| Google yukseltme sirasinda kismen basarili | Kayda yazilmaz; LibreTranslate cevirisi korunur |
| `LIBRETRANSLATE_URL` tanimsiz | LibreTranslate hic denenmez; sistem yalniz Google ile calisir |

## 10. Test Plani

Hicbir test gercek Google'a veya gercek LibreTranslate'e gitmez; HTTP cagrilari mock'lanir. Redis testleri benzersiz onek kullanir.

| Dosya | Kapsam |
|---|---|
| `test_translation_providers.py` | LibreTranslate: parcalama (satir, cumle, uzun cumle, bos satir), tek istekte liste gonderimi, birlestirme, zaman asimi/baglanti hatasi → `None` + devre kesici, URL tanimsizken `available()=False`. Google: mevcut davranisin tasindiktan sonra aynen korunmasi |
| `test_translation_chain.py` | Sira (Google once), Google `None` → LibreTranslate, Google dogrulama hatasi → LibreTranslate, ikisi de basarisiz → orijinal + sayac, `available()=False` saglayici hic cagrilmaz, `providers=['google']` kisiti, `consume_translation_providers()` sifirlama |
| `test_translation_verify.py` (genisler) | Tanimlayici korumasi: alt cizgili ad, `ad()`, `A::b()`; mevcut 14 test aynen gecer |
| `test_retranslate.py` (genisler) | Google kapali + LibreTranslate acik → devam eder ve cevirir; ikisi de kapali → durur; yukseltme yalnizca Google acikken; kismi yukseltme kayda yazilmaz; yukseltme `updated_at` ilerletir; yeni donus bicimi |
| `test_cache.py` / fetch testleri | Task kaydi `translation_provider` yazar; cache surumu 3 |
| `test_migrations_0009.py` | Veri migration'i: cevrilmis → `google`, bekleyen → `''`, `updated_at` degismez |
| v1 serializer testleri | `translation_provider` alani; bos → `null` |

Frontend etiketi `vite build` ile CI'da derlenir; gorsel dogrulama canli kontrolde yapilir.

## 11. Canli Dogrulama Hedefleri

1. `teknoloji-translate` saglikli; modeller volume'da; yeniden olusturmada model indirilmiyor.
2. Migration 0009 sonrasi uc surec yeniden baslatildi; gecmis cevrilmis kayitlar `google`.
3. Tek bir `retranslate_pending_task` calismasi Google kapaliyken bekleyen kayitlari LibreTranslate ile ceviriyor ve durmuyor.
4. Birkac calisma sonra bekleyen kayit sayisi belirgin dusuyor; yer tutucu kalintili "cevrildi" kayit 0.
5. v1 `translation_provider` donduruyor; frontend'de etiket gorunuyor.
6. `teknoloji-translate` durdurulunca bir cekim basarisiz olmuyor (kayitlar bekleyen oluyor); tekrar baslatilinca devam ediyor.

## 12. Kapsam Disi ve Sonraki Isler

- **Helm (Faz B):** LibreTranslate Deployment/Service/PVC ve `LIBRETRANSLATE_URL`.
- **Opus-MT denemesi:** Daha buyuk ucretsiz en-tr modeli (Helsinki-NLP) LibreTranslate'ten daha iyi kalite verebilir. Ayni saglayici arayuzuyle ucuncu bir saglayici olarak eklenebilir.
- **A4:** `FetchRun.translation_failures` yaninda saglayici dagilimi (`by_provider`) de kaydedilmeli; spec bolum 11'e not.
- **Kapsam disi gozlem (A3'ten):** `turkish_post_process` cumle basini buyuttugu icin `kubectl` gibi komutlar `Kubectl` olarak yaziliyor.
