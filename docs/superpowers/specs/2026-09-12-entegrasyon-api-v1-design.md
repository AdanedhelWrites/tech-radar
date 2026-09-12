# Entegrasyon API v1 — Tasarim Dokumani

- **Tarih:** 2026-09-12
- **Durum:** Onaylandi (uygulama bekliyor)
- **Kapsam:** Faz A — dis tuketici uygulamalar icin `/api/v1/` entegrasyon katmani
- **Kapsam disi:** Faz B — PostgreSQL gecisi ve Kubernetes'e tasima (mevcut Helm chart'inin dogrulanmasi; ayri dokuman)

## 1. Amac

CyberNews bugun kendi React arayuzunu besleyen bir uygulama. Amac, bunu **bagimsiz bir veri kaynagina** donusturmek: baska bir uygulama kendi arayuzunde CyberNews verisini gosterebilsin, gunluk olarak kritik zafiyetleri ve Kubernetes guncellemelerini kacirmadan cekebilsin.

Tuketici, ekibin kendi yazdigi bir servistir. Sozlesmeyi biz belirleriz.

### 1.1 Basari kriterleri

1. Tuketici, hicbir kaydi kacirmadan ve ayni kaydi tekrar tekrar islemeden delta cekebilir.
2. Ceviri hazir olmadiginda haber kaybolmaz; Ingilizce gelir, Turkcesi hazir olunca ayni kayit guncellenir.
3. Tuketici 6 saatlik takvimi beklemeden manuel cekim tetikleyebilir, ama kaynak sitelere ve ceviri kotasina zarar veremez.
4. Frontend'in kullandigi mevcut `/api/*` uc noktalari hicbir sekilde kirilmaz.

## 2. Mevcut Durumun Tespiti

Tasarim oncesi canli sistemde dogrulananlar:

| Konu | Tespit |
|---|---|
| Kimlik dogrulama | Yok — tum GET uc noktalari `AllowAny` |
| Filtreleme | Yok — severity/tarih/kaynak parametresi kabul edilmiyor |
| Sayfalama | `settings.py`'de tanimli ama view'lar kullanmiyor; sabit ilk 100 kayit |
| Surumleme | Yok; serializer'lar `fields = '__all__'` — model degisikligi dis sozlesmeyi kirar |
| Cache | Cache doluysa query parametreleri yok sayilir |
| Veri hacmi | 524 CVE (71 Kritik, 214 Yuksek), 48 Kubernetes (7 security) |
| Veritabani | Canlida SQLite; PostgreSQL yolu `settings.py`'de var ama denenmemis |
| Headless calisma | **Dogrulandi.** compose bagimliligi tek yonlu (`frontend -> api`); backend kodunda frontend referansi yok. `localhost:8000` ve ag ici `teknoloji-api:8000` cagrilari frontend olmadan calisti |

### 2.1 Tasarim sirasinda bulunan iki hata

Bunlar mevcut kodda duran, bu is kapsaminda duzeltilecek gercek hatalardir:

**H1 — Cache yeniden kurma dongunun icinde.** Alti `fetch_*` task'inda da cache, her kayit icin bir kez yeniden kuruluyor (tam sorgu + 100 nesne serilestirme + Redis yazimi). Olculen maliyet: adim basina **60.5 ms**. 135 kayitlik AI cekiminde **8.2 saniye**, 275 kayitlik CVE cekiminde ~17 saniye. Tamami israf — yalnizca son turun sonucu kullaniliyor.

**H2 — Bekleyen ceviriler kalici olarak asili kalabiliyor.** `_drop_existing`, `needs_translation=True` kayitlari listede tutuyor; ancak bu yalnizca kaynak feed o kaydi hala donduruyorsa ise yarar. Feed penceresinden cikan bir kayit bir daha hic gelmez, dolayisiyla hic yeniden cevrilmez. Bugun 434 isaretli kayit var.

## 3. Secilen Yaklasim

