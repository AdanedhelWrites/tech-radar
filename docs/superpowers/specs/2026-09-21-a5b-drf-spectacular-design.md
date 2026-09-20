# A5b — drf-spectacular Semasi, `/api/v1/schema/` ve `/api/v1/docs/` — Tasarim Dokumani

- **Tarih:** 2026-09-21
- **Durum:** Onaylandi (bolum 1-3 ve sidecar karari kullanici onayindan gecti 2026-09-21). Uygulanmadi.
- **Kapsam:** `drf-spectacular[sidecar]` bagimliligi; `news/api_v1/schema.py` (yeni) icinde zarf ve yanit serializer'lari, parametre tanimlari, v1 filtresi; `news/api_v1/serializers.py`'ye tip ipuclari; `news/api_v1/urls.py`'ye `extend_schema_view` uygulamasi ve iki yeni rota; `settings.py`
- **Kapsam disi:** `news/api_v1/views.py` — **tek istisna** modul docstring'ine eklenecek iki satirlik yon gosterme notudur (bkz. 4.1); hicbir view mantigi, dekoratoru veya imzasi degismez. Eski `/api/*` uc noktalari (semaya **girmez**, bkz. 2.1); ReDoc (yalniz Swagger UI); istemci SDK uretimi; sema surumleme/yayimlama sureci; Faz B (PostgreSQL, Helm)
- **Iliskili:** [ADR-0003](../../ADR-0003-Entegrasyon-API-v1.md) (v1 sozlesmesi, A5 yol haritasi), [ADR-0005](../../ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md) (upsert anahtari), [ADR-0006](../../ADR-0006-FetchRun-Gorunurlugu-ve-Status-Ucu.md) (`/status/` alan listesi)
- **Selef:** A5a (merge `6255f3d`) ornek istemciyi, README entegrasyon bolumunu ve upsert kuralini getirdi. A5b A5'in kalan yarisidir.
- **Migration:** **Yok.**
- **Bagimlilik:** **Var** (`drf-spectacular[sidecar]`). Dagitimda `restart` **yetmez**; imaj yeniden olusturulur ve api/worker/scheduler ucu birden yeniden yaratilir (bkz. bolum 7).

## 1. Amac

### 1.1 Problem

ADR-0003 dis tuketici icin bir entegrasyon katmani tanimladi ve A5a onu insan tarafindan okunur biçimde belgeledi (README + ornek istemci). Eksik olan **makine tarafindan okunur sozlesme**: tuketici ekibin istemcisini elle yazmasi ve her alan degisikligini README diff'inden takip etmesi gerekiyor.

### 1.2 Tasarimi belirleyen olcum

A5b'ye baslamadan once `drf-spectacular` 0.30.0 konteynere **gecici olarak** kuruldu, dekorasyonsuz sema uretildi ve paket geri kaldirildi (konteyner imajla ayni birakildi). Olculen sonuc, bu tasarimin merkezindedir:

| Bulgu | Olcum |
|---|---|
| Uretilen yol sayisi | **41** — 11 v1 + **30 eski `/api/*`** |
| Alti delta ucunun 200 semasi | Zarf degil **ciplak serializer** |
| Delta uclarinin query parametreleri | **0** (dokuzun hicbiri) |
| `health` / `status` / `jobs` / `refresh` | "unable to guess serializer" -> 200 semasi yok |
| Serializer method-field uyarisi | **~28** -> `title` `string` olarak belgeleniyor |
| `operationId` | `/{section}/refresh/` ve `/refresh/` ikisi de `v1_refresh_create` |

**Kritik cikarim: dekorasyonsuz sema eksik degil, YANLIS.** Iki madde bunu belirler. Birincisi, alti delta ucu gercekte `{results, next_cursor, has_more, count}` zarfi dondururken sema tek bir `CVEEntryV1` nesnesi donuyormus gibi yazar. Ikincisi, `title` gercekte `{original, tr}` iken sema `string` yazar. Bu semadan istemci ureten bir tuketici **derlenen ama calismayan** kod alir.

Bu, A5b'nin basari olcutunu degistirir: hedef "bir sema yayimlamak" degil, **yanlis sema yayimlamamaktir**. Yarim yapilmis bir A5b, hic yapilmamis A5b'den kotudur — cunku tuketici README'ye degil semaya guvenir.

