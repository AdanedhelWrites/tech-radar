# ADR 0003: Dis Tuketiciler icin `/api/v1/` Entegrasyon Katmani

## Status
Accepted — 2026-09-12 (A1–A3 uygulandi ve `main`'de: PR #1 A2 `c435550`, PR #2 A3 `eb5f93a`; A1 dogrudan `main`'e alindi). A4 (FetchRun / `status`) ve A5 (sema, ornek istemci, README) henuz uygulanmadi.

Tasarim: [`superpowers/specs/2026-09-12-entegrasyon-api-v1-design.md`](superpowers/specs/2026-09-12-entegrasyon-api-v1-design.md). Uygulama planlari: `superpowers/plans/2026-09-12-entegrasyon-api-v1-a{1,2,3}.md`. Spec ile plan celistiginde planlarin "Spec'e Gore Netlestirmeler" bolumleri gecerlidir.

## Context
CyberNews bugune kadar yalnizca kendi React arayuzunu besliyordu. Ekibin yazdigi ayri bir uygulamanin CyberNews verisini kendi arayuzunde gostermesi ve gunluk kritik zafiyetleri / Kubernetes guncellemelerini kacirmadan cekmesi istendi.

Mevcut `/api/*` uc noktalari bu is icin uygun degildi (2026-09-12 tespiti):

- Kimlik dogrulama yok (`AllowAny`), filtre yok, sayfalama tanimli ama kullanilmiyor (sabit ilk 100 kayit).
- Serializer'lar `fields = '__all__'`: modele alan eklemek dis sozlesmeyi degistirir.
- Cache-first mantik: cache doluysa query parametreleri yok sayilir.
- Tasarim sirasinda iki gercek hata bulundu: cache alti fetch task'inda da kayit basina yeniden kuruluyordu (135 kayitta 8.2 sn israf) ve feed penceresinden cikan `needs_translation=True` kayitlar bir daha hic cevrilmiyordu (434 asili kayit).

## Decision

1. **Ayri `/api/v1/` katmani** (`news/api_v1/` paketi). Mevcut `/api/*` uc noktalarina, `news/views.py`, `news/urls.py` ve `news/serializers.py` dosyalarina dokunulmaz; frontend onlara bagli. v1 kendi serializer'larini (alanlar tek tek yazilir), kendi izin/throttle siniflarini ve kendi testlerini tasir.

2. **Delta senkron: `(updated_at, id)` keyset imleci.** Alti modele `updated_at` (`auto_now`) ve bilesik `(updated_at, id)` index'i eklendi (migration `0008_updated_at`). Siralama her zaman `updated_at ASC, id ASC`; sorgu `updated_at > u OR (updated_at = u AND id > i)`. Imlec base64url ile kodlanmis `{"u", "i"}`'dir ve tuketici icin **opak**tir. Yanit zarfi `results / next_cursor / has_more / count`; `next_cursor` bos sonucta bile doner, `count` yalnizca sayfadaki kayit sayisidir. Offset sayfalama reddedildi: cekim sirasinda araya giren kayitlar sayfalari kaydirip atlamaya yol acar.

3. **v1 cache'e hic bakmaz;** dogrudan veritabanindan okur. Entegrasyon akisinda cache kaynakli tekrar/atlama yapisal olarak imkansiz olur.