**Ayri `/api/v1/` entegrasyon katmani.** Yeni `news/api_v1/` paketi: kendi router'i, acik alan listeli kendi serializer'lari, TokenAuthentication, kendi throttle siniflari, kendi testleri. Mevcut `/api/*` frontend icin dokunulmadan kalir.

Elenen alternatifler:

- **Mevcut uc noktalari genisletmek:** frontend tam da bu uc noktalari kullaniyor. Auth eklemek arayuzu kirar, cache-first mantik filtrelerle catisir, `__all__` sozlesmeyi kirilgan birakir.
- **Ayri Django app veya ayri servis:** en temiz sinir, ama ayni veritabanina iki servis ve iki deploy demek. Tek tuketici icin gereksiz.

### 3.1 Ortak taban sinifi

Alti bolum ayni kalibi paylasir. `@api_view` fonksiyonlarini alti kez kopyalamak yerine ortak bir `DeltaListAPIView` sinifi yazilir; her bolum ondan turetilir. Bu hem tekrari azaltir hem de drf-spectacular'in semayi dogru cikarmasini kolaylastirir.

## 4. Uc Noktalar

### 4.1 Okuma (delta)

```
GET /api/v1/cve/          GET /api/v1/sre/
GET /api/v1/kubernetes/   GET /api/v1/devtools/
GET /api/v1/news/         GET /api/v1/ai/
```

Ortak parametreler:

| Parametre | Tip | Anlam |
|---|---|---|
| `since_cursor` | opak string | Onceki yanittan alinan imlec |
| `since` | ISO8601 tarih | Imlec yerine ilk acilis noktasi |
| `limit` | int | Varsayilan 100, tavan 500 |
| `source` | virgullu liste | Kaynak adina gore filtre |
| `needs_translation` | bool | `true` ise yalnizca ceviri bekleyenler |

Bolume ozel: CVE'de `min_severity` ve `severity`; Kubernetes'te `category`; DevTools'ta `entry_type`.

`since_cursor` ve `since` ayni anda verilirse `since_cursor` kazanir.

**Siralama her zaman `updated_at ASC, id ASC`.** Imlecin dogrulugu buna baglidir. Bu, akis sirasidir — ekrana basma sirasi degil; tuketici gosterirken kendi siralamasini uygular. Mevcut `/api/*` uc noktalarinda siralama degismez.

**Bu uc noktalar cache'e bakmaz.** Dogrudan veritabanindan okur.

### 4.2 Tetikleme

```
POST /api/v1/{bolum}/refresh/     tek bolum
POST /api/v1/refresh/             alti bolum birden
GET  /api/v1/jobs/{job_id}/       is durumu
```

### 4.3 Saglik ve durum

```
GET /api/v1/health/               kimlik dogrulama istemez
GET /api/v1/status/               token ister
```

`health` yalnizca "servis ayakta mi" sorusunu yanitlar; Kubernetes liveness/readiness probe'lari icin kullanilir (mevcut Helm chart'inda bu probe'lar tanimli).

`status` veri tazeligini raporlar — ayrinti icin bkz. bolum 11.

## 5. Yanit Semasi

### 5.1 Zarf

```json
{
  "results": [ ... ],
  "next_cursor": "eyJ1IjoiMjAyNi0wOS0xMlQxNTowMDowMC4xMjNaIiwiaSI6NTI0fQ",
  "has_more": true,
  "count": 100
}
```

`next_cursor` **her zaman** doner. Sonuc bos ise gonderilen imlec aynen geri verilir; tuketicinin saklayacak bir degeri hep olur.

`has_more: true` ise tuketici hemen tekrar cagirmali; `false` ise bir sonraki tura kadar beklemeli.

`count`, **bu sayfadaki** kayit sayisidir — toplam kayit sayisi degildir. Delta akisinda "toplam" anlamli bir kavram olmadigi icin bilincli olarak dondurulmez.

### 5.2 Ortak kayit alanlari