### 1.3 Basari kriterleri

1. `/api/v1/schema/` OpenAPI 3 dokumani dondurur ve yalnizca `/api/v1/` yollarini icerir.
2. Sema uretimi **sifir uyari** ile tamamlanir.
3. Alti delta ucunun 200 semasi zarfi gosterir; `results` ilgili kayit tipinin dizisidir.
4. `title`, `description` ve `severity` ic ice nesne olarak; `translation_provider` nullable string olarak belgelenir.
5. Dokuz query parametresinin tamami ilgili uclarda gorunur.
6. `/api/v1/docs/` Swagger UI'yi **internet erisimi olmadan** acar.
7. Mevcut 303 test kirilmaz; `/api/*` ve v1 davranisi degismez.

## 2. Secilen Yaklasim

Sema metadata'si **ayri bir modulde** (`news/api_v1/schema.py`) toplanir ve `urls.py`'de `extend_schema_view` ile uygulanir. `views.py` metinsel olarak degismez. `serializers.py` yalnizca **stdlib tip ipuclari** alir; drf_spectacular import'u oraya girmez.

Gerekce: `views.py` bugun 380 satir ve ciddi mantik tasiyor (imlec, filtre, hata esleme, Celery durum cevirisi). Her uca cok satirli `@extend_schema` blogu eklemek dosyayi okunmaz hale getirir ve sozlesmeyi alti ayri yere dagitir. Tek dosyada toplandiginda "dis sozlesme neye benziyor" sorusu tek dosya okunarak yanitlanir.

### 2.1 Elenen alternatifler

| Alternatif | Neden elendi |
|---|---|
| Dekoratorleri dogrudan `views.py`'ye koymak | Django/DRF'in daha yaygin deyimi ve senkron kalmasi daha olasi, ama `views.py`'yi belirgin buyutur ve mantik ile dokumantasyonu ic ice gecirir (kullanici karari) |
| Elle yazilmis statik OpenAPI YAML | Koddan tamamen kopuk; ilk alan degisikliginde sessizce bayatlar — A5b'nin cozmeye calistigi problemin ta kendisi |
| Semayi dekorasyonsuz birakip yayimlamak | Olculdu: sema **yanlis** olurdu (1.2). Hicbir sema yayimlamamaktan kotu |
| Eski `/api/*` uclarini da belgelemek | ADR-0003 onlari frontend'e ait sayar ve sozlesme vermez; semaya girerlerse istemeden dis sozlesme olurlar |
| Gercek serializer'lar yerine paralel "dokuman" serializer'lari yazmak | Kodla baglantisi olmadigi icin sessizce ayrisir; yanlis semayi kalicilastirir |
| Sema snapshot / dondurma testi | Kullanici istemedi; yerine hedefli sozlesme assert'leri (bolum 6). Kabul edilen sinir olarak 10. bolumde kayitli |
| ReDoc'u da sunmak | Ikinci bir arayuz, ikinci bir varlik seti; Swagger UI yeterli |
| Swagger UI varliklarini CDN'den cekmek | k8s'te internetsiz ortamda docs sayfasi bos acilir; `[sidecar]` varliklari imajdan sunar (kullanici karari) |

## 3. Bilesenler

### 3.1 `requirements.txt`

`drf-spectacular[sidecar]==0.30.0` eklenir (surum olculen surumdur). `requirements_docker.txt` **degismez** — o dosya Flask tabanli scraper icindir, Django'yu icermez.

### 3.2 `cybernews/settings.py`