4. **Kimlik dogrulama: DRF `rest_framework.authtoken`** (`Authorization: Token <key>`). Token'lar Django admin'den uretilir ve iptal edilir; yeni model yazilmaz. Yalnizca `GET /api/v1/health/` tokensizdir (Kubernetes probe'lari icin).

5. **Uc katmanli hiz siniri.** Okuma throttle token basina `120/dk` (`v1_read`); refresh throttle token basina `12/saat` (`v1_refresh`); bolum sogumasi **paylasilan** 15 dk (`REFRESH_COOLDOWN`, Redis). Throttle tek istemciyi sinirlar, soguma kaynak siteleri ve ceviri kotasini korur — kac token olursa olsun.

6. **Manuel tetikleme** (`POST /api/v1/<bolum>/refresh/`, `POST /api/v1/refresh/`, `GET /api/v1/jobs/<id>/`). Redis `SET NX` bolum kilidi (`REFRESH_LOCK_TTL`, varsayilan 3600 sn) cift kazimayi onler; kilit `task_postrun` sinyaliyle birakilir. Baslatildi ve zaten calisiyor `202`, sogumada `429 + Retry-After`. Toplu refresh her zaman `202` doner; govdede `started / already_running / skipped` listeleri. Task icinde yakalanip `{'success': False, 'error': ...}` olarak donen hata da `failure` sayilir.

7. **Dil: orijinal + Turkce ic ice** (`title: {original, tr}`) ve `needs_translation` bayragi. Tuketici `title.tr || title.original` ile ceviri bekleyen kayitta Ingilizceye duser. Severity veritabaninda Turkce kalir, API'de `{code: "critical", label: "Kritik"}` olarak normalize edilir; filtre `code` uzerindendir (`?min_severity=high`).

8. **Tek bicim hata sozlesmesi:** `{"error": {"code", "message"}}`; kodlar `unauthorized 401`, `invalid_cursor 400`, `invalid_parameter 400`, `throttled 429`, `cooldown 429`, `internal 500`.

9. **Ceviri dogrulugu ve cache duzeltmeleri (A3).** `translate_text` ciktiyi geri koymadan once onarir, sonra dogrular: yanki (>= 4 cevrilecek kelime), kirpilma (>= 80 karakterde, `TRANSLATE_MIN_RATIO` 0.4), eksik yer tutucu ve kalinti (`XTRM0001X` formati). Dogrulanamayan metin orijinal kalir ve `needs_translation=True` isaretlenir; bu durum devre kesiciyi **tetiklemez** (sorun erisim degil icerik). `retranslate_pending` feed'e bakmadan, bolum basina Redis imleciyle bekleyenleri yeniden cevirir ve Beat'te tek saatlerde (`minute=5, hour='1-23/2'`) calisir; fetch slotlariyla (00/06/12/18) cakismaz. Cache her 10 kayitta bir ve cekim sonunda kurulur (frontend'in akis halinde gostermesi korunur); surumleme `CACHES['default']['VERSION']` ile yapilir.

### Elenen alternatifler

| Alternatif | Neden elendi |
|---|---|
| Mevcut `/api/*` uc noktalarini genisletmek | Auth eklemek arayuzu kirar; cache-first mantik filtrelerle catisir; `__all__` sozlesmeyi kirilgan birakir |
| Ayri Django app veya ayri servis | Ayni veritabanina iki servis, iki deploy; tek tuketici icin gereksiz |
| Offset sayfalama | Cekim sirasinda kayit atlar |
| Webhook ile push | Delta cekme yeterli goruldu; ertelendi |
| Retranslate icin `translation_attempted_at` alani | Migration gerektirirdi; 2026-09-12 migration regresyonundan sonra Redis imleci tercih edildi |

### Uygulama sirasinda duzeltilen varsayimlar

- **Celery uygulamasi Django surecinde yuklenmiyordu** (`cybernews/__init__.py` bos); `jobs` uc noktasi `DisabledBackend` goruyordu. A2'de duzeltildi, `CELERY_TASK_TRACK_STARTED` eklendi.
- **Yer tutucu formati** spec'teki `__TERM_n__` degil `XTRM0001X`; ic ice geri koyma sirasi ve bozuk yer tutucu onarimi (H5/H6) canli veride 19 CVE'yi bozmustu, A3'te duzeltildi ve `bozuk_cevirileri_isaretle` komutu eklendi.
- **View testleri canli Redis'e yaziyordu;** `V1TestCase` (locmem cache, WhiteNoise'suz) ile ayrildi. Testler hicbir zaman gercek Celery isi kuyruga atmaz, `FLUSHDB` kullanmaz.
- **Migration sonrasi api/worker/scheduler yeniden baslatilmali** (bind mount kod yeniden yuklemez). 2026-09-12'de atlanan yeniden baslatma bir CVE cekimini `NOT NULL` hatasiyla dusurdu.

## Consequences

- **Positive:** Tuketici hicbir kaydi kacirmadan ve tekrar islemeden delta cekebilir; Beat sayfalama sirasinda yazsa bile sayfalama bozulmaz. Ceviri hazir olmayan haber kaybolmaz: once Ingilizce gider, Turkcesi hazir olunca `updated_at` ilerledigi icin ayni `id` uzerine guncelleme gelir. Frontend'in sozlesmesi degismedi. Cache israfi (~%90) kalkti; asili ceviriler kendiliginden eriyor.
- **Negative / kabul edilen sinirlar:**
  - Ilk senkronda tum kayitlar yeni gorunur (migration mevcut satirlara simdiki zamani yazar); tuketici `?since=` ile daraltabilir.
  - `auto_now` icerik degismese de damgayi ilerletir; **tuketici tarafi upsert (idempotent) olmalidir**, salt insert cift kayit uretir.
  - Silmeler akista bildirilmez (tombstone yok); tuketici kendi saklama suresini uygular.
  - Frontend cache'i ilk 100 kaydi tutar; bu bilincli bir sinirdir.
  - "Ceviri olmus ama anlam kaymis" durumu otomatik yakalanamaz; admin'de orijinal/Turkce yan yana gosterimi (A4) bunun icindir.
- **Acik isler:** **A4 tamamlandi (2026-09-21).** Bu belgenin bolum 11'i (`FetchRun`, `GET /api/v1/status/`, admin) artik [ADR-0006](ADR-0006-FetchRun-Gorunurlugu-ve-Status-Ucu.md) ile degistirilmistir; oradaki alan listesi ve yanit govdesi gecerlidir. **Siralama 2026-09-17'de degisti: A4'ten once [ADR-0005](ADR-0005-CVE-Saklama-ve-Gemini-Onceligi.md) (saklama olcusu ve CVE'ye Gemini onceligi) uygulanir** — A4 onun sonucunu olcen adimdir. ADR-0005 ayrica asagidaki "tuketici tarafi upsert olmalidir" maddesini duzeltir: `id` bugun kararli degildir, tuketici `cve_id`/`link` uzerinden upsert etmelidir (A5'te yazili hale gelecek). A4 — `FetchRun` modeli, `GET /api/v1/status/`, admin duzeltmeleri (ceviri saglayici dagilimi `by_provider` dahil, bkz. [ADR-0004](ADR-0004-Ceviri-Saglayici-Zinciri.md)); A5 — drf-spectacular semasi, ornek istemci script'i, README entegrasyon bolumu ve env degiskenleri (`REFRESH_COOLDOWN`, `REFRESH_LOCK_TTL`, `TRANSLATE_MIN_RATIO`, `RETRANSLATE_BATCH`). Faz B — PostgreSQL ve Helm dogrulamasi ayri karar.