```json
{
  "id": 524,
  "type": "cve",
  "source": "NVD",
  "title":       { "original": "...", "tr": "..." },
  "description": { "original": "...", "tr": "" },
  "link": "https://...",
  "published_date": "2026-09-10",
  "needs_translation": true,
  "updated_at": "2026-09-12T15:00:00.123Z"
}
```

`type` alani kaydin hangi bolumden geldigini soyler ve su degerlerden birini alir: `cve`, `kubernetes`, `news`, `sre`, `devtools`, `ai`. Tuketici alti akisi tek bir tabloda birlestirirse ayirt edici olarak bu alani kullanir. Bolum adlari URL yollariyla birebir aynidir.

Dil varyantlari ic ice yerlestirilmistir: tuketici `title.tr || title.original` yazarak ceviri bekleyen kayitlarda otomatik olarak Ingilizceye duser. Duz alanlarla bu her cagri yerinde elle kontrol gerektirirdi.

### 5.3 Bolume ozel alanlar

| Bolum | Ek alanlar |
|---|---|
| CVE | `cve_id`, `severity: {code, label}`, `cvss_score`, `cwe_ids`, `references`, `affected_products`, `modified_date` |
| Kubernetes | `category`, `version` |
| DevTools | `entry_type`, `version` |
| Haber | `summary_tr`, `original_date` |
| SRE, AI | yalnizca ortak alanlar |

**Severity normalize edilir.** Veritabaninda Turkce saklanir (Kritik/Yuksek/Orta/Dusuk); API'de `{"code": "critical", "label": "Kritik"}` seklinde doner. Filtreleme `code` uzerinden yapilir: `?min_severity=high`.

**Alanlar tek tek yazilir.** `fields = '__all__'` kullanilmaz; modele alan eklendiginde dis sozlesme kendiliginden degismemelidir.

## 6. Imlec (Cursor)

### 6.1 Yapi

Icerik `{"u": "<updated_at ISO, mikrosaniye>", "i": <id>}`, base64url ile kodlanir. Tuketici acisindan **opak**tir — icini acmamalidir, boylece formati ileride degistirebiliriz.

### 6.2 Sorgu

```
WHERE updated_at > :u OR (updated_at = :u AND id > :i)
ORDER BY updated_at ASC, id ASC
LIMIT :n
```

Django ORM'de `Q(updated_at__gt=u) | Q(updated_at=u, id__gt=i)`. Bu bicim hem SQLite hem PostgreSQL'de calisir (Faz B icin onemli).

Ayni `updated_at` damgasina sahip kayitlar arasinda `id` ayirt edici oldugu icin atlama olmaz.

### 6.3 Model degisikligi

Alti modele eklenir:

```python
updated_at = models.DateTimeField(auto_now=True, verbose_name='Guncellenme Tarihi')

class Meta:
    indexes = [models.Index(fields=['updated_at', 'id'])]
```

Alan uzerinde ayrica `db_index=True` **kullanilmaz**: bilesik index zaten `updated_at` ile basladigi icin tek sutunlu index gereksiz olur ve her yazimda bosuna maliyet ekler.

Migration: `news/migrations/0008_updated_at.py`.

### 6.4 Kabul edilen sinirlar

**S1 — Ilk senkronda tum kayitlar yeni gorunur.** Migration mevcut satirlara simdiki zamani yazar; ~700 kayit tek seferde akar. Bu istenen davranistir (ilk dolum). Tuketici bunu istemiyorsa `?since=<tarih>` ile daha dar bir noktadan baslayabilir.

**S2 — Tuketici tarafindaki yazma idempotent olmalidir.** `updated_at` `auto_now` ile calisir; bir kayit yeniden islendiginde icerigi degismese bile damgasi ilerler ve delta'da yeniden gorunur. `id` anahtariyla uzerine yazan (upsert) mantik bunu sorunsuz yutar; salt "insert" mantigi cift kayit uretir.