- `INSTALLED_APPS` sonuna `'drf_spectacular'` ve `'drf_spectacular_sidecar'`.
- `REST_FRAMEWORK['DEFAULT_SCHEMA_CLASS'] = 'drf_spectacular.openapi.AutoSchema'`.
- Yeni `SPECTACULAR_SETTINGS`: `TITLE`, `DESCRIPTION` (upsert anahtari kuralina ve README'ye isaret eder), `VERSION = '1.0.0'`, `SERVE_INCLUDE_SCHEMA = False`, `PREPROCESSING_HOOKS = ['news.api_v1.schema.yalniz_v1']`, `SWAGGER_UI_DIST = 'SIDECAR'`, `SWAGGER_UI_FAVICON_HREF = 'SIDECAR'`.

`DEFAULT_SCHEMA_CLASS` global bir ayardir ve teknik olarak eski `/api/*` view'larini da kapsar. **Davranissal etkisi yoktur:** sema sinifi yalnizca sema uretiminde kullanilir, istek isleme yolunda degil; ustelik eski uclar 3.3'teki filtreyle semadan tamamen cikarilir. ADR-0003'un "`/api/*`'a dokunulmaz" maddesi korunur.

### 3.3 `news/api_v1/schema.py` (yeni)

Dort sorumluluk:

1. **`yalniz_v1(endpoints)`** — preprocessing hook. Yolu `/api/v1/` ile baslamayan her ucu eler. Olcum gosterdi ki bu olmadan semaya 30 eski uc girer.
2. **Zarf serializer'lari** — alti bolum icin `{results, next_cursor (nullable), has_more, count}`. `results` ilgili `*V1Serializer`'in `many=True` hali. Bir fabrika fonksiyonuyla uretilir; alti sinif elle kopyalanmaz.
3. **Yanit serializer'lari** — `health`, `status` (bolum basina ic ice), `jobs`, tek bolum `refresh`, toplu `refresh` ve **hata sozlesmesi** (`{"error": {"code", "message"}}`) icin. `/status/` alan listesi ADR-0006 bolum 4'ten birebir alinir; operator alanlari (Gemini butcesi, `by_provider`, `stopped_reason`, `trigger`, `error`) semaya **girmez**.

   Hata serializer'i bosta durmaz: her ucun `@extend_schema(responses=...)` haritasina o ucun gercekten uretebildigi hata kodlari eklenir — tum uclarda `401`, delta uclarinda ayrica `400` (`invalid_cursor` / `invalid_parameter`) ve `429`, `refresh` uclarinda `429` (`cooldown`, `Retry-After` basligiyla), `jobs` ve tek bolum `refresh` icin `404`. ADR-0003 bolum 8'deki kod listesi kaynaktir.
4. **Parametre tanimlari** — dokuz query parametresi (`since_cursor`, `since`, `limit`, `source`, `needs_translation`, `min_severity`, `severity`, `category`, `entry_type`). Ortak yedisi bir listede toplanir; `min_severity`/`severity` yalniz CVE'ye, `category` yalniz Kubernetes'e, `entry_type` yalniz DevTools'a eklenir. `min_severity` ve `severity` icin gecerli degerler (`low`/`medium`/`high`/`critical`) enum olarak verilir.

### 3.4 `news/api_v1/serializers.py` — yalnizca tip ipuclari

Iki `TypedDict` eklenir (`DilAlani {original, tr}`, `SiddetAlani {code, label}`) ve bes method field'a donus ipucu yazilir:

| Metot | Ipucu |
|---|---|
| `get_type` | `-> str` |
| `get_title`, `get_description` | `-> DilAlani` |
| `get_translation_provider` | `-> Optional[str]` |
| `get_severity` (CVE) | `-> SiddetAlani` |

Yalnizca `typing` import edilir. Bu, ~28 uyarinin tamamini kaldirir ve `title`'i dogru belgeler (4.2'de dogrulandi). Sema kutuphanesi `schema.py` ve `settings.py` ile sinirli kalir.

### 3.5 `news/api_v1/urls.py`

- Her view sinifina `schema.py`'den gelen `extend_schema_view` uygulanir.
- Iki yeni rota: `schema/` (`SpectacularAPIView`) ve `docs/` (`SpectacularSwaggerView`, `url_name='v1-schema'`).

### 3.6 Sema ve docs uclarinin kimlik dogrulamasi

Ikisi de kimlik dogrulamasi ister (kullanici karari): v1'in geri kalaniyla tutarli, yalniz `/health/` aciktir.

**Pratik sorun ve cozumu:** tarayici `Authorization: Token ...` basligi gondermez, yani yalniz `TokenAuthentication` ile `/api/v1/docs/` tarayicida her zaman 401 verir ve arayuz kullanilamaz hale gelir. Bu yuzden iki uc `authentication_classes = [TokenAuthentication, SessionAuthentication]` ve `permission_classes = [IsAuthenticated]` tasir: admin'de oturum acmis bir kullanici docs'u tarayicida acar, tuketici ekip semayi token ile `curl` veya kendi araciyla ceker. `SessionAuthentication`'in CSRF korumasi yalniz guvensiz metotlarda devreye girer; iki uc da salt `GET`'tir.