**S3 — Silmeler akista bildirilmez.** `fetch_*` task'lari gun araliginin disindaki kayitlari veritabanindan siler; delta akisi bunu tasimaz. Tuketici kendi saklama suresini kendisi uygular. Tombstone mekanizmasi bu asamada kapsam disidir.

**Karsiliginda kazanilan ozellik:** tuketici sayfalarken Beat yeni kayit yazarsa sayfalama bozulmaz. Yeni kayitlar her zaman akisin sonuna eklenir (siralama `updated_at` artan). Offset tabanli sayfalamada araya giren kayit sayfalari kaydirir ve bazi kayitlar atlanirdi.

### 6.5 Tuketici dongusu

```
imlec = kayitliysa oku, yoksa None (ve ?since=<tarih> ile basla)
tekrarla:
    y = GET /api/v1/cve/?since_cursor=<imlec>&min_severity=high&limit=200
    her kayit icin: upsert(kayit)          # id anahtariyla, uzerine yaz
    imlec = y.next_cursor  ->  kalici olarak kaydet
    y.has_more false ise dur
```

## 7. Kimlik Dogrulama ve Hiz Siniri

### 7.1 Kimlik dogrulama

DRF'in hazir `rest_framework.authtoken` uygulamasi. `Authorization: Token <key>` basligi. Token'lar Django admin uzerinden uretilir ve iptal edilir; yeni model yazilmaz.

`/api/v1/health/` disindaki tum v1 uc noktalari token ister.

### 7.2 Hiz siniri katmanlari

| Katman | Kapsam | Deger | Neyi korur |
|---|---|---|---|
| Okuma throttle | token basina | 120/dk | Sunucuyu |
| Refresh throttle | token basina | 12/saat | Tek bozuk istemciyi durdurur |
| Bolum sogumasi | **paylasilan** | 15 dk | Kaynak siteleri ve ceviri kotasini — kac token olursa olsun |

Son iki katman ayri ayri gereklidir: throttle tek istemciyi sinirlar, soguma dis dunyayi korur.

## 8. Manuel Tetikleme

### 8.1 Uc katmanli koruma

1. **Bolum kilidi.** Redis `SET NX` ile `refresh:running:{bolum}`. O bolum icin bir is zaten calisiyorsa ikincisi baslatilmaz; calisan isin kimligi doner. Iki istemci ayni anda tetiklerse cift kazima olmaz.
2. **Bolum sogumasi.** `refresh:cooldown:{bolum}`, varsayilan 900 saniye (`REFRESH_COOLDOWN` env degiskeni ile ayarlanir).
3. **Token throttle.** DRF `ScopedRateThrottle`, `v1_refresh` scope'u.

### 8.2 Yanitlar

| Durum | Kod | Govde / Baslik |
|---|---|---|
| Baslatildi | `202` | `{"job_id": "...", "section": "cve", "status": "started", "status_url": "/api/v1/jobs/<id>/"}` |
| Zaten calisiyor | `202` | `{"job_id": "...", "status": "already_running"}` |
| Sogumada | `429` | `Retry-After: <saniye>` + hata govdesi |

`POST /api/v1/refresh/` alti bolumu de kuyruga alir; her bolum kendi sogumasina tabidir. Yanitta hangi bolumlerin baslatildigi, hangilerinin atlandigi listelenir.

### 8.3 Is durumu

`GET /api/v1/jobs/{job_id}/` — `CELERY_RESULT_BACKEND` zaten Redis'e (db 0) bagli oldugu icin ek altyapi gerektirmez.

| Durum | Anlam |
|---|---|
| `pending` | Kuyrukta, worker henuz almadi |
| `started` | Worker calisiyor |
| `success` | Bitti; `count` alani kac kayit islendigini soyler |
| `failure` | Hata; mesaj doner |

Amaci, karsi uygulamanin arayuzunde "Guncelleniyor..." gosterip bitince sonucu bildirebilmesidir. Fonksiyonel olarak zorunlu degildir (tuketici bekleyip delta cekerek de sonucu gorur), ancak basarisiz isi fark etmenin tek yoludur.

### 8.4 Maliyet notu

Manuel tetikleme ucuzdur: `skip_existing=True` sayesinde zaten cevrilmis kayitlar listeden duser, yeni icerik yoksa Google'a hic istek gitmez. Pahali olan kisim RSS kaynaklarini gezmektir (AI bolumu: 154 kayit / 66 saniye). Soguma esas olarak bunun icindir.

### 8.5 Tetikleyiciler

Sistemde iki tetikleyici olur:

1. **Celery Beat** — 6 saatte bir, bolumler 10 dk arayla kaydirilmis. Asil yol; gunluk hicbir sey kacmaz.
2. **`refresh` cagrisi** — 6 saati beklemek istemeyen tuketici icin.

Django admin bir tetikleyici **degildir**; yalnizca veri goruntuleme ve elle duzeltme aracidir.

## 9. Ceviri Dogrulugu

### 9.1 Mevcut davranis

`translate_text` basarisizlikta orijinal metni dondurur ve sayaci artirir; task bunu `needs_translation=True` olarak kaydeder. Bu mekanizma dogru calisiyor, ancak asagidaki delikleri var.

### 9.2 Eklenecek dogrulamalar

| Kontrol | Kural | Gerekce |
|---|---|---|
| Yanki | Cikti, girdiyle (bosluk/buyuk-kucuk normalize edilerek) ayniysa **ve** metin >= 4 kelimeyse basarisizlik sayilir | Google bazen girdiyi aynen dondurur; su an bu "basarili" sayilip kayit yanlislikla cevrilmis isaretleniyor |
| Kirpilma | Cikti uzunlugu girdinin %40'indan azsa basarisizlik | Uzun metinlerde kismi yanit gelebiliyor |
| Yer tutucu kalintisi | Cikti hala `__TERM_n__` iceriyorsa basarisizlik | `_restore_terms` eksik calismis demektir |

4 kelime esigi zorunludur: "Kubernetes 1.31", "CVE-2026-1234", "GitOps" gibi kisa metinler mesru olarak ayni kalir; onlari basarisiz saymak yanlis alarm uretir.

%40 esigi `TRANSLATE_MIN_RATIO` env degiskeni ile ayarlanabilir.

### 9.3 `retranslate_pending_task`

H2'yi (asili kalan ceviriler) kapatir. Feed'e hic bakmaz; dogrudan veritabanindan calisir.

- `needs_translation=True` kayitlari en eski `updated_at`'ten baslayarak alir
- Tur basina en fazla 50 kayit (`RETRANSLATE_BATCH` ile ayarlanir)
- Basarili cevirdiginde bayragi dusurur
- Devre kesici acikken Google'a hic istek atmadan aninda doner
- Celery Beat'e eklenir: `crontab(minute=5, hour='*/2')` — mevcut cekim slotlariyla (00/10/20/30/40/50) cakismaz

**Yan etkisi istenen bir ozelliktir:** bu gorev kaydi guncelledigi icin `updated_at` ilerler ve ceviri delta akisindan tuketiciye kendiliginden gider. Karsi uygulama haberi once Ingilizce alir, Turkcesi hazir olunca ayni `id` uzerine guncellemeyi alir.

## 10. Redis Cache Duzeltmeleri