## 4. Dogrulanmis Mekanizmalar

Bu tasarimin iki tasiyici varsayimi **varsayim olarak birakilmadi**, sonda ile olculdu (2026-09-21).

### 4.1 `extend_schema_view` modul disindan uygulanabiliyor — ama sinifi yerinde degistiriyor

Sonda `CVEDeltaView`'a `urls.py` konumundan zarf ve iki parametre uyguladi: 200 semasi `#/components/schemas/CVEZarf`'a baglandi, parametreler (`limit`, `since_cursor`) sema ciktisina girdi, zarfin dort alani gorundu.

**Onemli uyari:** `extend_schema_view(...)(views.CVEDeltaView) is views.CVEDeltaView` -> **`True`**. Dekorator yeni bir sinif dondurmez, mevcut sinifi **yerinde** degistirir. Yani "`views.py` degismez" ozelligi **metinseldir**; calisma zamaninda `urls.py` import edildigi anda view siniflari dekore edilir. Bu kabul edilebilir (davranis degismez, yalnizca `schema` niteligi eklenir) ama dosyaya bakip "bu view'in semasi yok" diyen birini yaniltabilir. **Bu yuzden `views.py`'nin modul docstring'ine semanin `schema.py`'de yasadigini soyleyen iki satir eklenir** — tek kapsam disi istisna, davranis degil yon gosterme.

### 4.2 `TypedDict` donus ipuclari method field'lari cozuyor

Sonda `DilAlani` ve `SiddetAlani` ipucuyla bir serializer uretti: `title` ve `severity` `type: object` + dogru `properties` + `required` olarak, `Optional[str]` `nullable: true` olarak cikti ve **uyari sayisi 0** oldu. `@extend_schema_field` ve dolayisiyla `serializers.py`'ye drf_spectacular import'u gerekmedi.

### 4.3 Dogrulanmamis, planin ilk gorevinde dogrulanacak

`PREPROCESSING_HOOKS` imzasi ve sidecar ayarlari belgelenmis standart kullanimdir ama bu projede olculmedi. Planin ilk gorevi bunlari calistirip dogrulamalidir; beklenmedik bir durumda tasarim bolum 3.3/3.2 guncellenir.

## 5. Hata ve Risk Durumlari

| Durum | Davranis |
|---|---|
| Sema uretimi uyari veriyor | Test kirilir (bolum 6). Uyari, bir alanin yanlis belgelendiginin gostergesidir |
| Yeni bir bolum/uc eklenip `schema.py` guncellenmezse | Uc semada eksik veya yanlis gorunur. Bolum 6'daki uc sayisi assert'i bunu yakalar |
| Sidecar varliklari toplanmamis | Docs sayfasi stilsiz/bos acilir. `entrypoint.sh` zaten `collectstatic --noinput` calistirir; ek adim gerekmez |
| Worker/scheduler imaji guncellenmemis | `INSTALLED_APPS` yeni paketi arar, konteyner **acilmaz**. Bolum 7 bunu onler |
| Tarayicidan tokensiz `/api/v1/docs/` | 401. Beklenen davranis; admin oturumu ile acilir (3.6) |

## 6. Test Plani

TDD. Yeni dosya `news/tests/test_schema.py`. Hicbir test aga cikmaz.

| Test | Kapsam |
|---|---|
| Uyarisiz uretim | Sema uretimi sirasinda toplanan uyari listesi **bos** olmalidir (olcumdeki ~28 uyarinin regresyonu) |
| Yalniz v1 | Semadaki yollarin **tamami** `/api/v1/` ile baslar; eski `/api/*` yollarindan hicbiri yok (30 yolun sizmasi regresyonu) |
| Zarf sekli | Alti delta ucunun 200 semasi `results`, `next_cursor`, `has_more`, `count` anahtarlarini tasir; `results` bir dizidir |
| `title` nesne | `title` semasi `type: object` ve `original`/`tr` ozelliklerini tasir — **`string` degil** (1.2'nin ikinci kritik bulgusunun regresyonu) |
| Parametreler | Her delta ucu ortak yedi parametreyi; CVE ayrica `min_severity`+`severity`, Kubernetes `category`, DevTools `entry_type` tasir |
| `operationId` benzersiz | Semadaki tum `operationId` degerleri benzersizdir (cakisma regresyonu) |
| `/status/` darligi | `/status/` yanit semasinda `by_provider`, `stopped_reason`, `trigger`, `error` **yoktur** (ADR-0006 karar 4) |
| Uclarin kimlik dogrulamasi | `/api/v1/schema/` ve `/api/v1/docs/` tokensiz **401**; token ile 200. Kod 403 degil 401'dir cunku `TokenAuthentication` listede ilk siradadir ve DRF `WWW-Authenticate` basligini ondan turetir — sira degisirse bu test kirilir, kasitlidir |

Mevcut **303** testin hicbiri kirilmamalidir.

## 7. Dagitim

Bagimlilik degistigi icin `restart` **yetmez**:

```bash
docker compose up -d --build teknoloji-api teknoloji-worker teknoloji-scheduler
```

Ucu de gereklidir: paket `INSTALLED_APPS`'e girdigi icin worker ve scheduler de import eder; yalniz api yeniden olusturulursa digerleri **acilmaz**. `collectstatic` entrypoint'te zaten calisir, sidecar varliklari otomatik toplanir. Migration yoktur.

## 8. Canli Dogrulama Hedefleri

1. `/api/v1/schema/` token ile 200 doner; dokumandaki yol sayisi **11**'dir ve hicbiri `/api/v1/` disinda degildir.
2. Sema uretimi konteyner loglarinda **hicbir uyari** birakmaz.
3. `/api/v1/docs/` admin oturumuyla acilir ve Swagger UI **aga cikmadan** yuklenir (tarayici ag sekmesinde CDN istegi olmamalidir).
4. Docs'ta `cve` ucunun yanit ornegi zarfi gosterir ve `title` ic ice nesne olarak gorunur.
5. Uc servis de `up -d --build` sonrasi saglikli acilir; `/api/v1/health/` 200 doner.
6. A5a'nin `scripts/ornek_istemci.py`'si degisiklik sonrasi hala ucten uca calisir (v1 davranisinin degismedigi kaniti).

## 9. Kapsam Disi ve Sonraki Isler

- **Istemci SDK uretimi:** sema hazir olunca `openapi-generator` ile istemci uretmek tuketici ekibin isidir; bu repoda uretilmez.
- **Sema surumleme:** sema `VERSION = '1.0.0'` ile baslar. Alan degisikliginde surumun nasil ilerleyecegi ve tuketiciye nasil haber verilecegi **ayri bir karardir**.
- **ADR:** A5b yeni bir mimari karar uretmiyorsa ayri ADR yazilmaz; ADR-0003'un Status satiri ve acik isler maddesi guncellenir. Sema dis sozlesme haline geldigi icin bu, ADR-0003'e bir cumle olarak islenmelidir.
- **`NewsArticle.link` benzersizligi:** A5a'da acilan ayri gorev; A5b'yi bloke etmez.
- **Faz B:** PostgreSQL ve Helm.

## 10. Kabul Edilen Sinirlar

- **Snapshot testi yok** (kullanici karari). Bolum 6'daki hedefli assert'ler zarfi, `title`'i, parametreleri, `operationId` benzersizligini ve `/status/` darligini korur; **bunlarin disinda** bir alan tipi sessizce degisebilir ve hicbir test kirilmaz.
- **`schema.py` view'lardan bagimsizdir ve zamanla ayrisabilir.** Yeni bir uc eklenip `schema.py` guncellenmezse sema eksik kalir; bolum 6'daki uc sayisi assert'i bunu yakalar ama yeni bir *parametre* eklenmesini yakalamaz.
- **Dekorator view siniflarini yerinde degistirir** (4.1). Davranis degismez ama `views.py`'ye bakan biri semanin nerede tanimlandigini gormez; docstring notu bunu hafifletir, ortadan kaldirmaz.
- **Imaj buyur** (~2 MB sidecar varliklari). Internetsiz ortamda docs'un calismasinin bedeli.
- **Sema yayimlandigi andan itibaren dis sozlesmedir.** Bugune kadar sozlesmeyi README tasiyordu ve bir hata "dokumantasyon hatasi"ydi; sema yayimlandiktan sonra ayni hata tuketicinin istemcisini kirar.