| # | Degisiklik | Gerekce |
|---|---|---|
| C1 | Cache yazimi dongunun disina alinir; dongu bitince bir kez yazilir (alti task'ta da) | H1; olculen israf 8.2–17 sn |
| C2 | v1 uc noktalari cache'e hic bakmaz | Entegrasyon akisinda cache kaynakli tekrar/atlama/kayip yapisal olarak imkansiz olur |
| C3 | Cache anahtarlari surumlenir (`v2:cve_entries` gibi) | Serializer sekli degistiginde eski blob 1 saat daha servis edilmesin |
| C4 | Kismi liste sizmasi kapanir (C1'in dogal sonucu) | Su an view cache'i siliyor, task dongu icinde dolduruyor; cekim surerken okuyan yarim liste goruyor. C1 sonrasi ya eski tam liste ya yeni tam liste doner |
| C5 | 100 kayit siniri belgelenir | Cache ilk 100 kaydi tutar, veritabaninda 524 CVE var. Frontend zaten 100 gosteriyor; bilincli bir sinir oldugu kayda gecsin, ileride "kayip" sanilmasin |

## 11. Gorunurluk ve Teshis

### 11.1 Problem

Bugun tek gorunurluk, worker loglarindaki `print()` satirlaridir: ucucu, aranabilir degil, container yeniden baslayinca kaybolur. "CVE kaynagi uc turdur bos donuyor" gibi bir durumu fark etmenin hicbir yolu yok. 2026-09-11'de Dark Reading ve Krebs kaynaklarinin bozuldugunu fark etmek saatler aldi; bu bolum tam olarak onu onlemek icindir.

### 11.2 `FetchRun` modeli

Her cekim calistirmasi bir satir birakir.

| Alan | Icerik |
|---|---|
| `section` | `cve`, `kubernetes`, `news`, `sre`, `devtools`, `ai` |
| `trigger` | `beat`, `api`, `admin` |
| `started_at`, `finished_at` | Sure hesabi icin |
| `fetched_count` | Kaynaktan donen kayit sayisi |
| `saved_count` | Veritabanina yazilan kayit sayisi |
| `translation_failures` | Basarisiz ceviri sayisi |
| `status` | `running`, `success`, `failure` |
| `error` | Basarisizlikta hata ozeti |

Alti `fetch_*` task'i basta bir `FetchRun` acar, bitiste kapatir. `retranslate_pending_task` da kendi satirini yazar (`section='retranslate'`).

Teshis edilebilecek durumlar:

| Belirti | Anlami |
|---|---|
| `fetched_count` birkac turdur 0 | Kaynak bozulmus (feed URL'i olmus, 403 donuyor, format degismis) |
| `translation_failures` surekli yuksek | Google engeli devam ediyor |
| `status = failure` | Kod hatasi; `error` alaninda sebebi |
| `finished_at` bos ve `started_at` cok eski | Task asili kalmis veya worker olmus |

**Saklama:** `FetchRun` kayitlari 30 gunden eskiyse silinir; temizlik `retranslate_pending_task` ile ayni Beat turunda yapilir.

### 11.3 `GET /api/v1/status/`

Makine okunur veri tazeligi raporu. Tuketici bunu "veri bayat mi" kontrolu icin de kullanabilir.

```json
{
  "sections": {
    "cve": {
      "last_success_at": "2026-09-12T18:10:00Z",
      "last_fetched_count": 42,
      "last_saved_count": 7,
      "pending_translation": 275,
      "total": 524,
      "last_status": "success"
    }
  },
  "translation": { "circuit_open": true, "cooldown_remaining_seconds": 840 }
}
```

### 11.4 Django admin

| Degisiklik | Gerekce |
|---|---|
| `FetchRun` admin'e kaydedilir (salt okunur, bolum/durum/tarih filtreli) | En hizli bakis yeri |
| `DevToolsEntry` ve `AINewsEntry` admin'e kaydedilir | Su an hic gorunmuyorlar |
| Alti modelde `needs_translation` `list_filter`'a eklenir | "Ceviri bekleyenleri goster" tek tik olur |
| Liste ve detay goruntusunde orijinal ve Turkce metin yan yana | Yanlis cevirinin gozle gorulup elle duzeltilebilmesi icin |

### 11.5 Kabul edilen sinir

Yanki, kirpilma ve yer tutucu kalintisi **mekanik** hatalardir; bolum 9'daki kontrollerle otomatik yakalanir. Ancak "ceviri olmus ama anlam kaymis" durumu hicbir otomatik kontrolle yakalanamaz. Bu yuzden admin'de orijinal ile Turkce metnin yan yana gorunmesi ve elle duzeltme yolu acik tutulur; otomatik dogrulama bunun yerine gecmez.

## 12. Hata Sozlesmesi

Tek bicim:

```json
{ "error": { "code": "invalid_cursor", "message": "Imlec cozulemedi." } }
```

| Kod | HTTP | Durum |
|---|---|---|
| `unauthorized` | 401 | Token yok veya gecersiz |
| `invalid_cursor` | 400 | Imlec cozulemedi |
| `invalid_parameter` | 400 | Bilinmeyen veya gecersiz parametre |
| `throttled` | 429 | Hiz siniri asildi (`Retry-After`) |
| `cooldown` | 429 | Bolum sogumada (`Retry-After`) |
| `internal` | 500 | Beklenmeyen hata |

## 13. Dokumantasyon

- **`drf-spectacular`** (MIT) eklenir. `/api/v1/schema/` OpenAPI dosyasi, `/api/v1/docs/` gezilebilir arayuz.
- Ozel zarf (`results`/`next_cursor`/`has_more`) `DeltaListAPIView` uzerinde bir kez tanimlanir; her uc noktada tekrar isaretleme gerekmez.
- **Ornek istemci script'i** yazilir: delta dongusunu bastan sona yapan, ~40 satirlik calisan bir Python dosyasi. Sema bunun yerine gecmez; karsi ekip cogu zaman once bunu kullanir.
- README'ye entegrasyon bolumu ve yeni ADR eklenir.

## 14. Test Plani

TDD ile yazilir. Mevcut `news/tests.py` (12 test) bir pakete bolunur: `news/tests/`.

| Dosya | Kapsam |
|---|---|
| `test_cursor.py` | Atlama yok, tekrar yok, ayni `updated_at` damgali kayitlar, bozuk imlec 400, `since` ile baslangic, `has_more` dogrulugu |
| `test_auth.py` | Tokensiz 401, gecersiz token 401, gecerli token 200, `health` tokensiz 200 |
| `test_filters.py` | `min_severity`, `severity`, `category`, `entry_type`, `source`, `needs_translation`, `limit` tavani |
| `test_refresh.py` | Kilit (ikinci cagri yeni task acmaz), soguma 429 + `Retry-After`, throttle, toplu refresh'te atlanan bolumlerin raporlanmasi |
| `test_jobs.py` | Durum gecisleri, bilinmeyen job_id |
| `test_translation_verify.py` | Yanki yakalanir, kirpilma yakalanir, kisa metin yanlis alarm vermez, yer tutucu kalintisi yakalanir |
| `test_retranslate.py` | Bekleyen kayit feed'e bakilmadan cevrilir, basarida bayrak duser, devre kesici acikken Google'a gidilmez, batch siniri uygulanir |
| `test_cache.py` | Dongu basina tek yazim, v1 cache'e bakmaz, surumlu anahtar |
| `test_fetchrun.py` | Her cekim bir satir birakir, basarisizlikta `status=failure` ve `error` dolar, 30 gunden eski kayitlar temizlenir |
| `test_status.py` | `status` bolum basina son basarili cekimi ve bekleyen ceviri sayisini dogru raporlar, devre kesici durumu yansir |

Disaridaki tek mock, ceviri saglayicisidir. Redis ve veritabani gercek kullanilir (mevcut test kaliyla ayni).

## 15. Uygulama Sirasi

| Adim | Icerik | Bagimlilik |
|---|---|---|
| **A1** | `updated_at` + migration 0008 + index; `DeltaListAPIView`; alti okuma uc noktasi; token auth; filtreler; imlec; hata sozlesmesi; throttle; `health` | — |
| **A2** | `refresh` (tekli + toplu), `jobs`, bolum kilidi ve sogumasi | A1 |
| **A3** | Ceviri dogrulama (yanki/kirpilma/kalinti), `retranslate_pending_task`, cache duzeltmeleri C1–C5 | Bagimsiz; A1 sonrasi |
| **A4** | `FetchRun` modeli ve migration, `GET /api/v1/status/`, `health` detaylandirmasi, admin duzeltmeleri (bolum 11) | A3 (ceviri sayaclarini `FetchRun`'a yazabilmek icin) |
| **A5** | drf-spectacular semasi, ornek istemci script'i, README + ADR | A1–A4 |

A1 once gelir; `updated_at` olmadan diger adimlar anlamsizdir. A4, A3'ten sonra gelir cunku `translation_failures` sayacini ancak ceviri dogrulamasi yerine oturduktan sonra anlamli sekilde kaydedebiliriz.

## 16. Kapsam Disi

**Faz B — PostgreSQL ve Kubernetes.**

Onemli duzeltme: bu is **sifirdan degil**. Depoda zaten bir Helm chart (`helm/tech-radar/`: `postgresql.yaml`, `redis.yaml`, `backend.yaml`, `frontend.yaml`, `celery.yaml`, `ingress.yaml`, `migration-job.yaml`, `secret.yaml`, `configmap.yaml`) ve ham `k8s/` manifest'leri mevcut (commit `d453887`). Dolayisiyla Faz B, yazma degil **dogrulama ve guncelleme** isidir:

- Chart'in guncel kodla calistigini dogrulamak (hic deploy edilip edilmedigi bilinmiyor)
- Imaja kod gomme — compose su an `./:/app` bind mount ile calisiyor, yani imaj kod icermiyor olabilir; chart bunu varsayiyorsa uyusmazlik vardir
- SQLite'tan PostgreSQL'e gecis ve mevcut verinin tasinmasi
- Bu tasarimla gelen yeni env degiskenlerinin (`REFRESH_COOLDOWN`, `TRANSLATE_MIN_RATIO`, `RETRANSLATE_BATCH`) configmap/secret'a eklenmesi
- `/api/v1/health/` uc noktasinin probe'lara baglanmasi

Ayri bir tasarim turu olarak ele alinacak.

**Ertelenen maddeler:**

1. `django_celery_beat` kurulu oldugu icin admin'de "Periodic tasks" ekrani cikiyor, ancak zamanlayici dosya tabanli `PersistentScheduler` + `settings.CELERY_BEAT_SCHEDULE` kullaniyor. O ekrandan yapilan degisikligin hicbir etkisi yok; yaniltici. Ya `DatabaseScheduler`'a gecilmeli ya da ekran gizlenmeli. (A4'te ele alinmiyor; ayri karar gerektiriyor.)
2. Webhook ile push bildirimi (kritik CVE dustugunde karsi tarafa POST). Delta cekme yeterli goruldugu icin ertelendi.
3. Silinen kayitlar icin tombstone mekanizmasi (bkz. S3).

Not: `DevToolsEntry` ve `AINewsEntry`'nin admin'e kaydedilmesi artik kapsam **icindedir** (bkz. bolum 11.4).

## 17. Alinan Kararlar Ozeti

| Karar | Secim |
|---|---|
| Tuketici tipi | Ekibin kendi yazdigi servis |
| Yaklasim | Ayri `/api/v1/` katmani |
| Kapsam | Alti bolumun hepsi |
| Senkron modeli | `(updated_at, id)` imleci ile delta |
| Kimlik dogrulama | DRF `authtoken` |
| Dil | Hem orijinal hem Turkce + `needs_translation` bayragi |
| Severity | `critical/high/medium/low` + Turkce etiket |
| Soguma | 15 dakika |
| Is durumu uc noktasi | Kapsamda |
| Gorunurluk | `FetchRun` tablosu + `/api/v1/status/` + admin duzeltmeleri; ayri adim (A4) |
| Dokumantasyon | `drf-spectacular` + ornek istemci |
| Sira | A1 → A2 → A3 → A4 → A5 |
